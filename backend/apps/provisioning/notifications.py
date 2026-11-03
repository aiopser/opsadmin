from django.db import transaction
import logging

from apps.automation.models import (
    NotificationRecord,
    NotificationTemplate,
    NotificationChannel,
)
from apps.jobs.alerts import _enqueue_alert
from common.redaction import redact_text


def notify(record, phase, plan_id=None, message=""):
    try:
        _notify(record, phase, plan_id, message)
    except Exception:
        # Notification persistence must not rewrite the actual cloud execution outcome.
        logging.getLogger(__name__).exception(
            "Could not persist resource notification for request %s", record.pk
        )


def _notify(record, phase, plan_id, message):
    config = record.notification_snapshot
    if not config.get("templateId"):
        return
    snapshot = {
        **config.get("templateSnapshot", {}),
        "receivers": config.get("receivers", ""),
    }
    notification, created = NotificationRecord.objects.get_or_create(
        alert_key=f"provisioning:{record.pk}:{plan_id or 0}:{phase}",
        defaults={
            "template": NotificationTemplate.objects.filter(
                pk=config["templateId"]
            ).first(),
            "channel": NotificationChannel.objects.filter(
                pk=snapshot.get("channelId")
            ).first(),
            "template_snapshot": snapshot,
            "context": {
                "title": f"资源申请：{record.name}",
                "delivery": {
                    "requestId": record.pk,
                    "name": record.name,
                    "phase": phase,
                    "region": record.region,
                    "message": redact_text(message),
                },
            },
        },
    )
    if created:
        transaction.on_commit(lambda: _enqueue_alert(notification.pk))
