from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from .models import JumpServerSync, JumpServerConnection
from .services import execute, preview, confirm


@shared_task(soft_time_limit=900, time_limit=960)
def sync_jumpserver(run_id):
    execute(run_id)


@shared_task
def recover_stale_jumpserver():
    return JumpServerSync.objects.filter(
        status__in=["queued", "running"],
        updated_at__lt=timezone.now() - timedelta(minutes=20),
    ).update(status="failed", error="任务超时或worker中断，请重新预览后重试", updated_at=timezone.now())


@shared_task
def schedule_jumpserver():
    recover_stale_jumpserver()
    for connection in JumpServerConnection.objects.filter(
        is_active=True, sync_interval_minutes__gt=0
    ).select_related("sync_actor"):
        if (
            connection.last_sync_at
            and connection.last_sync_at
            > timezone.now() - timedelta(minutes=connection.sync_interval_minutes)
        ):
            continue
        try:
            run = preview(
                connection, connection.sync_actor, connection.selected_host_ids
            )
            run = confirm(run, connection.sync_actor)
            sync_jumpserver.delay(run.pk)
        except Exception:
            continue
