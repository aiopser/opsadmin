from unittest.mock import patch
from datetime import timedelta
import pytest

from django.contrib.auth import get_user_model
from django.utils import timezone

from .contracts import canonical_digest
from .models import ProvisioningApproval, ProvisioningAttempt
from .test_contract import request_record, ready_plan


def test_long_queue_wait_does_not_retire_just_started_worker(request_record):
    from .tasks import recover_stale

    attempt = ProvisioningAttempt.objects.create(
        plan=ready_plan(request_record),
        actor=request_record.created_by,
        idempotency_key="recent-start",
        status="running",
        started_at=timezone.now(),
    )
    ProvisioningAttempt.objects.filter(pk=attempt.pk).update(
        created_at=timezone.now() - timedelta(minutes=50)
    )
    recover_stale()
    attempt.refresh_from_db()
    assert attempt.status == "running"


@pytest.mark.parametrize(
    "scenario",
    [
        "queue_unavailable",
        "archive_unavailable",
        "fenced_success",
        "credential_changed_during_init",
    ],
)
def test_readback_dispatch_failure_keeps_creation_success(
    request_record, settings, tmp_path, scenario
):
    from .tasks import apply_plan

    settings.PROVISIONING_ENABLED = True
    record = request_record
    record.approval_status = "approved"
    record.execution_status = "queued"
    record.save()
    plan = ready_plan(record)
    saved = {"files": {}, "terraform": "1.9.8"}
    plan.digest = canonical_digest(
        {
            "files": {},
            "inputs": plan.input_digest,
            "credential_revision": 1,
            "terraform": "1.9.8",
        }
    )
    saved["digest"] = plan.digest
    plan.confirmed_by = record.created_by
    plan.save()
    approver = get_user_model().objects.create_superuser(username="worker-reviewer")
    ProvisioningApproval.objects.create(
        plan=plan, actor=approver, digest=plan.digest, decision="approved"
    )
    attempt = ProvisioningAttempt.objects.create(
        plan=plan, actor=record.created_by, idempotency_key="worker-once"
    )
    working = tmp_path / "working"
    working.mkdir()
    with patch("apps.provisioning.tasks.ArtifactStore") as store, patch(
        "apps.provisioning.tasks.TerraformRunner"
    ) as runner, patch(
        "apps.provisioning.tasks.credential_environment", return_value={}
    ), patch(
        "apps.provisioning.reconciliation.reconcile_attempt.apply_async",
        side_effect=RuntimeError("queue unavailable"),
    ):
        store.return_value.working_root = working
        store.return_value.get.return_value = saved
        store.return_value.put.return_value = "recovery-key"
        if scenario == "archive_unavailable":
            store.return_value.put.side_effect = OSError("storage unavailable")
        if scenario == "fenced_success":

            def completed_elsewhere():
                ProvisioningAttempt.objects.filter(pk=attempt.pk).update(
                    status="reconciled", execution_token="different-owner"
                )
                type(record).objects.filter(pk=record.pk).update(
                    execution_status="success", inventory_status="failed"
                )
                raise RuntimeError("old worker returned after reconciliation")

            runner.return_value.apply.side_effect = completed_elsewhere
        runner.return_value.version = "1.9.8"
        if scenario == "credential_changed_during_init":

            def change_credential():
                type(record.credential).objects.filter(pk=record.credential_id).update(
                    revision=2
                )

            runner.return_value.initialize.side_effect = change_credential
        apply_plan(attempt.pk)
        apply_plan(attempt.pk)
        if scenario == "credential_changed_during_init":
            runner.return_value.apply.assert_not_called()
        else:
            runner.return_value.apply.assert_called_once()
    record.refresh_from_db()
    if scenario == "credential_changed_during_init":
        assert record.execution_status == "failed"
        return
    assert record.execution_status == "success"
    assert record.inventory_status == "failed"
