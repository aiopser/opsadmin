"""One-off ScheduledJob contract: clocked mirror, single fire, retirement.

A one-off job stores its single occurrence in ``run_at`` (application-local
convention) and mirrors it into beat as a ClockedSchedule plus ``one_off=True``
(beat's naive-UTC convention).  Firing it must create exactly one run and then
retire the job; a job past ``expires_at`` must never start a run.
"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_celery_beat.models import ClockedSchedule, CrontabSchedule, PeriodicTask
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.automation.workflow_graph import replace_graph
from apps.cmdb.models import AssetHost
from apps.jobs.cron import celery_datetime, celery_instant, prev_cron_time
from apps.jobs.models import ScheduledJob, ScheduledJobOutcome, WorkerPool, WorkflowRun
from apps.jobs.schedule_sync import periodic_task_name, upsert_periodic_task
from apps.jobs.tasks import execute_scheduled_job
from apps.jobs.views import ScheduledJobViewSet


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_superuser(
        username="one-off-admin",
        password="123456",
        email="one-off@example.test",
        phone="13800006666",
    )


@pytest.fixture
def host(db):
    return AssetHost.objects.create(
        hostname="one-off-host",
        internal_ip="10.0.0.66",
        os_family=AssetHost.OSFamily.LINUX,
    )


@pytest.fixture
def pool(db):
    return WorkerPool.objects.create(
        code="one-off", name="one-off", queue_name="ansible.one-off", is_default=True
    )


@pytest.fixture
def version(db):
    command = CommandAtom.objects.create(name="one-off", code="one-off")
    command_version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="linux_shell",
        content="echo one-off",
    )
    command_version.publish(None)
    template = WorkflowTemplate.objects.create(name="one-off", code="one-off")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "work", "type": "command", "timeoutSeconds": 60},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "work"},
            {"id": "b", "source": "work", "target": "end"},
        ],
    }
    graph["nodes"][1]["commandVersionId"] = command_version.pk
    assert replace_graph(version, graph) == []
    version.publish(None)
    return version


def make_schedule(version, pool, actor, host, **overrides):
    fields = {
        "name": "one-off-job",
        "workflow_version": version,
        "worker_pool": pool,
        "host_ids": [host.id],
        "created_by": actor,
    }
    fields.update(overrides)
    schedule = ScheduledJob.objects.create(**fields)
    upsert_periodic_task(schedule)
    return schedule


def clocked_occurrence(schedule):
    """The ``scheduled_for`` payload beat would deliver for a one-off job."""
    return celery_instant(celery_datetime(schedule.run_at)).isoformat()


def fire(schedule, scheduled_for):
    payload = json.loads(
        PeriodicTask.objects.get(name=periodic_task_name(schedule.pk)).kwargs
    )
    return execute_scheduled_job(**payload, scheduled_for=scheduled_for)


@pytest.mark.django_db
def test_one_off_mirrors_clocked_schedule(actor, host, pool, version):
    run_at = timezone.now() + timedelta(hours=3)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        schedule_type=ScheduledJob.ScheduleType.ONCE,
        run_at=run_at,
    )

    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.crontab_id is None
    assert task.clocked_id is not None
    assert task.one_off is True
    # Beat reads the clocked moment as naive UTC, so the local run_at must be
    # shifted rather than stored verbatim.
    assert task.clocked.clocked_time == celery_datetime(run_at)
    assert CrontabSchedule.objects.count() == 0


@pytest.mark.django_db
def test_switching_type_rewrites_the_mirror(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)
    periodic_task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert periodic_task.crontab_id is not None

    schedule.schedule_type = ScheduledJob.ScheduleType.ONCE
    schedule.run_at = timezone.now() + timedelta(hours=1)
    schedule.save(update_fields=["schedule_type", "run_at", "updated_at"])
    upsert_periodic_task(schedule)

    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.crontab_id is None
    assert task.one_off is True
    assert ClockedSchedule.objects.filter(periodictask__isnull=True).count() == 0


@pytest.mark.django_db
def test_one_off_fires_once_then_retires(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    run_at = timezone.now() - timedelta(minutes=1)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        schedule_type=ScheduledJob.ScheduleType.ONCE,
        run_at=run_at,
    )

    result = fire(schedule, clocked_occurrence(schedule))

    assert result["status"] == "dispatched"
    schedule.refresh_from_db()
    assert WorkflowRun.objects.count() == 1
    assert schedule.last_workflow_run_id is not None
    # Retired: no next occurrence, no longer enabled, and beat stopped.
    assert schedule.enabled is False
    assert schedule.next_run_at is None
    assert schedule.last_skip_reason == ""
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.enabled is False
    assert ScheduledJobOutcome.objects.get(scheduled_job=schedule).outcome == "dispatched"

    # A redelivered or duplicate trigger after retirement must not run again.
    assert fire(schedule, clocked_occurrence(schedule))["status"] == "inactive"
    assert WorkflowRun.objects.count() == 1


@pytest.mark.django_db
def test_one_off_rejects_a_foreign_occurrence(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        schedule_type=ScheduledJob.ScheduleType.ONCE,
        run_at=timezone.now() - timedelta(minutes=1),
    )

    stray = celery_instant(celery_datetime(schedule.run_at + timedelta(hours=2)))

    assert fire(schedule, stray.isoformat())["status"] == "invalid_trigger"
    assert WorkflowRun.objects.count() == 0


@pytest.mark.django_db
def test_expired_schedule_retires_without_running(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        expires_at=timezone.now() - timedelta(minutes=1),
    )
    scheduled_for = prev_cron_time(
        schedule.cron_expression, schedule.timezone
    ).isoformat()

    result = fire(schedule, scheduled_for)

    assert result["status"] == "expired"
    schedule.refresh_from_db()
    assert schedule.enabled is False
    assert schedule.next_run_at is None
    assert WorkflowRun.objects.count() == 0
    assert ScheduledJobOutcome.objects.get(scheduled_job=schedule).outcome == "expired"
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.enabled is False


@pytest.mark.django_db
def test_create_one_off_via_api_plans_run_at(actor, host, pool, version):
    run_at = timezone.now() + timedelta(hours=2)
    request = APIRequestFactory().post(
        "/api/v1/jobs/scheduled-jobs",
        {
            "name": "api-one-off",
            "workflow_version": version.id,
            "host_ids": [host.id],
            "schedule_type": "once",
            "run_at": run_at.isoformat(),
            "enabled": True,
        },
        format="json",
    )
    force_authenticate(request, user=actor)
    request.user = actor

    response = ScheduledJobViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 200
    schedule = ScheduledJob.objects.get(name="api-one-off")
    assert schedule.next_run_at == run_at
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.one_off is True and task.crontab_id is None


@pytest.mark.django_db
def test_create_one_off_requires_future_run_at(actor, host, pool, version):
    view = ScheduledJobViewSet.as_view({"post": "create"})
    base_payload = {
        "name": "bad-one-off",
        "workflow_version": version.id,
        "host_ids": [host.id],
        "schedule_type": "once",
    }

    for run_at, field in (
        (None, "run_at"),
        ((timezone.now() - timedelta(hours=1)).isoformat(), "run_at"),
    ):
        payload = {**base_payload}
        if run_at is not None:
            payload["run_at"] = run_at
        request = APIRequestFactory().post(
            "/api/v1/jobs/scheduled-jobs", payload, format="json"
        )
        force_authenticate(request, user=actor)
        request.user = actor

        response = view(request)

        assert response.status_code == 400
        assert field in json.dumps(response.data["msg"])
    assert not ScheduledJob.objects.filter(name="bad-one-off").exists()
