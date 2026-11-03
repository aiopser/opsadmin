import pytest
from .collector import parse_avd

HTML = """<table><tr><th>编号</th></tr><tr><td><a href="/detail?id=AVD-2026-001">AVD-2026-001</a></td><td>Example</td><td><button title="执行">类型</button></td><td>2026-10-27</td><td><button></button><button title="高危">高危</button></td></tr></table>"""


def test_official_table_contract():
    row = parse_avd(HTML)[0]
    assert row["stable_id"] == "AVD-2026-001"
    assert row["severity"] == "high"
    assert row["url"].startswith("https://avd.aliyun.com/detail?")


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["timeout", "schema"])
def test_collection_failure_identifies_safe_stage(kind, monkeypatch, django_user_model):
    import requests
    from .models import SecuritySubscription, SecurityCollection
    from .tasks import collect

    actor = django_user_model.objects.create(username=f"diagnostic-{kind}")
    subscription = SecuritySubscription.objects.create(name="official", actor=actor)
    record = SecurityCollection.objects.create(subscription=subscription, actor=actor)
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: True)

    def fail():
        if kind == "timeout":
            raise requests.exceptions.Timeout("secret=do-not-leak")
        raise ValueError("secret=do-not-leak")

    monkeypatch.setattr("apps.security.tasks.fetch_avd", fail)
    collect(record.pk)
    record.refresh_from_db()
    assert f"fetch/{kind}" in record.error
    assert "do-not-leak" not in record.error


@pytest.mark.parametrize(
    "html",
    [
        "<html>captcha</html>",
        "<table><tr><td>changed</td></tr></table>",
        HTML.replace("/detail?id=", "https://evil.invalid/?id="),
    ],
)
def test_reject_changed_or_unsafe_source(html):
    with pytest.raises(ValueError):
        parse_avd(html)


@pytest.mark.django_db
def test_baseline_changes_filters_and_durable_dedupe(monkeypatch, django_user_model):
    from apps.automation.models import (
        NotificationChannel,
        NotificationTemplate,
        NotificationRecord,
    )
    from .models import SecuritySubscription, SecurityCollection, SecurityAdvisory
    from .tasks import collect

    actor = django_user_model.objects.create(
        username="security-worker", is_active=True, is_superuser=True
    )
    channel = NotificationChannel.objects.create(name="mock", channel_type="wecom")
    template = NotificationTemplate.objects.create(
        name="mock",
        code="security-mock",
        channel=channel,
        body_template="{{ advisory.title }}",
    )
    subscription = SecuritySubscription.objects.create(
        name="official",
        actor=actor,
        enabled=True,
        notification={"templateId": template.pk},
    )
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: True)
    monkeypatch.setattr("apps.security.tasks._enqueue_alert", lambda *args: None)
    rows = parse_avd(HTML)
    monkeypatch.setattr("apps.security.tasks.fetch_avd", lambda: rows)

    def run():
        record = SecurityCollection.objects.create(
            subscription=subscription, actor=actor
        )
        collect(record.pk)
        record.refresh_from_db()
        assert record.status == "success"
        return record

    assert run().notifications == 0
    assert SecurityAdvisory.objects.count() == 1
    rows = parse_avd(HTML.replace("Example", "Updated"))
    assert run().notifications == 1
    assert run().notifications == 0
    assert NotificationRecord.objects.count() == 1
    subscription.keywords = ["does not match"]
    subscription.save()
    rows = parse_avd(HTML.replace("Example", "Unmatched"))
    assert run().notifications == 0


@pytest.mark.django_db
def test_failed_fetch_and_revoked_actor_never_initialize(
    monkeypatch, django_user_model
):
    from .models import SecuritySubscription, SecurityCollection
    from .tasks import collect

    actor = django_user_model.objects.create(username="revoked")
    subscription = SecuritySubscription.objects.create(name="official", actor=actor)
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: False)
    monkeypatch.setattr(
        "apps.security.tasks.fetch_avd",
        lambda: pytest.fail("unauthorized network access"),
    )
    record = SecurityCollection.objects.create(subscription=subscription, actor=actor)
    collect(record.pk)
    record.refresh_from_db()
    subscription.refresh_from_db()
    assert record.status == "failed"
    assert subscription.initialized_at is None


@pytest.mark.django_db
def test_stale_queued_task_is_failed_and_duplicate_delivery_is_fenced(
    monkeypatch, django_user_model
):
    from datetime import timedelta
    from django.utils import timezone
    from .models import SecuritySubscription, SecurityCollection
    from .tasks import sweep, collect, enqueue

    actor = django_user_model.objects.create(username="security-queue")
    subscription = SecuritySubscription.objects.create(name="official", actor=actor)
    record = SecurityCollection.objects.create(subscription=subscription, actor=actor)
    with pytest.raises(ValueError, match="已有采集"):
        enqueue(subscription.pk, actor)
    SecurityCollection.objects.filter(pk=record.pk).update(
        updated_at=timezone.now() - timedelta(minutes=11)
    )
    sweep()
    record.refresh_from_db()
    assert record.status == "failed"
    monkeypatch.setattr(
        "apps.security.tasks.fetch_avd",
        lambda: pytest.fail("stale execution must not fetch"),
    )
    collect(record.pk)


@pytest.mark.django_db
def test_sweep_shares_one_fetch_across_due_subscriptions(
    monkeypatch, django_user_model
):
    from datetime import timedelta

    from django.utils import timezone

    from .models import SecurityCollection, SecurityFetch, SecuritySubscription
    from .tasks import collect_source, sweep

    now = timezone.now()
    actor = django_user_model.objects.create(username="security-share", is_active=True)
    due = SecuritySubscription.objects.create(
        name="due",
        actor=actor,
        enabled=True,
        last_attempt_at=now - timedelta(minutes=120),
    )
    waiting = SecuritySubscription.objects.create(
        name="waiting", actor=actor, enabled=True, last_attempt_at=now
    )
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: True)
    calls = []
    rows = parse_avd(HTML)

    def fetch():
        calls.append(1)
        return rows

    monkeypatch.setattr("apps.security.tasks.fetch_avd", fetch)
    sweep()
    assert SecurityCollection.objects.filter(subscription=due, status="queued").exists()
    assert not SecurityCollection.objects.filter(subscription=waiting).exists()
    fetch_row = SecurityFetch.objects.get(status="queued")
    record_ids = list(
        SecurityCollection.objects.filter(status="queued").values_list("pk", flat=True)
    )
    collect_source(fetch_row.pk, record_ids)
    assert len(calls) == 1
    fetch_row.refresh_from_db()
    assert fetch_row.status == "success"
    assert fetch_row.count == len(rows)
    due.refresh_from_db()
    assert due.initialized_at is not None
    assert not SecurityCollection.objects.filter(status="queued").exists()


@pytest.mark.django_db
def test_shared_fetch_failure_marks_every_record_failed(monkeypatch, django_user_model):
    import requests

    from .models import SecurityFetch, SecuritySubscription
    from .tasks import collect_source, enqueue

    actor = django_user_model.objects.create(username="security-share-fail")
    first = SecuritySubscription.objects.create(name="a", actor=actor, enabled=True)
    second = SecuritySubscription.objects.create(name="b", actor=actor, enabled=True)
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: True)

    def fail():
        raise requests.exceptions.Timeout("secret=do-not-leak")

    monkeypatch.setattr("apps.security.tasks.fetch_avd", fail)
    record_a = enqueue(first.pk, actor, "scheduled", dispatch_record=False)
    record_b = enqueue(second.pk, actor, "scheduled", dispatch_record=False)
    fetch_row = SecurityFetch.objects.create(trigger="scheduled")
    collect_source(fetch_row.pk, [record_a.pk, record_b.pk])
    record_a.refresh_from_db()
    record_b.refresh_from_db()
    fetch_row.refresh_from_db()
    assert record_a.status == record_b.status == "failed"
    assert "fetch/timeout" in record_a.error
    assert "do-not-leak" not in record_a.error
    assert fetch_row.status == "failed"
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.initialized_at is None and second.initialized_at is None


@pytest.mark.django_db
def test_source_failure_is_not_empty_success(monkeypatch, django_user_model):
    from .models import SecuritySubscription, SecurityCollection
    from .tasks import collect

    actor = django_user_model.objects.create(username="security-source-error")
    subscription = SecuritySubscription.objects.create(name="official", actor=actor)
    record = SecurityCollection.objects.create(subscription=subscription, actor=actor)
    monkeypatch.setattr("apps.security.tasks.authorized", lambda *args: True)

    def fail():
        raise RuntimeError("secret-token-in-request-must-never-leak")

    monkeypatch.setattr("apps.security.tasks.fetch_avd", fail)
    collect(record.pk)
    record.refresh_from_db()
    subscription.refresh_from_db()
    assert record.status == "failed"
    assert "secret-token" not in record.error
    assert subscription.initialized_at is None


@pytest.mark.django_db
def test_subscription_api_persists_actor_and_validates_enabled_notification(
    django_user_model,
):
    from rest_framework.test import APIRequestFactory, force_authenticate
    from .views import SubscriptionViewSet
    from .models import SecuritySubscription

    actor = django_user_model.objects.create(username="security-api", is_superuser=True)
    factory = APIRequestFactory()
    view = SubscriptionViewSet.as_view({"post": "create"})
    request = factory.post(
        "/api/v1/security/subscriptions",
        {"name": "AVD", "interval_minutes": 60},
        format="json",
    )
    force_authenticate(request, actor)
    response = view(request)
    assert response.status_code == 200
    assert SecuritySubscription.objects.get().actor == actor
    request = factory.post(
        "/api/v1/security/subscriptions",
        {"name": "AVD", "enabled": True, "interval_minutes": 60},
        format="json",
    )
    force_authenticate(request, actor)
    assert view(request).status_code == 400


@pytest.mark.django_db
def test_notifications_reuse_existing_failure_retry_delivery(
    monkeypatch, django_user_model
):
    from django.utils import timezone
    from apps.automation.models import (
        NotificationChannel,
        NotificationTemplate,
        NotificationRecord,
    )
    from apps.jobs.alerts import deliver_alert
    from .models import SecuritySubscription, SecurityAdvisory
    from .tasks import queue_notification

    actor = django_user_model.objects.create(username="security-retry")
    channel = NotificationChannel.objects.create(name="mock", channel_type="wecom")
    template = NotificationTemplate.objects.create(
        name="mock",
        code="security-retry",
        channel=channel,
        body_template="{{ advisory.title }}",
    )
    subscription = SecuritySubscription.objects.create(
        name="official", actor=actor, notification={"templateId": template.pk}
    )
    advisory = SecurityAdvisory.objects.create(**parse_avd(HTML)[0])
    monkeypatch.setattr("apps.security.tasks._enqueue_alert", lambda *args: None)
    assert queue_notification(subscription, advisory)
    assert not queue_notification(subscription, advisory)
    record = NotificationRecord.objects.get()

    def fail(*args, **kwargs):
        raise RuntimeError("mock failure")

    monkeypatch.setattr("apps.jobs.alerts.send_notification", fail)
    assert not deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.status == "failed"
    assert record.attempt_count == 1
    assert record.next_retry_at is not None
    NotificationRecord.objects.filter(pk=record.pk).update(next_retry_at=timezone.now())

    def succeed(*args, record, **kwargs):
        record.status = "success"
        record.save()

    monkeypatch.setattr("apps.jobs.alerts.send_notification", succeed)
    assert deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.status == "success"
    assert record.attempt_count == 2


@pytest.mark.django_db
def test_advisory_pagination_matches_frontend_contract(django_user_model):
    from rest_framework.test import APIRequestFactory, force_authenticate
    from .views import AdvisoryViewSet

    actor = django_user_model.objects.create(
        username="security-reader", is_superuser=True
    )
    request = APIRequestFactory().get(
        "/api/v1/security/advisories", {"pageNum": 1, "pageSize": 20}
    )
    force_authenticate(request, actor)
    response = AdvisoryViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert response.data["data"]["list"] == []
    assert response.data["data"]["total"] == 0
