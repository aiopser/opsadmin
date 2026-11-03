from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .contracts import ProvisioningError
from .models import ProvisioningArtifact, ProvisioningRequest, ProvisioningPlan
from .services import event
from .terraform import ArtifactStore


def retention_candidates(now):
    # Until lifecycle destruction is independently verified, no state is eligible.
    pending_requests = ProvisioningPlan.objects.filter(
        Q(status__in=["queued", "running"])
        | Q(status="ready", attempt__isnull=True, expires_at__gt=now)
    ).values("request_id")
    return (
        ProvisioningArtifact.objects.filter(
            purpose__in=["plan", "diagnostic"],
            held=False,
            cleanup_status="retained",
            expires_at__lte=now,
        )
        .exclude(
            request__execution_status__in=["queued", "running", "needs_reconciliation"]
        )
        .exclude(request_id__in=pending_requests)
    )


@transaction.atomic
def purge_artifact(artifact_id, actor):
    artifact = ProvisioningArtifact.objects.select_related("request").get(
        pk=artifact_id
    )
    record = ProvisioningRequest.objects.select_for_update().get(pk=artifact.request_id)
    artifact = (
        retention_candidates(timezone.now())
        .select_for_update()
        .filter(pk=artifact_id)
        .first()
    )
    if artifact is None:
        return False
    store = ArtifactStore(backup=artifact.storage == "backup")
    if len(artifact.key) != 32 or any(
        c not in "0123456789abcdef" for c in artifact.key
    ):
        raise ProvisioningError("无效的制品索引")
    path = store.root / artifact.key
    if path.is_symlink() or path.resolve().parent != store.root.resolve():
        raise ProvisioningError("制品路径不属于私有目录")
    artifact.cleanup_status = "deleting"
    artifact.save(update_fields=["cleanup_status", "updated_at"])
    path.unlink(missing_ok=True)
    artifact.cleanup_status = "deleted"
    artifact.save(update_fields=["cleanup_status", "updated_at"])
    event(record, actor, "artifact_deleted", f"已按保留策略清理制品索引 #{artifact.pk}")
    return True
