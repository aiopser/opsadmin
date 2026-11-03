from datetime import timedelta

from celery import group
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from common.auth.rbac import verify_permission
from apps.consul.models import ConsulConnection
from .models import MonitoringTarget, SyncRecord
from .registration import ACTIVE, enqueue_sync


def publish_records(record_ids):
    """Do not retry publishing in the web request; surface failures on records."""
    if not record_ids:
        return
    from .tasks import sync_consul_target

    try:
        group(sync_consul_target.s(record_id) for record_id in record_ids).apply_async(
            retry=False
        )
    except Exception:
        SyncRecord.objects.filter(pk__in=record_ids, status="queued").update(
            status="failed", error="任务投递失败，请检查 Celery 服务后重试", finished_at=timezone.now()
        )


def check_auto_actor(target, actor):
    if not actor or not actor.is_active or not getattr(actor, "job_status", False):
        raise ValidationError("自动同步执行账号已失效，请重新配置自动同步")
    allowed, _ = verify_permission(
        actor, f"/api/v1/monitoring/targets/{target.pk}/sync", "POST"
    )
    if not allowed:
        raise ValidationError("自动同步执行账号已无同步权限，请重新配置")
    if target.follow_host_address and target.host_id:
        allowed, _ = verify_permission(
            actor, f"/api/v1/cmdb/hosts/{target.host_id}", "GET"
        )
        if not allowed:
            raise ValidationError("自动同步执行账号已无关联主机读取权限")


def dispatch_due_targets():
    now = timezone.now()
    ids = list(
        MonitoringTarget.objects.filter(
            sync_interval_minutes__gt=0, connection__is_active=True
        )
        .exclude(sync_records__status__in=ACTIVE)
        .filter(Q(next_auto_sync_at__isnull=True) | Q(next_auto_sync_at__lte=now))
        .order_by("next_auto_sync_at", "id")
        .values_list("id", flat=True)[:100]
    )
    record_ids = []
    failed = 0
    for target_id in ids:
        with transaction.atomic():
            connection_id = (
                MonitoringTarget.objects.filter(pk=target_id)
                .values_list("connection_id", flat=True)
                .first()
            )
            if connection_id is None:
                continue
            ConsulConnection.objects.select_for_update().get(pk=connection_id)
            target = (
                MonitoringTarget.objects.select_for_update()
                .select_related("host", "auto_sync_actor", "connection")
                .filter(pk=target_id)
                .first()
            )
            if (
                not target
                or target.connection_id != connection_id
                or not target.connection.is_active
                or not target.sync_interval_minutes
                or (target.next_auto_sync_at and target.next_auto_sync_at > now)
            ):
                continue
            if target.sync_records.filter(status__in=ACTIVE).exists():
                continue
            target.last_auto_sync_at = now
            target.next_auto_sync_at = now + timedelta(
                minutes=target.sync_interval_minutes
            )
            error = ""
            try:
                check_auto_actor(target, target.auto_sync_actor)
            except ValidationError as exc:
                error = "；".join(map(str, exc.detail))[:512]
                target.sync_interval_minutes = 0
                target.next_auto_sync_at = None
            if not error and target.follow_host_address:
                if not target.host or target.host.status != "active":
                    error = "关联主机已删除或停用，本次跳过；原 Consul 注册保留"
                else:
                    address = (
                        target.host.internal_ip
                        if target.address_source == "internal"
                        else target.host.external_ip
                    )
                    if not address:
                        error = "关联主机缺少所选 IP，本次跳过；不回退其他地址"
                    else:
                        from .serializers import MonitoringTargetSerializer

                        try:
                            target.address = (
                                MonitoringTargetSerializer().validate_address(address)
                            )
                        except ValidationError:
                            error = "关联主机 IP 不允许用于监控目标"
            target.save(
                update_fields=[
                    "last_auto_sync_at",
                    "next_auto_sync_at",
                    "sync_interval_minutes",
                    "address",
                    "updated_at",
                ]
            )
            if error:
                SyncRecord.objects.create(
                    target=target,
                    target_name=target.name,
                    actor=target.auto_sync_actor,
                    trigger="automatic",
                    operation="register",
                    status="failed",
                    error=error,
                    finished_at=now,
                )
                failed += 1
                continue
            record_ids.append(
                enqueue_sync(
                    target.pk, "register", target.auto_sync_actor, trigger="automatic"
                ).pk
            )
    if record_ids:
        publish_records(record_ids)
    return {"queued": len(record_ids), "failed": failed}
