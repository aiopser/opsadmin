import base64
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from .contracts import ProvisioningError
from .test_contract import request_record, ready_plan


@pytest.fixture
def protected_attempt(request_record, settings, tmp_path):
    from .models import ProvisioningAttempt

    settings.PROVISIONING_ARTIFACT_ROOT = str(tmp_path / "primary")
    settings.PROVISIONING_BACKUP_ROOT = str(tmp_path / "backup")
    settings.PROVISIONING_STATE_KEYS = {"v1": Fernet.generate_key().decode()}
    settings.PROVISIONING_STATE_ACTIVE_KEY_ID = "v1"
    request_record.execution_status = "success"
    request_record.save()
    return ProvisioningAttempt.objects.create(
        plan=ready_plan(request_record),
        actor=request_record.created_by,
        idempotency_key="protected",
        status="applied",
    )


def state_files(serial=1, lineage="delivery-lineage"):
    state = {
        "version": 4,
        "lineage": lineage,
        "serial": serial,
        "resources": [
            {
                "mode": "managed",
                "type": "alicloud_instance",
                "instances": [
                    {"attributes": {"id": "i-one", "password": "must-stay-private"}}
                ],
            }
        ],
    }
    return {"terraform.tfstate": base64.b64encode(json.dumps(state).encode()).decode()}


def test_key_rotation_preserves_old_versions(settings):
    from .state_crypto import StateKeyring

    settings.PROVISIONING_STATE_KEYS = {
        "v1": Fernet.generate_key().decode(),
        "v2": Fernet.generate_key().decode(),
    }
    settings.PROVISIONING_STATE_ACTIVE_KEY_ID = "v1"
    envelope = StateKeyring().encrypt({"private": "value"})
    settings.PROVISIONING_STATE_ACTIVE_KEY_ID = "v2"
    assert StateKeyring().decrypt(envelope) == {"private": "value"}
    settings.PROVISIONING_STATE_KEYS = {"v2": settings.PROVISIONING_STATE_KEYS["v2"]}
    with pytest.raises(ProvisioningError, match="密钥"):
        StateKeyring().decrypt(envelope)


def test_capture_is_backed_up_and_idempotent(protected_attempt):
    from .state_protection import capture_state, read_state_files

    version = capture_state(protected_attempt.pk, state_files())
    again = capture_state(protected_attempt.pk, state_files())
    assert version.pk == again.pk
    assert version.protection_status == "protected"
    assert read_state_files(version, backup=True) == state_files()


def test_backup_failure_does_not_erase_success(protected_attempt):
    from .state_protection import capture_state

    with patch(
        "apps.provisioning.state_protection.write_backup",
        side_effect=OSError("unavailable"),
    ):
        version = capture_state(protected_attempt.pk, state_files())
    assert version.protection_status == "degraded"
    protected_attempt.plan.request.refresh_from_db()
    assert protected_attempt.plan.request.execution_status == "success"


def test_backups_cannot_be_under_primary(protected_attempt, settings):
    from .state_protection import check_protection_storage

    settings.PROVISIONING_BACKUP_ROOT = settings.PROVISIONING_ARTIFACT_ROOT + "/nested"
    with pytest.raises(ProvisioningError):
        check_protection_storage()


def test_restore_uses_backup_and_never_applies(protected_attempt):
    from .state_protection import capture_state
    from .state_restore import preview_restore, confirm_restore

    version = capture_state(protected_attempt.pk, state_files())
    actor = protected_attempt.actor
    preview = preview_restore(protected_attempt.plan.request_id, actor, version.pk)
    with patch("apps.provisioning.reconciliation.reconcile_attempt.apply_async"), patch(
        "apps.provisioning.tasks.TerraformRunner"
    ) as runner:
        restored = confirm_restore(preview.pk, actor, preview.digest)
    assert restored.digest == version.digest
    assert restored.version == version.version + 1
    runner.assert_not_called()
    with pytest.raises(ProvisioningError):
        confirm_restore(preview.pk, actor, preview.digest)


def test_restore_rejects_old_serial(protected_attempt):
    from .state_protection import capture_state
    from .state_restore import preview_restore

    first = capture_state(protected_attempt.pk, state_files(1))
    capture_state(protected_attempt.pk, state_files(2))
    with pytest.raises(ProvisioningError, match="版本"):
        preview_restore(
            protected_attempt.plan.request_id, protected_attempt.actor, first.pk
        )


def test_retention_keeps_active_state(protected_attempt):
    from .state_protection import capture_state
    from .retention import retention_candidates

    version = capture_state(protected_attempt.pk, state_files())
    assert (
        not retention_candidates(timezone.now() + timedelta(days=400))
        .filter(pk=version.primary_artifact_id)
        .exists()
    )


def test_stale_worker_is_not_healthy(db):
    from .worker_health import record_worker_heartbeat, health_snapshot
    from .models import ProvisioningWorker

    record_worker_heartbeat(
        "test-worker", "epoch-1", ["provisioning"], {"runtime": True}
    )
    assert health_snapshot()["workers"][0]["online"] is True
    ProvisioningWorker.objects.update(
        last_seen_at=timezone.now() - timedelta(seconds=91)
    )
    assert health_snapshot()["workers"][0]["online"] is False


def test_write_rejects_corrupt_backup(protected_attempt):
    from .state_protection import capture_state, assert_write_protected
    from .terraform import ArtifactStore

    version = capture_state(protected_attempt.pk, state_files())
    (ArtifactStore(backup=True).root / version.backup_artifact.key).write_bytes(
        b"corrupt"
    )
    record = protected_attempt.plan.request
    record.refresh_from_db()
    with pytest.raises(ProvisioningError):
        assert_write_protected(record)


def test_restore_rejects_inconsistent_running_attempt(protected_attempt):
    from .state_protection import capture_state
    from .state_restore import preview_restore

    version = capture_state(protected_attempt.pk, state_files())
    protected_attempt.status = "running"
    protected_attempt.save()
    with pytest.raises(ProvisioningError, match="写任务"):
        preview_restore(
            protected_attempt.plan.request_id, protected_attempt.actor, version.pk
        )


def test_invalid_lease_never_starts_process(tmp_path):
    from .terraform import TerraformRunner

    runner = object.__new__(TerraformRunner)
    runner.binary = "/opt/terraform"
    runner.workspace = tmp_path
    runner.environment = {}
    runner.on_tick = lambda: False
    with patch("apps.provisioning.terraform.os.name", "posix"), patch(
        "apps.provisioning.terraform.subprocess.Popen"
    ) as process:
        with pytest.raises(ProvisioningError, match="租约"):
            runner._managed_command(["apply"], 30)
        process.assert_not_called()


def test_expired_plan_is_collectable_after_creation(protected_attempt):
    from .models import ProvisioningArtifact
    from .retention import retention_candidates

    artifact = ProvisioningArtifact.objects.create(
        request=protected_attempt.plan.request,
        purpose="plan",
        key="a" * 32,
        digest="a" * 64,
        expires_at=timezone.now() - timedelta(days=1),
    )
    assert retention_candidates(timezone.now()).filter(pk=artifact.pk).exists()


def test_state_api_exposes_metadata_only(protected_attempt):
    from rest_framework.test import APIClient
    from .state_protection import capture_state

    version = capture_state(protected_attempt.pk, state_files())
    client = APIClient()
    client.force_authenticate(protected_attempt.actor)
    base = f"/api/v1/provisioning/requests/{protected_attempt.plan.request_id}"
    response = client.get(base + "/state-versions")
    assert response.status_code == 200
    assert response.data["data"][0]["id"] == version.pk
    assert "must-stay-private" not in str(response.data)
    assert version.primary_artifact.key not in str(response.data)
    invalid = client.post(
        base + "/restore-confirm",
        {"previewId": "invalid", "digest": "bad"},
        format="json",
    )
    assert invalid.status_code == 400


def test_monitor_does_not_alarm_when_feature_disabled(db, settings):
    from .worker_health import monitor_provisioning
    from .models import ProvisioningHealthIncident

    settings.PROVISIONING_ENABLED = False
    monitor_provisioning()
    assert not ProvisioningHealthIncident.objects.filter(
        kind="worker_unavailable", status="open"
    ).exists()


def test_monitor_fences_expired_apply_without_requeue(protected_attempt, settings):
    from .worker_health import monitor_provisioning

    settings.PROVISIONING_MONITOR_NOTIFICATION_TEMPLATE_ID = None
    protected_attempt.status = "running"
    protected_attempt.execution_token = "expired"
    protected_attempt.lease_expires_at = timezone.now() - timedelta(seconds=1)
    protected_attempt.save()
    with patch("apps.provisioning.tasks.apply_plan.apply_async") as dispatch:
        monitor_provisioning()
        monitor_provisioning()
        dispatch.assert_not_called()
    protected_attempt.refresh_from_db()
    assert protected_attempt.status == "needs_reconciliation"


def test_expired_unexecuted_plan_does_not_hold_artifacts(request_record):
    from .models import ProvisioningArtifact
    from .retention import retention_candidates

    plan = ready_plan(request_record)
    plan.expires_at = timezone.now() - timedelta(days=31)
    plan.save()
    artifact = ProvisioningArtifact.objects.create(
        request=request_record,
        purpose="plan",
        key="a" * 32,
        digest="a" * 64,
        expires_at=timezone.now() - timedelta(days=1),
    )
    assert retention_candidates(timezone.now()).filter(pk=artifact.pk).exists()


def test_restore_repairs_missing_primary_from_backup(protected_attempt):
    from .state_protection import capture_state, read_state_files
    from .state_restore import preview_restore, confirm_restore
    from .terraform import ArtifactStore

    version = capture_state(protected_attempt.pk, state_files())
    (ArtifactStore().root / version.primary_artifact.key).unlink()
    from .worker_health import monitor_provisioning

    monitor_provisioning()
    version.refresh_from_db()
    assert version.protection_status == "degraded"
    preview = preview_restore(
        protected_attempt.plan.request_id, protected_attempt.actor, version.pk
    )
    with patch("apps.provisioning.reconciliation.reconcile_attempt.apply_async"):
        restored = confirm_restore(preview.pk, protected_attempt.actor, preview.digest)
    assert restored.version == version.version + 1
    assert read_state_files(restored) == state_files()


@pytest.mark.parametrize(
    "copy,damage", [("main", "missing"), ("backup", "missing"), ("backup", "corrupt")]
)
def test_monitor_checks_actual_state_files(protected_attempt, settings, copy, damage):
    from .state_protection import capture_state, protection_summary
    from .worker_health import monitor_provisioning
    from .models import ProvisioningHealthIncident
    from .terraform import ArtifactStore

    settings.PROVISIONING_MONITOR_NOTIFICATION_TEMPLATE_ID = None
    version = capture_state(protected_attempt.pk, state_files())
    artifact = version.primary_artifact if copy == "main" else version.backup_artifact
    path = ArtifactStore(backup=copy == "backup").root / artifact.key
    original = path.read_bytes()
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"corrupt")
    monitor_provisioning()
    record = protected_attempt.plan.request
    record.refresh_from_db()
    assert protection_summary(record)["status"] == "degraded"
    assert ProvisioningHealthIncident.objects.filter(
        kind="state_backup", status="open"
    ).exists()
    path.write_bytes(original)
    monitor_provisioning()
    record.refresh_from_db()
    assert protection_summary(record)["status"] == "protected"
    assert not ProvisioningHealthIncident.objects.filter(
        kind="state_backup", status="open"
    ).exists()
