import hashlib
import requests
from datetime import timedelta
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from common.auth.rbac import verify_permission
from apps.automation.failure_alerts import freeze_failure_alert
from apps.automation.models import NotificationRecord, NotificationTemplate
from apps.jobs.alerts import _enqueue_alert
from .collector import fetch_avd
from .models import (
    SecurityAdvisory,
    SecurityCollection,
    SecurityFetch,
    SecurityObservation,
    SecuritySubscription,
)


def authorized(actor, subscription_id):
    return bool(
        actor
        and actor.is_active
        and actor.job_status
        and verify_permission(
            actor, f"/api/v1/security/subscriptions/{subscription_id}/collect", "POST"
        )[0]
    )


def dispatch(record_id):
    try:
        collect.apply_async(args=[record_id], queue="task")
    except Exception:
        SecurityCollection.objects.filter(pk=record_id, status="queued").update(
            status="failed", error="任务投递失败，请检查 Worker", finished_at=timezone.now()
        )


def enqueue(subscription_id, actor, trigger="manual", dispatch_record=True):
    with transaction.atomic():
        subscription = SecuritySubscription.objects.select_for_update().get(
            pk=subscription_id
        )
        if SecurityCollection.objects.filter(
            subscription=subscription, status__in=["queued", "running"]
        ).exists():
            raise ValueError("已有采集任务进行中")
        record = SecurityCollection.objects.create(
            subscription=subscription, actor=actor, trigger=trigger
        )
        SecuritySubscription.objects.filter(pk=subscription.pk).update(
            last_attempt_at=timezone.now()
        )
        if dispatch_record:
            transaction.on_commit(lambda: dispatch(record.pk))
        return record


def describe_failure(stage, exc):
    """Map an exception to a safe (category, hint) pair without leaking internals."""
    if isinstance(exc, (TimeoutError, requests.exceptions.Timeout)):
        return "timeout", "请求超时，请检查 Worker 出网与源站响应"
    if isinstance(exc, requests.exceptions.SSLError):
        return "tls", "证书验证失败，请检查系统证书及代理"
    if isinstance(exc, requests.exceptions.RequestException):
        return "network", "源站请求失败，请检查网络、HTTP 状态及访问限制"
    if stage == "fetch" and isinstance(exc, (ValueError, UnicodeError)):
        return "schema", "源站结构、内容或编码变化，请核对公告解析规则"
    hints = {
        "authorization": "执行账号权限失效或订阅已停用",
        "fetch": "读取官方源失败，请检查源站状态和访问限制",
        "notification": "通知配置无效，请检查模板与渠道启用状态",
        "persist": "公告保存失败，请检查数据库与任务状态",
    }
    return "unknown", hints.get(stage, "采集失败，请查看采集记录")


def fail_records(queryset, stage, exc):
    category, hint = describe_failure(stage, exc)
    queryset.update(
        status="failed",
        error=f"采集失败[{stage}/{category}]：{hint}",
        finished_at=timezone.now(),
        updated_at=timezone.now(),
    )


def queue_notification(subscription, advisory):
    config = freeze_failure_alert(subscription.notification) or {}
    if not config:
        return False
    template = NotificationTemplate.objects.filter(
        pk=config["templateId"], is_active=True, channel__is_active=True
    ).first()
    if template is None:
        raise ValueError("通知模板或渠道已停用")
    record, created = NotificationRecord.objects.get_or_create(
        alert_key="security:"
        + hashlib.sha256(
            f"{subscription.pk}:{advisory.stable_id}:{advisory.fingerprint}".encode()
        ).hexdigest(),
        defaults=dict(
            template=template,
            channel=template.channel,
            template_snapshot={
                **config["templateSnapshot"],
                "receivers": config.get("receivers", ""),
            },
            context={
                "delivery": {"actorId": subscription.actor_id},
                "title": f"漏洞公告：{advisory.title}",
                "advisory": {
                    "id": advisory.stable_id,
                    "title": advisory.title,
                    "url": advisory.url,
                    "severity": advisory.severity,
                    "category": advisory.category,
                    "published": advisory.published,
                },
            },
        ),
    )
    if created:
        transaction.on_commit(lambda: _enqueue_alert(record.pk))
    return created


def sync_advisories(rows):
    """Persist one shared fetch result; every subscription matches against these rows."""
    advisories = []
    for row in rows:
        advisory, _ = SecurityAdvisory.objects.update_or_create(
            stable_id=row["stable_id"], defaults=row
        )
        advisories.append(advisory)
    return advisories


def apply_subscription(record, advisories):
    """Match one shared fetch result against one subscription and finalize its record."""
    subscription = record.subscription
    stage = "authorization"
    try:
        if not authorized(record.actor, subscription.pk):
            raise ValueError("执行账号采集权限已失效")
        if record.trigger == "scheduled" and not subscription.enabled:
            raise ValueError("周期订阅已停用")
        count = 0
        with transaction.atomic():
            stage = "persist"
            for advisory in advisories:
                observation = SecurityObservation.objects.filter(
                    subscription=subscription, advisory=advisory
                ).first()
                changed = (
                    observation is None
                    or observation.fingerprint != advisory.fingerprint
                )
                matches = (
                    not subscription.severities
                    or advisory.severity in subscription.severities
                ) and (
                    not subscription.keywords
                    or any(
                        word.casefold()
                        in f"{advisory.title} {advisory.category}".casefold()
                        for word in subscription.keywords
                    )
                )
                if (
                    subscription.initialized_at
                    and subscription.enabled
                    and changed
                    and matches
                ):
                    stage = "notification"
                    count += int(queue_notification(subscription, advisory))
                    stage = "persist"
                SecurityObservation.objects.update_or_create(
                    subscription=subscription,
                    advisory=advisory,
                    defaults={"fingerprint": advisory.fingerprint},
                )
            if not subscription.initialized_at:
                subscription.initialized_at = timezone.now()
                subscription.save(update_fields=["initialized_at"])
        SecurityCollection.objects.filter(
            pk=record.pk, status__in=["queued", "running"]
        ).update(
            status="success",
            count=len(advisories),
            notifications=count,
            finished_at=timezone.now(),
            updated_at=timezone.now(),
        )
    except Exception as exc:
        fail_records(
            SecurityCollection.objects.filter(
                pk=record.pk, status__in=["queued", "running"]
            ),
            stage,
            exc,
        )


@shared_task(name="security.collect", soft_time_limit=90, time_limit=120)
def collect(record_id):
    """Manual single-subscription collection: fetch the source once for itself."""
    if not SecurityCollection.objects.filter(pk=record_id, status="queued").update(
        status="running", updated_at=timezone.now()
    ):
        return
    record = SecurityCollection.objects.select_related("subscription", "actor").get(
        pk=record_id
    )
    stage = "authorization"
    try:
        if not authorized(record.actor, record.subscription_id):
            raise ValueError("执行账号采集权限已失效")
        stage = "fetch"
        advisories = sync_advisories(fetch_avd())
        apply_subscription(record, advisories)
    except Exception as exc:
        fail_records(
            SecurityCollection.objects.filter(
                pk=record_id, status__in=["queued", "running"]
            ),
            stage,
            exc,
        )


@shared_task(name="security.collect_source", soft_time_limit=90, time_limit=120)
def collect_source(fetch_id, record_ids):
    """Scheduled shared collection: fetch the source once, then match every due subscription."""
    if not SecurityFetch.objects.filter(pk=fetch_id, status="queued").update(
        status="running", updated_at=timezone.now()
    ):
        return
    records = list(
        SecurityCollection.objects.filter(
            pk__in=record_ids, status="queued"
        ).select_related("subscription", "actor")
    )
    try:
        advisories = sync_advisories(fetch_avd())
    except Exception as exc:
        fail_records(
            SecurityCollection.objects.filter(
                pk__in=[record.pk for record in records],
                status__in=["queued", "running"],
            ),
            "fetch",
            exc,
        )
        fail_records(
            SecurityFetch.objects.filter(pk=fetch_id, status="running"), "fetch", exc
        )
        return
    for record in records:
        apply_subscription(record, advisories)
    SecurityFetch.objects.filter(pk=fetch_id, status="running").update(
        status="success",
        count=len(advisories),
        finished_at=timezone.now(),
        updated_at=timezone.now(),
    )


@shared_task(name="security.sweep")
def sweep():
    now = timezone.now()
    SecurityCollection.objects.filter(
        status__in=["queued", "running"], updated_at__lt=now - timedelta(minutes=10)
    ).update(
        status="failed",
        error="采集超时，已释放任务，请重新采集",
        finished_at=now,
        updated_at=now,
    )
    SecurityFetch.objects.filter(
        status__in=["queued", "running"], updated_at__lt=now - timedelta(minutes=10)
    ).update(
        status="failed",
        error="抓取超时，已释放任务",
        finished_at=now,
        updated_at=now,
    )
    record_ids = []
    for subscription in SecuritySubscription.objects.filter(
        enabled=True
    ).select_related("actor"):
        if (
            subscription.last_attempt_at
            and subscription.last_attempt_at
            + timedelta(minutes=subscription.interval_minutes)
            > now
        ):
            continue
        if not authorized(subscription.actor, subscription.pk):
            continue
        try:
            record = enqueue(
                subscription.pk, subscription.actor, "scheduled", dispatch_record=False
            )
        except ValueError:
            continue
        record_ids.append(record.pk)
    if not record_ids:
        return
    fetch = SecurityFetch.objects.create(trigger="scheduled")
    transaction.on_commit(
        lambda: collect_source.apply_async(args=[fetch.pk, record_ids], queue="task")
    )
