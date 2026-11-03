import json
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.jobs.cron import next_cron_time, prev_cron_time
from apps.jobs.models import ScheduledJob, WorkflowRun
from apps.jobs.schedule_sync import periodic_task_name, upsert_periodic_task
from apps.jobs.tasks import execute_scheduled_job
from apps.jobs.test_schedule_policy import actor, host, pool, version, make_schedule


def message(schedule, slot):
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    return {**json.loads(task.kwargs), "scheduled_for": slot.isoformat()}


@pytest.mark.django_db
def test_actual_scheduler_honors_job_timezone_with_naive_database(
    actor, host, pool, version
):
    from apps.jobs.scheduler import ScheduledJobEntry

    schedule = make_schedule(version, pool, actor, host, timezone="UTC")
    upsert_periodic_task(schedule)
    entry = ScheduledJobEntry(
        PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    )
    assert str(entry.schedule.tz) == "UTC"


@pytest.mark.django_db
def test_metadata_edit_preserves_cursor_and_delivery_token(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)
    upsert_periodic_task(schedule)
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    cursor = datetime.now(dt_timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    PeriodicTask.objects.filter(pk=task.pk).update(last_run_at=cursor)
    token = json.loads(task.kwargs)["schedule_token"]
    schedule.name = "renamed"
    upsert_periodic_task(schedule)
    task.refresh_from_db()
    assert task.last_run_at == cursor
    assert json.loads(task.kwargs)["schedule_token"] == token


@pytest.mark.django_db
def test_initializing_delivery_token_preserves_existing_cursor(
    actor, host, pool, version
):
    schedule = make_schedule(version, pool, actor, host)
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    cursor = datetime.now(dt_timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    PeriodicTask.objects.filter(pk=task.pk).update(
        kwargs=json.dumps({"scheduled_job_id": schedule.pk}),
        last_run_at=cursor,
    )
    upsert_periodic_task(schedule)
    task.refresh_from_db()
    assert task.last_run_at == cursor
    assert json.loads(task.kwargs)["schedule_token"]


@pytest.mark.django_db
def test_rejected_catchup_is_finalized_instead_of_retried_forever(
    actor, host, pool, version, monkeypatch
):
    from apps.jobs.tasks import deliver_scheduled_catchups
    from apps.jobs.models import ScheduledJobOutcome

    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    previous = WorkflowRun.objects.create(
        worker_pool=pool, triggered_by=actor, status="running"
    )
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression="* * * * *",
        overlap_policy="queue",
        last_workflow_run=previous,
    )
    execute_scheduled_job(
        **message(schedule, prev_cron_time(schedule.cron_expression, schedule.timezone))
    )
    WorkflowRun.objects.filter(pk=previous.pk).update(status="success")
    schedule.host_ids = [host.pk + 10000]
    schedule.save(update_fields=["host_ids"])
    deliver_scheduled_catchups()
    schedule.refresh_from_db()
    assert not schedule.pending_dispatch
    assert schedule.outcomes.get().outcome == ScheduledJobOutcome.Outcome.INVALID


@pytest.mark.django_db
def test_redelivery_after_minute_boundary_is_deduplicated(
    actor, host, pool, version, monkeypatch
):
    clock = {"now": timezone.now().replace(second=5, microsecond=0)}
    monkeypatch.setattr("apps.jobs.tasks.timezone.now", lambda: clock["now"])
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version, pool, actor, host, cron_expression="* * * * *", overlap_policy="allow"
    )
    upsert_periodic_task(schedule)
    payload = message(
        schedule,
        prev_cron_time(schedule.cron_expression, schedule.timezone, clock["now"]),
    )
    assert execute_scheduled_job(**payload)["status"] == "dispatched"
    clock["now"] += timedelta(minutes=1)
    assert execute_scheduled_job(**payload)["status"] == "duplicate"
    assert WorkflowRun.objects.count() == 1


@pytest.mark.django_db
def test_delayed_message_uses_original_slot_for_misfire(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    now = timezone.now()
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression="* * * * *",
        misfire_policy="skip",
        misfire_grace_seconds=30,
    )
    upsert_periodic_task(schedule)
    result = execute_scheduled_job(
        **message(schedule, now.replace(second=0, microsecond=0) - timedelta(hours=1))
    )
    assert result["status"] == "misfire_skipped"
    assert WorkflowRun.objects.count() == 0


@pytest.mark.django_db
def test_cron_edit_rejects_queued_message_from_old_definition(
    actor, host, pool, version
):
    schedule = make_schedule(version, pool, actor, host)
    upsert_periodic_task(schedule)
    payload = message(
        schedule, prev_cron_time(schedule.cron_expression, schedule.timezone)
    )
    schedule.cron_expression = "*/10 * * * *"
    upsert_periodic_task(schedule)
    assert execute_scheduled_job(**payload)["status"] == "stale"
    assert WorkflowRun.objects.count() == 0


@pytest.mark.django_db
def test_queue_policy_advances_next_time_and_claims_each_occurrence(
    actor, host, pool, version
):
    previous = WorkflowRun.objects.create(
        worker_pool=pool, triggered_by=actor, status="running"
    )
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression="* * * * *",
        overlap_policy="queue",
        last_workflow_run=previous,
    )
    upsert_periodic_task(schedule)
    slot = prev_cron_time(schedule.cron_expression, schedule.timezone)
    execute_scheduled_job(**message(schedule, slot))
    schedule.refresh_from_db()
    assert schedule.pending_dispatch
    assert schedule.next_run_at > timezone.now()


def test_calendar_matches_beat_and_semantics():
    from celery.schedules import crontab

    anchor = datetime(2026, 10, 18, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    native = crontab(
        minute="0", hour="0", day_of_month="1", day_of_week="1", nowfun=lambda: anchor
    )
    last, delta, _ = native.remaining_delta(anchor)
    assert next_cron_time("0 0 1 * 1", "Asia/Shanghai", anchor).replace(
        tzinfo=None
    ) == (last + delta).replace(tzinfo=None)


@pytest.mark.django_db
def test_missing_occurrence_is_rejected_without_creating_run(
    actor, host, pool, version
):
    schedule = make_schedule(version, pool, actor, host)
    assert execute_scheduled_job(schedule.pk)["status"] == "invalid_trigger"
    assert WorkflowRun.objects.count() == 0


@pytest.mark.django_db
def test_scheduler_freezes_original_slot_before_cursor_advances(
    actor, host, pool, version, monkeypatch
):
    from django_celery_beat.schedulers import DatabaseScheduler
    from apps.jobs.scheduler import ScheduledJobEntry, ScheduledJobScheduler

    schedule = make_schedule(
        version, pool, actor, host, cron_expression="* * * * *", timezone="UTC"
    )
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    anchor = datetime(2026, 10, 16, 1, 59, 30)
    task.last_run_at = anchor
    task.save()
    entry = ScheduledJobEntry(task)
    next(entry)  # Beat tick reserves the next entry before publishing the old one.
    published = []

    def capture(self, delivery, **kwargs):
        published.append(delivery.kwargs)

    monkeypatch.setattr(DatabaseScheduler, "apply_async", capture)
    ScheduledJobScheduler.apply_async(
        object.__new__(ScheduledJobScheduler), entry, advance=False
    )
    assert published[0]["scheduled_for"] == "2026-10-16T02:00:00+00:00"
    assert published[0]["schedule_token"] == json.loads(task.kwargs)["schedule_token"]
    assert "scheduled_for" not in entry.kwargs


@pytest.mark.django_db
def test_history_filters_by_schedule_and_trigger_type(
    actor, host, pool, version, monkeypatch
):
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.jobs.views import WorkflowRunViewSet

    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, cron_expression="* * * * *")
    result = execute_scheduled_job(
        **message(schedule, prev_cron_time(schedule.cron_expression, schedule.timezone))
    )
    assert result["status"] == "dispatched"
    WorkflowRun.objects.create(
        worker_pool=pool, triggered_by=actor, trigger_type="manual"
    )
    request = APIRequestFactory().get(
        "/api/v1/tasks/runs",
        {"scheduledJobId": schedule.pk, "triggerType": "scheduled"},
    )
    force_authenticate(request, user=actor)
    response = WorkflowRunViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200
    assert len(response.data["data"]) == 1
    record = response.data["data"][0]
    assert record["triggerType"] == "scheduled"
    assert record["scheduledJobName"] == schedule.name
    assert record["executionKind"] == "workflow"
