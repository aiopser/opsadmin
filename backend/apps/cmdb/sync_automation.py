"""Durable cloud synchronization scheduling and notification integration."""

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AssetSource, AssetSyncRecord

logger = logging.getLogger(__name__)


def queue_sync_failure_alert(record):
    if record.status not in {"failed", "partial"} or not record.failure_alert.get(
        "templateId"
    ):
        return
    from apps.automation.models import (
        NotificationChannel,
        NotificationRecord,
        NotificationTemplate,
    )
    from apps.jobs.alerts import _enqueue_alert

    template = NotificationTemplate.objects.filter(
        pk=record.failure_alert["templateId"]
    ).first()
    snapshot = {
        **record.failure_alert.get("templateSnapshot", {}),
        "receivers": record.failure_alert.get("receivers", ""),
    }
    from common.redaction import redact_text

    notification, created = NotificationRecord.objects.get_or_create(
        alert_key=f"cmdb-sync-failure:{record.pk}",
        defaults={
            "template": template,
            "channel": NotificationChannel.objects.filter(
                pk=snapshot.get("channelId")
            ).first(),
            "template_snapshot": snapshot,
            "context": {
                "title": f"资产同步{'部分失败' if record.status == 'partial' else '失败'}：{record.source.name}",
                "sync": {
                    "id": record.pk,
                    "sourceName": record.source.name,
                    "status": record.status,
                    "trigger": record.trigger,
                    "errorMessage": redact_text(record.error_message),
                },
            },
        },
    )
    if created:
        transaction.on_commit(lambda: _enqueue_alert(notification.pk))


def fail_sync(record, message):
    finished_at = timezone.now()
    changed = AssetSyncRecord.objects.filter(
        pk=record.pk, status__in=["queued", "running"]
    ).update(
        status="failed",
        finished_at=finished_at,
        error_message=message,
        updated_at=finished_at,
    )
    record.refresh_from_db()
    if changed:
        queue_sync_failure_alert(record)


def collection_scope(source, *, complete=True):
    return {
        "provider": source.cloud_provider,
        "regions": list(source.regions),
        "complete": complete,
        "sourceUpdatedAt": source.updated_at.isoformat(),
    }


def dispatch_sync(record_id):
    from .tasks import sync_asset_source

    try:
        task = sync_asset_source.apply_async(args=[record_id], queue="task")
        AssetSyncRecord.objects.filter(pk=record_id).update(
            task_id=getattr(task, "id", "") or ""
        )
    except Exception:
        logger.exception("Could not queue asset synchronization %s", record_id)
        record = AssetSyncRecord.objects.select_related("source").get(pk=record_id)
        if record.status == "queued":
            fail_sync(record, "同步任务投递失败，请检查 Worker 队列")


def create_sync_record(
    source, assets, *, trigger="manual", observed_at=None, scope=None
):
    from apps.automation.failure_alerts import freeze_failure_alert

    return AssetSyncRecord.objects.create(
        source=source,
        payload=assets,
        total_count=len(assets),
        trigger=trigger,
        observed_at=observed_at or timezone.now(),
        collection_scope=scope
        or collection_scope(source, complete=trigger != "scheduled"),
        failure_alert=freeze_failure_alert(source.sync_failure_alert) or {},
    )


def scheduled_sync_authorized(source):
    from common.auth.rbac import verify_permission

    current = AssetSource.objects.select_related("sync_actor").get(pk=source.pk)
    actor = current.sync_actor
    return bool(
        current.is_active
        and actor is not None
        and actor.is_active
        and actor.job_status
        and verify_permission(
            actor, f"/api/v1/cmdb/asset-sources/{source.pk}/sync-cloud", "POST"
        )[0]
    )


def collect_scheduled_inventory(record):
    from .cloud import collect_cloud_assets, CloudCollectionError

    source = record.source
    if not scheduled_sync_authorized(source):
        fail_sync(record, "周期同步授权已失效，请由具有同步权限的用户重新保存云账号")
        return False
    if source.updated_at.isoformat() != record.collection_scope.get("sourceUpdatedAt"):
        fail_sync(record, "云账号配置已变化，本次周期同步已取消")
        return False
    try:
        assets = collect_cloud_assets(source)
    except CloudCollectionError as exc:
        fail_sync(record, str(exc)[:2000])
        return False
    except Exception:
        fail_sync(record, "云资产读取失败，请检查账号权限、区域和网络")
        return False
    source.refresh_from_db()
    if not scheduled_sync_authorized(source):
        fail_sync(record, "周期同步授权已失效，未写入资产")
        return False
    if source.updated_at.isoformat() != record.collection_scope.get("sourceUpdatedAt"):
        fail_sync(record, "云账号配置已变化，本次周期同步已取消")
        return False
    # A periodic recovery may have fenced this worker while its API call was pending.
    record.payload = assets
    record.total_count = len(assets)
    record.observed_at = timezone.now()
    record.collection_scope = collection_scope(source)
    changed = AssetSyncRecord.objects.filter(pk=record.pk, status="running").update(
        payload=assets,
        total_count=len(assets),
        observed_at=record.observed_at,
        collection_scope=record.collection_scope,
        updated_at=timezone.now(),
    )
    if not changed:
        record.refresh_from_db()
    return bool(changed)


def queue_due_cloud_syncs(now=None):
    now = now or timezone.now()
    # Failed/abandoned executions stay visible; the next interval retries from a new observation.
    stale = AssetSyncRecord.objects.filter(
        status__in=["queued", "running"], updated_at__lt=now - timedelta(minutes=30)
    )
    for record in stale.select_related("source")[:100]:
        if AssetSyncRecord.objects.filter(
            pk=record.pk, status=record.status, updated_at=record.updated_at
        ).update(
            status="failed",
            finished_at=now,
            error_message="同步任务长时间无进展，请检查 Worker 后重新同步",
            updated_at=now,
        ):
            record.refresh_from_db()
            queue_sync_failure_alert(record)
    candidates = AssetSource.objects.filter(
        source_type="cloud", is_active=True, sync_interval_minutes__gt=0
    ).values_list("pk", flat=True)
    queued = 0
    for source_id in candidates.iterator(chunk_size=200):
        if queued >= 200:
            break
        with transaction.atomic():
            source = AssetSource.objects.select_for_update().get(pk=source_id)
            if not source.is_active or not source.sync_interval_minutes:
                continue
            if (
                source.last_sync_attempt_at
                and now
                < source.last_sync_attempt_at
                + timedelta(minutes=source.sync_interval_minutes)
            ):
                continue
            if AssetSyncRecord.objects.filter(
                source=source, status__in=["queued", "running"]
            ).exists():
                continue
            record = create_sync_record(source, [], trigger="scheduled")
            # Scheduling bookkeeping must not invalidate an already confirmed manual preview.
            AssetSource.objects.filter(pk=source.pk).update(last_sync_attempt_at=now)
            transaction.on_commit(lambda record_id=record.pk: dispatch_sync(record_id))
            queued += 1
    return queued
