"""通知历史记录清理。

配置以 SystemConfig 存储（分组 notification）。仅清理发送成功、超过保留期
且不携带 alert_key 的记录；失败记录与告警去重记录始终保留。
"""

from datetime import timedelta

from django.utils import timezone

from apps.permission.models import SystemConfig

from .models import NotificationRecord

CONFIG_GROUP = "notification"
CONFIG_KEY = "notification.history.retention_days"
DEFAULT_RETENTION_DAYS = 180
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 3650
BATCH_SIZE = 500


def _parse_retention_days(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    if not MIN_RETENTION_DAYS <= value <= MAX_RETENTION_DAYS:
        return DEFAULT_RETENTION_DAYS
    return value


def parse_retention_days(value) -> int:
    try:
        days = int(value)
    except (TypeError, ValueError):
        raise ValueError("保留天数必须是数字") from None
    if not MIN_RETENTION_DAYS <= days <= MAX_RETENTION_DAYS:
        raise ValueError(f"保留天数范围应为 {MIN_RETENTION_DAYS} ~ {MAX_RETENTION_DAYS}")
    return days


def get_history_settings() -> dict:
    config = (
        SystemConfig.objects.filter(config_key=CONFIG_KEY).only("config_value").first()
    )
    return {
        "retentionDays": _parse_retention_days(config.config_value if config else None)
    }


def save_history_settings(payload: dict) -> dict:
    days = parse_retention_days(payload.get("retentionDays"))
    SystemConfig.objects.update_or_create(
        config_key=CONFIG_KEY,
        defaults={
            "config_name": "通知历史清理:retention_days",
            "config_value": str(days),
            "config_group": CONFIG_GROUP,
            "is_system": True,
        },
    )
    return get_history_settings()


def notification_history_candidates(*, now=None, retention_days=None):
    days = retention_days or get_history_settings()["retentionDays"]
    cutoff = (now or timezone.now()) - timedelta(days=days)
    return NotificationRecord.objects.filter(
        status=NotificationRecord.Status.SUCCESS,
        alert_key__isnull=True,
        sent_at__isnull=False,
        sent_at__lt=cutoff,
    )


def purge_notification_history(*, dry_run=False, now=None, retention_days=None) -> dict:
    candidates = notification_history_candidates(now=now, retention_days=retention_days)
    if dry_run:
        return {"count": candidates.count(), "deleted": 0, "dryRun": True}

    deleted = 0
    while True:
        ids = list(candidates.values_list("pk", flat=True)[:BATCH_SIZE])
        if not ids:
            break
        NotificationRecord.objects.filter(pk__in=ids).delete()
        deleted += len(ids)
        if len(ids) < BATCH_SIZE:
            break
    return {"count": deleted, "deleted": deleted, "dryRun": False}
