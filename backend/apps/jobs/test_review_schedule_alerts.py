"""Regression coverage for schedule boundaries and durable failure alerts."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.failure_alerts import freeze_failure_alert
from apps.automation.models import NotificationChannel, NotificationRecord, WorkflowTemplate
from apps.automation.views import WorkflowTemplateViewSet
from apps.cmdb.crypto import encrypt_secret
from apps.jobs.alerts import deliver_alert
from apps.jobs.cron import prev_cron_time
from apps.jobs.models import ScheduledJobOutcome, WorkflowRun, WorkflowTaskTicket
from apps.jobs.schedule_sync import periodic_task_name
from apps.jobs.tasks import deliver_scheduled_catchups
from apps.jobs.test_failure_alerts import failure_alert
from apps.jobs.test_schedule_one_off import actor, fire, host, make_schedule, pool, version
from apps.jobs.views import ScheduledJobViewSet


@pytest.mark.django_db
def test_once_expiry_must_be_after_execution_time(actor, host, pool, version):
    run_at = timezone.now() + timedelta(hours=1)
    request = APIRequestFactory().post(
        "/api/v1/jobs/scheduled-jobs",
        {
            "name": "empty execution window",
            "workflow_version": version.pk,
            "worker_pool": pool.pk,
            "host_ids": [host.pk],
            "schedule_type": "once",
            "run_at": run_at.isoformat(),
            "expires_at": run_at.isoformat(),
        },
        format="json",
    )
    force_authenticate(request, actor)

    response = ScheduledJobViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 400
    assert not version.scheduled_jobs.exists()


@pytest.mark.django_db
def test_completed_once_requires_a_future_time_before_reenabling(actor, host, pool, version):
    run_at = timezone.now() - timedelta(minutes=1)
    schedule = make_schedule(
        version, pool, actor, host, schedule_type="once", run_at=run_at, enabled=False
    )
    ScheduledJobOutcome.objects.create(
        scheduled_job=schedule, scheduled_for=run_at, outcome="dispatched"
    )
    request = APIRequestFactory().patch(
        f"/api/v1/jobs/scheduled-jobs/{schedule.pk}", {"enabled": True}, format="json"
    )
    force_authenticate(request, actor)

    response = ScheduledJobViewSet.as_view({"patch": "partial_update"})(request, pk=schedule.pk)

    assert response.status_code == 400
    schedule.refresh_from_db()
    assert not schedule.enabled


@pytest.mark.django_db
@pytest.mark.parametrize("reference", ["schedule", "ticket", "run"])
def test_workflow_deletion_preserves_referenced_versions(actor, host, pool, version, reference):
    if reference == "schedule":
        make_schedule(version, pool, actor, host)
    elif reference == "ticket":
        WorkflowTaskTicket.objects.create(name="reusable task", workflow_version=version)
    else:
        WorkflowRun.objects.create(workflow_version=version, worker_pool=pool, triggered_by=actor)
    workflow_id = version.workflow_id
    request = APIRequestFactory().delete(f"/api/v1/automation/workflows/{workflow_id}")
    force_authenticate(request, actor)

    response = WorkflowTemplateViewSet.as_view({"delete": "destroy"})(request, pk=workflow_id)

    assert response.status_code == 400
    assert WorkflowTemplate.objects.filter(pk=workflow_id).exists()
    assert type(version).objects.filter(pk=version.pk).exists()


@pytest.mark.django_db
def test_missing_workflow_version_retires_periodic_trigger(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)
    schedule.workflow_version = None
    schedule.save(update_fields=["workflow_version"])
    occurrence = prev_cron_time(schedule.cron_expression, schedule.timezone)

    result = fire(schedule, occurrence.isoformat())

    assert result["status"] == "invalid"
    schedule.refresh_from_db()
    assert not schedule.enabled
    assert "deleted" in schedule.last_skip_reason
    assert schedule.outcomes.get().outcome == "invalid"
    assert not PeriodicTask.objects.get(name=periodic_task_name(schedule.pk)).enabled


@pytest.mark.django_db
def test_missing_workflow_version_retires_queued_catchup(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host, pending_dispatch=True)
    schedule.workflow_version = None
    schedule.save(update_fields=["workflow_version"])

    result = deliver_scheduled_catchups()

    assert result["dispatched"] == 0
    schedule.refresh_from_db()
    assert not schedule.enabled


@pytest.mark.django_db
def test_alert_keeps_original_incident_after_run_retry(failure_alert, monkeypatch):
    run, template = failure_alert
    template.body_template = "{{ run.status }}: {{ run.failureReason }}"
    template.save(update_fields=["body_template"])
    run.failure_alert = freeze_failure_alert(run.failure_alert)
    run.status = "failed"
    run.failure_reason = "original incident"
    run.save(update_fields=["failure_alert", "status", "failure_reason"])
    record = NotificationRecord.objects.get(workflow_run=run)
    sent = []

    def fake_request(method, url, headers, body, timeout):
        sent.append(json.loads(body))
        return (503, {}, "temporary failure") if len(sent) == 1 else (200, {}, "{}")

    monkeypatch.setattr("apps.jobs.node_executors._request", fake_request)
    assert not deliver_alert(record.pk)
    run.status = "running"
    run.failure_reason = ""
    run.save(update_fields=["status", "failure_reason"])
    run.status = "success"
    run.save(update_fields=["status"])
    record.refresh_from_db()
    record.next_retry_at = timezone.now() - timedelta(seconds=1)
    record.save(update_fields=["next_retry_at"])

    assert deliver_alert(record.pk)

    assert sent[0] == sent[1]
    assert sent[1]["text"]["content"] == "failed: original incident"
    record.refresh_from_db()
    assert record.status == "success"


@pytest.mark.django_db
def test_deleted_frozen_alert_channel_never_falls_back(failure_alert, monkeypatch):
    run, template = failure_alert
    run.failure_alert = freeze_failure_alert(run.failure_alert)
    run.save(update_fields=["failure_alert"])
    old_channel = template.channel
    template.channel = NotificationChannel.objects.create(
        name="another team",
        channel_type="webhook",
        secret_encrypted=encrypt_secret("https://example.test/another-team"),
    )
    template.save(update_fields=["channel"])
    old_channel.delete()
    run.status = "failed"
    run.save(update_fields=["status"])
    record = NotificationRecord.objects.get(workflow_run=run)

    assert record.status == "failed"
    assert record.channel_id is None
    assert "渠道已删除" in record.failure_reason
    assert not deliver_alert(record.pk)
