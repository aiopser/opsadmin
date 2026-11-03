from datetime import timedelta

import pytest
from django.utils import timezone

from apps.automation.models import NotificationChannel, NotificationRecord, NotificationTemplate, WorkflowTemplate
from apps.automation.failure_alerts import freeze_failure_alert
from apps.automation.serializers import WorkflowTemplateSerializer
from apps.cmdb.crypto import encrypt_secret
from apps.jobs.alerts import deliver_alert, recover_alerts
from apps.jobs.models import WorkerPool, WorkflowRun, WorkflowTaskTicket
from apps.jobs.serializers import WorkflowTaskTicketSerializer


@pytest.fixture
def failure_alert(monkeypatch):
    monkeypatch.setattr("apps.jobs.alerts._enqueue_alert", lambda record_id: None)
    pool = WorkerPool.objects.create(code="alerts", name="alerts", queue_name="task")
    channel = NotificationChannel.objects.create(
        name="alert hook",
        channel_type=NotificationChannel.ChannelType.WEBHOOK,
        secret_encrypted=encrypt_secret("https://example.test/robot"),
    )
    template = NotificationTemplate.objects.create(
        name="run failed",
        code="run-failed",
        channel=channel,
        subject_template="Run {{ run.id }} failed",
        body_template="{{ run.name }}: {{ run.failureReason }}",
    )
    run = WorkflowRun.objects.create(
        worker_pool=pool, name="deployment",
        failure_alert={"templateId": template.pk, "receivers": "ops@example.test"},
    )
    return run, template


@pytest.mark.django_db
def test_failure_alert_is_durable_and_idempotent(monkeypatch, failure_alert):
    run, template = failure_alert
    run.status = WorkflowRun.Status.FAILED
    run.failure_reason = "worker unavailable"
    run.save(update_fields=["status", "failure_reason"])
    run.save(update_fields=["status"])
    record = NotificationRecord.objects.get(workflow_run=run, template=template)
    assert NotificationRecord.objects.filter(workflow_run=run, alert_key__isnull=False).count() == 1
    assert record.status == NotificationRecord.Status.PENDING

    sent = {}

    def fake_request(method, url, headers, body, timeout):
        sent["body"] = body
        return 200, {}, "{}"

    monkeypatch.setattr("apps.jobs.node_executors._request", fake_request)
    assert deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.status == NotificationRecord.Status.SUCCESS
    assert record.attempt_count == 1
    assert b"worker unavailable" in sent["body"]
    assert record.receivers == ["ops@example.test"]
    assert not deliver_alert(record.pk)


@pytest.mark.django_db
def test_failed_alert_is_retried_without_new_record(monkeypatch, failure_alert):
    run, template = failure_alert
    run.status = WorkflowRun.Status.TIMEOUT
    run.save(update_fields=["status"])
    record = NotificationRecord.objects.get(workflow_run=run, template=template)
    monkeypatch.setattr("apps.jobs.node_executors._request", lambda *args: (503, {}, "down"))
    assert not deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.status == NotificationRecord.Status.FAILED
    assert record.attempt_count == 1
    assert record.next_retry_at is not None

    record.next_retry_at = timezone.now() - timedelta(seconds=1)
    record.save(update_fields=["next_retry_at"])
    monkeypatch.setattr("apps.jobs.node_executors._request", lambda *args: (200, {}, "{}"))
    assert deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.status == NotificationRecord.Status.SUCCESS
    assert record.attempt_count == 2
    assert record.failure_reason == ""


@pytest.mark.django_db
def test_run_without_failure_alert_does_not_notify(failure_alert):
    run, _ = failure_alert
    run.failure_alert = {}
    run.status = WorkflowRun.Status.FAILED
    run.save(update_fields=["failure_alert", "status"])
    assert not NotificationRecord.objects.filter(workflow_run=run).exists()


@pytest.mark.django_db
def test_workflow_alert_contract_and_ticket_override(failure_alert):
    _, template = failure_alert
    workflow = WorkflowTemplate.objects.create(name="deploy", code="deploy")
    data = {"failureAlert": {"templateId": template.pk, "receivers": "ops@example.test"}}
    serializer = WorkflowTemplateSerializer(workflow, data=data, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert WorkflowTemplateSerializer(workflow).data["failureAlert"] == data["failureAlert"]

    ticket = WorkflowTaskTicket.objects.create(name="deploy ticket")
    ticket_serializer = WorkflowTaskTicketSerializer(ticket)
    assert ticket_serializer.data["failureAlert"] is None


@pytest.mark.django_db
def test_deleted_template_keeps_visible_failed_alert_record(failure_alert):
    run, template = failure_alert
    template.delete()
    run.status = WorkflowRun.Status.FAILED
    run.save(update_fields=["status"])
    record = NotificationRecord.objects.get(workflow_run=run)
    assert record.status == NotificationRecord.Status.FAILED
    assert record.failure_reason == "通知模板已删除"


@pytest.mark.django_db
def test_run_alert_uses_frozen_template_after_template_is_edited(monkeypatch, failure_alert):
    run, template = failure_alert
    run.failure_alert = freeze_failure_alert(run.failure_alert)
    run.save(update_fields=["failure_alert"])
    template.body_template = "edited after run creation"
    template.save(update_fields=["body_template"])
    run.status = WorkflowRun.Status.FAILED
    run.failure_reason = "original incident"
    run.save(update_fields=["status", "failure_reason"])
    sent = {}

    def fake_request(method, url, headers, body, timeout):
        sent["body"] = body
        return 200, {}, "{}"

    monkeypatch.setattr("apps.jobs.node_executors._request", fake_request)
    assert deliver_alert(NotificationRecord.objects.get(workflow_run=run).pk)
    assert b"original incident" in sent["body"]
    assert b"edited after run creation" not in sent["body"]


@pytest.mark.django_db
def test_run_alert_uses_frozen_template_after_template_is_deleted(monkeypatch, failure_alert):
    run, template = failure_alert
    run.failure_alert = freeze_failure_alert(run.failure_alert)
    run.save(update_fields=["failure_alert"])
    template.delete()
    run.status = WorkflowRun.Status.FAILED
    run.save(update_fields=["status"])
    record = NotificationRecord.objects.get(workflow_run=run)
    assert record.status == NotificationRecord.Status.PENDING
    monkeypatch.setattr("apps.jobs.node_executors._request", lambda *args: (200, {}, "{}"))
    assert deliver_alert(record.pk)


@pytest.mark.django_db
def test_failure_alert_supports_common_title_placeholder(monkeypatch, failure_alert):
    run, template = failure_alert
    template.subject_template = "{{ title }}"
    template.body_template = "{{ run.failureReason }}"
    template.save(update_fields=["subject_template", "body_template"])
    run.failure_alert = freeze_failure_alert(run.failure_alert)
    run.save(update_fields=["failure_alert"])
    run.status = WorkflowRun.Status.FAILED
    run.failure_reason = "command step failed"
    run.save(update_fields=["status", "failure_reason"])
    sent = {}

    def fake_request(method, url, headers, body, timeout):
        sent["body"] = body
        return 200, {}, "{}"

    monkeypatch.setattr("apps.jobs.node_executors._request", fake_request)
    record = NotificationRecord.objects.get(workflow_run=run)
    assert deliver_alert(record.pk)
    record.refresh_from_db()
    assert record.subject == "运行失败：deployment"
    assert b"command step failed" in sent["body"]
