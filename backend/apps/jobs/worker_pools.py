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


def region_for_targets(targets) -> str:
    """目标主机的地域路由值：目标中恰好存在一个非空地域时返回该地域，否则返回空串。

    空串表示不做地域路由（回退默认池）。忽略无地域（如存量数据）的目标，
    只要其余目标同属一个地域就按其就近路由，可达性由网关层独立保障。
    """
    regions = {str(target.get("region") or "").strip() for target in targets or []}
    regions.discard("")
    if len(regions) == 1:
        return regions.pop()
    return ""


def _pool_for_region(*, actor, queryset, target_region, execution_kind):
    """按目标地域就近选择 worker 池。

    候选必须激活、支持该执行类型且当前用户有权访问，按 code 稳定排序取第一个；
    无匹配（该地域无可用池/不支持该类型/无权限）时返回 None，由调用方回退默认池。
    """
    if not target_region:
        return None
    candidates = queryset.filter(region=target_region).order_by("code", "pk")
    for candidate in candidates:
        if execution_kind not in candidate.execution_kinds:
            continue
        if verify_permission(actor, f"/api/v1/jobs/worker-pools/{candidate.pk}", "GET")[0]:
            return candidate
    return None


def resolve_worker_pool(*, actor, pool_id, execution_kind, target_region="") -> WorkerPool:
    queryset = WorkerPool.objects.filter(is_active=True)
    if pool_id is not None:
        # 显式指定优先，不做地域自动路由。
        pool = queryset.filter(pk=pool_id).first()
    else:
        pool = _pool_for_region(
            actor=actor,
            queryset=queryset,
            target_region=str(target_region or "").strip(),
            execution_kind=execution_kind,
        ) or queryset.filter(is_default=True).first()
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
