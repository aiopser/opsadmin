from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from .contracts import ProvisioningError
from .models import ProvisioningAttempt, ProvisioningRequest
from .test_contract import request_record, ready_plan
from .test_state_protection import protected_attempt, state_files


@pytest.fixture
def uncertain(protected_attempt):
    from .state_protection import capture_state

    attempt = protected_attempt
    attempt.status = "needs_reconciliation"
    attempt.apply_started_at = timezone.now() - timedelta(hours=1)
    attempt.save()
    record = attempt.plan.request
    record.execution_status = "needs_reconciliation"
    record.save()
    version = capture_state(attempt.pk, state_files())
    reviewer = get_user_model().objects.create_superuser(username="resolution-reviewer")
    return record, attempt, version, reviewer


def cloud_asset(**overrides):
    return {
        "source_id": "i-one",
        "hostname": "created",
        "internal_ip": "10.8.8.8",
        "os_family": "windows",
        "cloud_state": "running",
        **overrides,
    }


def test_verified_manual_resolution_closes_unknown_and_never_applies(
    uncertain, settings
):
    from .manual_resolution import preview_resolution, confirm_resolution
    from .services import execute_plan, queue_plan
    from apps.cmdb.models import AssetHost

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ), patch("apps.provisioning.tasks.TerraformRunner") as runner:
        preview = preview_resolution(record.pk, reviewer, version.pk)
        resolved = confirm_resolution(
            preview.pk,
            reviewer,
            preview.digest,
            "INC-20261023-001",
            "已核实云控制台、请求数量与 state 一致",
        )
        with pytest.raises(ProvisioningError):
            confirm_resolution(
                preview.pk, reviewer, preview.digest, "INC-001", "重复确认不得结案"
            )
    runner.assert_not_called()
    record.refresh_from_db()
    attempt.refresh_from_db()
    assert record.execution_status == "success" and record.inventory_status == "success"
    assert record.active_state_version_id == version.pk and record.state_generation == 1
    assert attempt.status == "reconciled" and attempt.instance_ids == ["i-one"]
    assert AssetHost.objects.get(pk=attempt.asset_ids[0]).connection_type == "winrm"
    resolved.refresh_from_db()
    assert (
        resolved.status == "consumed"
        and resolved.evidence_reference == "INC-20261023-001"
    )
    event = record.events.get(kind="manually_reconciled")
    assert event.actor_id == reviewer.pk
    from apps.audit_center.models import DomainAuditEvent

    audit = DomainAuditEvent.objects.get(action="provisioning.manually_reconciled")
    assert audit.after["evidence"]["stateDigest"] == version.digest
    assert "must-stay-private" not in str(audit.after)
    settings.PROVISIONING_ENABLED = True
    with patch("apps.provisioning.tasks.apply_plan.apply_async") as dispatch:
        assert (
            execute_plan(
                record.pk,
                record.created_by,
                attempt.plan_id,
                attempt.plan.digest,
                attempt.idempotency_key,
            ).pk
            == attempt.pk
        )
        with pytest.raises(ProvisioningError):
            queue_plan(record.pk, record.created_by)
    dispatch.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    [
        "self_review",
        "permission",
        "live_writer",
        "missing_cloud",
        "wrong_count",
        "degraded",
        "old_state",
        "corrupt_backup",
        "no_apply_marker",
    ],
)
def test_manual_preview_refuses_unverified_outcomes(uncertain, failure):
    from .manual_resolution import preview_resolution
    from .state_protection import capture_state
    from .terraform import ArtifactStore

    record, attempt, version, reviewer = uncertain
    assets = [cloud_asset()]
    if failure == "self_review":
        reviewer = record.created_by
    if failure == "live_writer":
        attempt.lease_expires_at = timezone.now() + timedelta(minutes=5)
        attempt.save()
    if failure == "no_apply_marker":
        attempt.apply_started_at = None
        attempt.save()
    if failure == "missing_cloud":
        assets = []
    if failure == "wrong_count":
        record.parameters = {"count": 2}
        record.save()
    if failure == "degraded":
        version.protection_status = "degraded"
        version.save()
    if failure == "old_state":
        capture_state(attempt.pk, state_files(serial=2))
    if failure == "corrupt_backup":
        (ArtifactStore(backup=True).root / version.backup_artifact.key).write_bytes(
            b"corrupt"
        )
    with patch(
        "apps.provisioning.manual_resolution.read_instances", return_value=assets
    ), patch(
        "apps.provisioning.manual_resolution.verify_permission",
        return_value=(failure != "permission", ""),
    ), pytest.raises(
        ProvisioningError
    ):
        preview_resolution(record.pk, reviewer, version.pk)
    record.refresh_from_db()
    assert record.execution_status == "needs_reconciliation"


@pytest.mark.parametrize(
    "failure",
    [
        "source_changed",
        "new_state",
        "other_actor",
        "revoked",
        "expired",
        "cloud_changed",
        "no_evidence",
        "digest",
        "request_changed",
    ],
)
def test_manual_confirm_revalidates_frozen_evidence(uncertain, failure):
    from .manual_resolution import preview_resolution, confirm_resolution
    from .state_protection import capture_state

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer, version.pk)
    if failure == "source_changed":
        source = record.credential.source
        source.name = "changed"
        source.save()
    if failure == "new_state":
        capture_state(attempt.pk, state_files(serial=2))
    if failure == "other_actor":
        reviewer = get_user_model().objects.create_superuser(
            username="another-reviewer"
        )
    if failure == "expired":
        type(preview).objects.filter(pk=preview.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
    if failure == "request_changed":
        ProvisioningRequest.objects.filter(pk=record.pk).update(state_generation=1)
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset(internal_ip="10.8.8.9")]
        if failure == "cloud_changed"
        else [cloud_asset()],
    ), patch(
        "apps.provisioning.manual_resolution.verify_permission",
        return_value=(failure != "revoked", ""),
    ), pytest.raises(
        ProvisioningError
    ):
        confirm_resolution(
            preview.pk,
            reviewer,
            "x" * 64 if failure == "digest" else preview.digest,
            "" if failure == "no_evidence" else "INC-001",
            "人工核实记录",
        )
    record.refresh_from_db()
    assert record.execution_status == "needs_reconciliation"


def test_resolution_api_requires_review_permission_even_for_owner(uncertain):
    record, attempt, version, reviewer = uncertain
    owner = record.created_by
    owner.is_superuser = False
    owner.save()
    client = APIClient()
    client.force_authenticate(owner)
    with patch(
        "apps.provisioning.manual_resolution.verify_permission",
        return_value=(False, ""),
    ):
        response = client.post(
            f"/api/v1/provisioning/requests/{record.pk}/resolution-preview",
            {"stateVersionId": version.pk},
            format="json",
        )
    assert response.status_code == 403


def test_resolution_api_returns_safe_evidence_and_confirms(uncertain):
    record, attempt, version, reviewer = uncertain
    client = APIClient()
    client.force_authenticate(reviewer)
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        response = client.post(
            f"/api/v1/provisioning/requests/{record.pk}/resolution-preview",
            {"stateVersionId": version.pk},
            format="json",
        )
        assert response.status_code == 200
        data = response.data["data"]
        assert data["instanceIds"] == ["i-one"] and "must-stay-private" not in str(data)
        response = client.post(
            f"/api/v1/provisioning/requests/{record.pk}/resolution-confirm",
            {
                "previewId": data["previewId"],
                "digest": data["digest"],
                "evidenceReference": "INC-001",
                "comment": "核实云端与 state 一致",
            },
            format="json",
        )
    assert response.status_code == 200
    record.refresh_from_db()
    assert record.execution_status == "success"


def test_manual_preview_protects_internal_recovery_archive(protected_attempt):
    from .manual_resolution import preview_resolution, confirm_resolution
    from .terraform import ArtifactStore

    attempt = protected_attempt
    attempt.status = "needs_reconciliation"
    attempt.apply_started_at = timezone.now() - timedelta(hours=1)
    attempt.recovery_artifact_key = ArtifactStore().put({"files": state_files()})
    attempt.save()
    record = attempt.plan.request
    record.execution_status = "needs_reconciliation"
    record.save()
    reviewer = get_user_model().objects.create_superuser(username="archive-reviewer")
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer)
        assert preview.state_version.protection_status == "protected"
        confirm_resolution(
            preview.pk, reviewer, preview.digest, "INC-archive", "归档保护和云资源已核实"
        )
    record.refresh_from_db()
    assert record.active_state_version_id == preview.state_version_id


def test_manual_resolution_fences_reader_already_in_cloud_call(uncertain):
    from .manual_resolution import preview_resolution, confirm_resolution
    from .reconciliation import reconcile_attempt

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer, version.pk)

        def finish_manually(*args):
            confirm_resolution(
                preview.pk, reviewer, preview.digest, "INC-race", "已核实中断执行创建成功"
            )
            raise RuntimeError("old reader returned too late")

        with patch(
            "apps.provisioning.reconciliation.read_instances",
            side_effect=finish_manually,
        ), patch.object(reconcile_attempt, "retry") as retry:
            reconcile_attempt(attempt.pk)
    retry.assert_not_called()
    record.refresh_from_db()
    attempt.refresh_from_db()
    assert record.inventory_status == "success" and record.execution_status == "success"
    assert attempt.status == "reconciled" and attempt.error_message == ""


def test_second_resolution_preview_cannot_close_again(uncertain):
    from .manual_resolution import preview_resolution, confirm_resolution

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        first = preview_resolution(record.pk, reviewer, version.pk)
        second = preview_resolution(record.pk, reviewer, version.pk)
        confirm_resolution(second.pk, reviewer, second.digest, "INC-one", "已核实中断执行结果")
        with pytest.raises(ProvisioningError):
            confirm_resolution(first.pk, reviewer, first.digest, "INC-two", "不得再次结案")
    assert record.events.filter(kind="manually_reconciled").count() == 1


@pytest.mark.parametrize("disabled_field", ["is_active", "job_status"])
def test_manual_confirmation_rechecks_actor_after_cloud_read(uncertain, disabled_field):
    from .manual_resolution import preview_resolution, confirm_resolution

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer, version.pk)

    def deactivate(*args):
        get_user_model().objects.filter(pk=reviewer.pk).update(
            **{disabled_field: False}
        )
        return [cloud_asset()]

    with patch(
        "apps.provisioning.manual_resolution.read_instances", side_effect=deactivate
    ), pytest.raises(ProvisioningError):
        confirm_resolution(
            preview.pk, reviewer, preview.digest, "INC-revoked", "云端读取期间停用复核人"
        )
    record.refresh_from_db()
    assert record.execution_status == "needs_reconciliation"


def test_manual_api_masks_unexpected_cloud_failure(uncertain):
    record, attempt, version, reviewer = uncertain
    client = APIClient()
    client.force_authenticate(reviewer)
    client.raise_request_exception = False
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        side_effect=RuntimeError("write-secret-canary"),
    ):
        response = client.post(
            f"/api/v1/provisioning/requests/{record.pk}/resolution-preview",
            {"stateVersionId": version.pk},
            format="json",
        )
    assert response.status_code == 400
    assert "write-secret-canary" not in str(response.data)


def test_manual_confirmation_rejects_a_newer_inventory_observation(uncertain):
    from .manual_resolution import preview_resolution, confirm_resolution
    from apps.cmdb.models import AssetHost

    record, attempt, version, reviewer = uncertain
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer, version.pk)

    def observed_elsewhere(*args):
        AssetHost.objects.create(
            asset_source=record.credential.source,
            source_id="i-one",
            source_type="cloud",
            hostname="deleted",
            internal_ip="10.8.8.8",
            cloud_state="deleted",
            last_observed_at=timezone.now() + timedelta(seconds=1),
        )
        return [cloud_asset()]

    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        side_effect=observed_elsewhere,
    ), pytest.raises(ProvisioningError):
        confirm_resolution(
            preview.pk, reviewer, preview.digest, "INC-newer", "回读后又有新的云端观测"
        )
    record.refresh_from_db()
    assert record.execution_status == "needs_reconciliation"


def test_manual_preview_repairs_latest_degraded_state_after_backup_recovers(
    protected_attempt,
):
    from .manual_resolution import preview_resolution
    from .state_protection import capture_state

    attempt = protected_attempt
    attempt.status = "needs_reconciliation"
    attempt.apply_started_at = timezone.now() - timedelta(hours=1)
    attempt.save()
    record = attempt.plan.request
    record.execution_status = "needs_reconciliation"
    record.save()
    with patch(
        "apps.provisioning.state_protection.write_backup",
        side_effect=OSError("unavailable"),
    ):
        degraded = capture_state(attempt.pk, state_files())
    reviewer = get_user_model().objects.create_superuser(username="backup-reviewer")
    with patch(
        "apps.provisioning.manual_resolution.read_instances",
        return_value=[cloud_asset()],
    ):
        preview = preview_resolution(record.pk, reviewer)
    assert preview.state_version.protection_status == "protected"
    assert preview.state_version.version > degraded.version
    record.refresh_from_db()
    assert (
        record.execution_status == "needs_reconciliation"
        and record.active_state_version_id is None
    )
