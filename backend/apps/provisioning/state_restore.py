from datetime import timedelta
import secrets

from django.db import transaction
from django.utils import timezone

from .contracts import ProvisioningError, canonical_digest
from .models import ProvisioningRequest, ProvisioningRestorePreview
from .services import authorize, event
from .state_protection import capture_state, read_state_files


def _validate(record, version):
    if version.request_id != record.pk or version.protection_status not in {
        "protected",
        "degraded",
    }:
        raise ProvisioningError("备份不属于此申请或尚未校验")
    if (
        record.execution_status in {"queued", "running", "needs_reconciliation"}
        or record.plans.filter(
            attempt__status__in=["queued", "running", "needs_reconciliation"]
        ).exists()
    ):
        raise ProvisioningError("存在未核实的写任务，禁止恢复")
    latest = record.state_versions.order_by("-serial", "-version").first()
    if latest and (version.serial < latest.serial or version.lineage != latest.lineage):
        raise ProvisioningError("备份版本落后或 lineage 不一致，需人工接管")


@transaction.atomic
def preview_restore(request_id, actor, state_version_id):
    authorize(actor, "restore-preview", request_id)
    record = (
        ProvisioningRequest.objects.select_for_update()
        .select_related("credential__source")
        .get(pk=request_id)
    )
    version = record.state_versions.get(pk=state_version_id)
    _validate(record, version)
    read_state_files(version, backup=True)
    digest = canonical_digest(
        {
            "state": version.digest,
            "generation": record.state_generation,
            "source": record.credential.source.updated_at.isoformat(),
            "actor": actor.pk,
        }
    )
    return ProvisioningRestorePreview.objects.create(
        request=record,
        state_version=version,
        actor=actor,
        generation=record.state_generation,
        source_updated_at=record.credential.source.updated_at,
        digest=digest,
        expires_at=timezone.now() + timedelta(minutes=15),
    )


@transaction.atomic
def confirm_restore(preview_id, actor, digest):
    preview = (
        ProvisioningRestorePreview.objects.select_for_update()
        .select_related("state_version__attempt")
        .get(pk=preview_id)
    )
    authorize(actor, "restore-confirm", preview.request_id)
    record = (
        ProvisioningRequest.objects.select_for_update()
        .select_related("credential__source")
        .get(pk=preview.request_id)
    )
    if (
        preview.actor_id != actor.pk
        or preview.status != "pending"
        or preview.expires_at <= timezone.now()
        or record.state_generation != preview.generation
        or record.credential.source.updated_at != preview.source_updated_at
        or not secrets.compare_digest(preview.digest, digest)
    ):
        raise ProvisioningError("恢复预览已失效，请重新校验")
    _validate(record, preview.state_version)
    files = read_state_files(preview.state_version, backup=True)
    # The selected state is re-copied and independently verified, never applied.
    restored = capture_state(
        preview.state_version.attempt_id, files, force_version=True
    )
    if restored.protection_status != "protected":
        raise ProvisioningError("恢复后的独立备份校验失败，请修复备份存储后重试")
    record.active_state_version = restored
    record.state_generation += 1
    record.save(
        update_fields=["active_state_version", "state_generation", "updated_at"]
    )
    record.plans.filter(status="ready").update(status="superseded", confirmed_by=None)
    preview.status = "consumed"
    preview.save(update_fields=["status", "updated_at"])
    event(
        record,
        actor,
        "state_restored",
        f"已将备份 v{preview.state_version.version} 恢复为控制版本 v{restored.version}，等待只读核实；未执行资源变更",
    )
    from .reconciliation import queue_reconciliation

    def enqueue():
        try:
            queue_reconciliation(restored.attempt_id, actor.pk, force=True)
        except ProvisioningError:
            # The shared dispatcher has already fenced any ambiguous delivery.
            pass

    transaction.on_commit(enqueue)
    return restored
