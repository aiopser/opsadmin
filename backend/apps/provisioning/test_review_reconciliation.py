import base64
import json
from unittest.mock import patch

from apps.cmdb.models import AssetHost
from .models import ProvisioningAttempt
from .test_contract import request_record, ready_plan


def applied_attempt(record):
    record.execution_status = "success"
    record.save()
    return ProvisioningAttempt.objects.create(
        plan=ready_plan(record),
        actor=record.created_by,
        idempotency_key="review-once",
        status="applied",
        recovery_artifact_key="x",
    )


def files():
    state = {
        "resources": [
            {
                "mode": "managed",
                "type": "alicloud_instance",
                "instances": [{"attributes": {"id": "i-review"}}],
            }
        ]
    }
    return {"terraform.tfstate": base64.b64encode(json.dumps(state).encode()).decode()}


def observed(**overrides):
    return {
        "source_id": "i-review",
        "hostname": "windows",
        "internal_ip": "10.2.2.2",
        "os_family": "windows",
        **overrides,
    }


def test_readback_initializes_windows_connection_and_preserves_manual_fields(
    request_record,
):
    from .reconciliation import reconcile_attempt

    attempt = applied_attempt(request_record)
    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", return_value=[observed()]
    ):
        store.return_value.get.return_value = {"files": files()}
        reconcile_attempt(attempt.pk)
    host = AssetHost.objects.get(source_id="i-review")
    assert (host.os_family, host.connection_type, host.connection_port) == (
        "windows",
        "winrm",
        5986,
    )
    host.connection_port = 12345
    host.save()
    attempt.status = "applied"
    attempt.save()
    request_record.inventory_status = "failed"
    request_record.save()
    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", return_value=[observed()]
    ):
        store.return_value.get.return_value = {"files": files()}
        reconcile_attempt(attempt.pk)
    host.refresh_from_db()
    assert host.connection_port == 12345


def test_older_readback_failure_cannot_replace_newer_success(request_record):
    from .reconciliation import reconcile_attempt

    attempt = applied_attempt(request_record)
    calls = 0

    def read(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            reconcile_attempt(attempt.pk)
            raise RuntimeError("older reader failed after newer completion")
        return [observed()]

    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", side_effect=read
    ), patch.object(
        reconcile_attempt, "retry", return_value=RuntimeError("retry")
    ) as retry:
        store.return_value.get.return_value = {"files": files()}
        try:
            reconcile_attempt(attempt.pk)
        except RuntimeError:
            pass
    request_record.refresh_from_db()
    attempt.refresh_from_db()
    assert request_record.inventory_status == "success"
    assert attempt.status == "reconciled" and attempt.error_message == ""
    retry.assert_not_called()


def test_ambiguous_broker_failure_does_not_downgrade_completed_readback(request_record):
    from .reconciliation import queue_reconciliation, reconcile_attempt

    attempt = applied_attempt(request_record)

    def completed_then_error(*, args, queue):
        reconcile_attempt(*args)
        raise RuntimeError("broker acknowledgement lost")

    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", return_value=[observed()]
    ), patch.object(reconcile_attempt, "apply_async", side_effect=completed_then_error):
        store.return_value.get.return_value = {"files": files()}
        assert not queue_reconciliation(attempt.pk)
    request_record.refresh_from_db()
    assert request_record.inventory_status == "success"


def test_failed_dispatch_fences_a_message_that_was_accepted_before_error(
    request_record,
):
    import pytest
    from .contracts import ProvisioningError
    from .reconciliation import queue_reconciliation, reconcile_attempt

    attempt = applied_attempt(request_record)
    with patch.object(
        reconcile_attempt,
        "apply_async",
        side_effect=RuntimeError("broker acknowledgement lost"),
    ) as dispatch, pytest.raises(ProvisioningError):
        queue_reconciliation(attempt.pk)
    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", return_value=[observed()]
    ) as read:
        store.return_value.get.return_value = {"files": files()}
        reconcile_attempt(*dispatch.call_args.kwargs["args"])
    read.assert_not_called()
    request_record.refresh_from_db()
    assert request_record.inventory_status == "failed"


def test_explicit_readback_rechecks_previously_reconciled_inventory(request_record):
    from .reconciliation import queue_reconciliation, reconcile_attempt

    attempt = applied_attempt(request_record)
    attempt.status = "reconciled"
    attempt.save()
    request_record.inventory_status = "success"
    request_record.save()
    with patch.object(reconcile_attempt, "apply_async") as dispatch:
        assert queue_reconciliation(attempt.pk, force=True)
    assert dispatch.call_count == 1
    attempt.refresh_from_db()
    assert attempt.status == "applied"


def test_suspended_superuser_cannot_run_readback(request_record):
    import pytest
    from .contracts import ProvisioningError
    from .reconciliation import reconcile_attempt

    attempt = applied_attempt(request_record)
    actor = request_record.created_by
    actor.job_status = False
    actor.save()
    with patch(
        "apps.provisioning.reconciliation.read_instances"
    ) as read, pytest.raises(ProvisioningError, match="授权"):
        reconcile_attempt(attempt.pk)
    read.assert_not_called()
    attempt.refresh_from_db()
    assert "授权" in attempt.error_message


def test_readback_rechecks_suspension_after_cloud_call(request_record):
    import pytest
    from django.contrib.auth import get_user_model
    from .contracts import ProvisioningError
    from .reconciliation import reconcile_attempt

    attempt = applied_attempt(request_record)

    def suspend(*args):
        get_user_model().objects.filter(pk=attempt.actor_id).update(job_status=False)
        return [observed()]

    with patch("apps.provisioning.reconciliation.ArtifactStore") as store, patch(
        "apps.provisioning.reconciliation.read_instances", side_effect=suspend
    ), pytest.raises(ProvisioningError, match="授权"):
        store.return_value.get.return_value = {"files": files()}
        reconcile_attempt(attempt.pk)
    assert not AssetHost.objects.filter(source_id="i-review").exists()
