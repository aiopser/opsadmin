import re

from rest_framework.exceptions import PermissionDenied, ValidationError

from common.auth.rbac import verify_permission
from .models import WorkerPool


def queue_for_pool(pool: WorkerPool) -> str:
    if not pool.is_active:
        raise ValidationError("Worker pool is disabled")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", pool.queue_name):
        raise ValidationError("Invalid worker queue")
    return pool.queue_name


def resolve_worker_pool(*, actor, pool_id, execution_kind) -> WorkerPool:
    queryset = WorkerPool.objects.filter(is_active=True)
    pool = queryset.filter(pk=pool_id).first() if pool_id is not None else queryset.filter(is_default=True).first()
    if pool is None:
        raise ValidationError("Worker pool is missing or disabled")
    if not getattr(actor, "is_authenticated", False) or not actor.is_active or not getattr(actor, "job_status", True):
        raise PermissionDenied("Active actor required")
    if not verify_permission(actor, f"/api/v1/jobs/worker-pools/{pool.pk}", "GET")[0]:
        raise PermissionDenied("Worker pool access denied")
    if execution_kind not in pool.execution_kinds:
        raise ValidationError("Worker pool does not support this execution kind")
    queue_for_pool(pool)
    return pool
