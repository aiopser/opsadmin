"""Worker-executed CMDB probes; Web processes never run Ansible directly.

A probe is scheduled on the WorkerPool routed for the host region so the
network path matches real executions. The AssetProbe row doubles as the
durable dispatch record: PENDING rows that were never claimed are
republished by the recovery scanner, and RUNNING rows whose worker died
are failed after the staleness window (a ping/setup probe has no remote
side effects, so failing is safe).
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.jobs.worker_pools import (
    queue_for_pool,
    region_for_targets,
    resolve_worker_pool,
)

from .models import AssetProbe

PUBLISH_RETRY_AFTER_SECONDS = 30
RUNNING_STALE_SECONDS = 120
RECOVER_BATCH_SIZE = 50


def probe_module_for(kind, connection_type):
    """Return (module, module_args) for the requested probe kind."""
    if kind == AssetProbe.Kind.FACTS:
        module = (
            "ansible.windows.setup"
            if connection_type == "winrm"
            else "ansible.builtin.setup"
        )
        return module, "gather_subset=!all,!min,hardware,network"
    module = (
        "ansible.windows.win_ping"
        if connection_type == "winrm"
        else "ansible.builtin.ping"
    )
    return module, ""


def schedule_asset_probe(
    *, actor, host_id, kind=AssetProbe.Kind.CONNECT, timeout=15
) -> AssetProbe:
    """Validate access, route to a worker pool, and persist the probe.

    Raises PermissionDenied/ValidationError when the actor may not touch the
    host or no active worker pool supports module execution for its region;
    those errors surface to the API caller before any queueing happens.
    """
    from .targets import resolve_targets

    targets = resolve_targets(actor=actor, host_ids=[host_id], group_ids=[])
    module, module_args = probe_module_for(kind, targets[0]["connection_type"])
    pool = resolve_worker_pool(
        actor=actor,
        pool_id=None,
        execution_kind="module",
        target_region=region_for_targets(targets),
    )
    probe = AssetProbe.objects.create(
        host_id=host_id,
        triggered_by=actor,
        kind=kind,
        module=module,
        module_args=module_args,
        timeout_seconds=timeout,
        worker_pool=pool,
    )
    transaction.on_commit(lambda: publish_asset_probe(probe.id, probe.attempt))
    return probe


def publish_asset_probe(probe_id, attempt) -> bool:
    """Publish the probe task to its worker pool queue once.

    Returns False when the row is not in the expected pending state or the
    broker rejected publication; the recovery scanner will retry either way.
    """
    from .tasks import execute_asset_probe

    probe = AssetProbe.objects.select_related("worker_pool").get(pk=probe_id)
    if probe.status != AssetProbe.Status.PENDING or probe.attempt != attempt:
        return False
    try:
        queue = queue_for_pool(probe.worker_pool)
        execute_asset_probe.apply_async(
            args=[probe.id, probe.attempt],
            queue=queue,
            soft_time_limit=probe.timeout_seconds + 5,
            time_limit=probe.timeout_seconds + 10,
        )
    except Exception:
        # Row stays PENDING; the recovery scanner republishes it.
        return False
    return True


def recover_stale_probes(now=None) -> int:
    """Republish lost PENDING probes and fail dead RUNNING ones."""
    now = now or timezone.now()
    recovered = 0
    pending = AssetProbe.objects.filter(
        status=AssetProbe.Status.PENDING,
        updated_at__lt=now - timedelta(seconds=PUBLISH_RETRY_AFTER_SECONDS),
    ).order_by("id")[:RECOVER_BATCH_SIZE]
    for probe in pending:
        if publish_asset_probe(probe.id, probe.attempt):
            recovered += 1
    stale_running = AssetProbe.objects.filter(
        status=AssetProbe.Status.RUNNING,
        updated_at__lt=now - timedelta(seconds=RUNNING_STALE_SECONDS),
    ).order_by("id")[:RECOVER_BATCH_SIZE]
    for probe in stale_running:
        recovered += AssetProbe.objects.filter(
            pk=probe.pk,
            status=AssetProbe.Status.RUNNING,
        ).update(
            status=AssetProbe.Status.FAILED,
            error="probe lost: worker did not report back",
            updated_at=now,
        )
    return recovered
