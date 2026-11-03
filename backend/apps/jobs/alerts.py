"""Durable, idempotent failure alerts for terminal workflow runs."""

import logging
from datetime import timedelta
from types import SimpleNamespace

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from common.redaction import redact_text

from apps.automation.models import NotificationChannel, NotificationRecord, NotificationTemplate

from .models import WorkflowRun
from .node_executors import send_notification


logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3
RETRY_DELAYS = (60, 300, 900)
CLAIM_TIMEOUT = timedelta(minutes=5)


def _enqueue_alert(record_id):
    from .tasks import dispatch_notification_alert

    try:
        dispatch_notification_alert.apply_async(args=[record_id], queue="task")
    except Exception:
        # The pending database record is recovered by the periodic sweep.
        logger.exception("Could not enqueue notification alert %s", record_id)


@receiver(post_save, sender=WorkflowRun, dispatch_uid="jobs.queue_failure_alerts")
@transaction.atomic
def queue_failure_alerts(sender, instance, **kwargs):
    if instance.status not in {WorkflowRun.Status.FAILED, WorkflowRun.Status.TIMEOUT}:
        return
    config = instance.failure_alert or {}
    template_id = config.get("templateId") if isinstance(config, dict) else None
    if not template_id:
        return
    template = NotificationTemplate.objects.filter(pk=template_id).select_related("channel").first()
    snapshot = config.get("templateSnapshot") or {}
    channel = (
        NotificationChannel.objects.filter(pk=snapshot.get("channelId")).first()
        if isinstance(snapshot, dict) and snapshot.get("channelId") else None
    )
    if not snapshot and template:
        channel = template.channel
    available = channel is not None
    record, created = NotificationRecord.objects.get_or_create(
        alert_key=f"run-failure:{instance.pk}:{template_id}",
        defaults={
            "template": template,
            "channel": channel,
            "workflow_run": instance,
            "status": NotificationRecord.Status.PENDING if available else NotificationRecord.Status.FAILED,
            "failure_reason": (
                "通知渠道已删除" if snapshot else "通知模板已删除"
            ) if not available else "",
            "attempt_count": MAX_ATTEMPTS if not available else 0,
        },
    )
    if created:
        context = instance.failure_alert_context or _alert_context(instance)
        WorkflowRun.objects.filter(pk=instance.pk, failure_alert_context={}).update(
            failure_alert_context=context
        )
        instance.failure_alert_context = context
        if available:
            transaction.on_commit(lambda record_id=record.pk: _enqueue_alert(record_id))


def _alert_context(run):
    failed_step = run.node_runs.filter(status__in=["failed", "timeout"]).order_by("id").first()
    failed_hosts = list(
        failed_step.host_results.filter(status__in=["failed", "unreachable"])
        .order_by("hostname").values_list("hostname", flat=True)[:20]
    ) if failed_step else []
    run_name = run.name or f"运行 #{run.pk}"
    return {
        "title": f"运行{'超时' if run.status == WorkflowRun.Status.TIMEOUT else '失败'}：{run_name}",
        "run": {
            "id": run.pk,
            "name": run_name,
            "status": run.status,
            "failureReason": redact_text(run.failure_reason),
            "failedStep": failed_step.node_name or failed_step.node_key if failed_step else "",
            "failedHosts": failed_hosts,
            "detailPath": f"/{'ops' if run.run_domain == WorkflowRun.RunDomain.OPS else 'task'}/run-detail/{run.pk}",
        }
    }


def deliver_alert(record_id):
    now = timezone.now()
    with transaction.atomic():
        record = (
            NotificationRecord.objects.select_for_update()
            .select_related("template__channel", "workflow_run")
            .get(pk=record_id)
        )
        if not record.alert_key or record.status not in {
            NotificationRecord.Status.PENDING,
            NotificationRecord.Status.FAILED,
        }:
            return False
        if record.attempt_count >= MAX_ATTEMPTS or (
            record.next_retry_at and record.next_retry_at > now
        ):
            return False
        record.status = NotificationRecord.Status.SENDING
        record.attempt_count += 1
        record.claimed_at = now
        record.save(update_fields=["status", "attempt_count", "claimed_at", "updated_at"])

    try:
        run = record.workflow_run
        if not run and not (record.context and record.template_snapshot):
            raise ValueError("Alert context no longer exists")
        if run:
            snapshot = (run.failure_alert or {}).get("templateSnapshot") or {}
            context = run.failure_alert_context or _alert_context(run)
            receivers = (run.failure_alert or {}).get("receivers", "")
        else:
            snapshot = record.template_snapshot
            context = record.context
            receivers = snapshot.get("receivers", "")
        if snapshot:
            channel = record.channel
            if channel is None:
                raise ValueError("Alert channel no longer exists")
            template = SimpleNamespace(
                channel=channel,
                is_active=True,
                subject_template=snapshot["subjectTemplate"],
                body_template=snapshot["bodyTemplate"],
                receiver_template=snapshot["receiverTemplate"],
            )
        else:
            template = record.template
            if template is None:
                raise ValueError("Alert template no longer exists")
        send_notification(
            template,
            context,
            overrides={"receivers": receivers},
            record=record,
        )
    except Exception as exc:
        record.refresh_from_db()
        record.status = NotificationRecord.Status.FAILED
        if not record.failure_reason:
            record.failure_reason = f"Notification delivery failed: {exc.__class__.__name__}"
        record.next_retry_at = (
            now + timedelta(seconds=RETRY_DELAYS[record.attempt_count - 1])
            if record.attempt_count < MAX_ATTEMPTS
            else None
        )
        record.save(update_fields=["status", "failure_reason", "next_retry_at", "updated_at"])
        return False
    return True


def recover_alerts(now=None):
    now = now or timezone.now()
    NotificationRecord.objects.filter(
        alert_key__isnull=False,
        status=NotificationRecord.Status.SENDING,
        claimed_at__lt=now - CLAIM_TIMEOUT,
    ).update(status=NotificationRecord.Status.FAILED, next_retry_at=now)
    pending = NotificationRecord.objects.filter(
        alert_key__isnull=False,
        status__in=[NotificationRecord.Status.PENDING, NotificationRecord.Status.FAILED],
        attempt_count__lt=MAX_ATTEMPTS,
    ).filter(next_retry_at__isnull=True) | NotificationRecord.objects.filter(
        alert_key__isnull=False,
        status=NotificationRecord.Status.FAILED,
        attempt_count__lt=MAX_ATTEMPTS,
        next_retry_at__lte=now,
    )
    ids = list(pending.order_by("id").values_list("id", flat=True)[:100])
    for record_id in ids:
        _enqueue_alert(record_id)
    return len(ids)
