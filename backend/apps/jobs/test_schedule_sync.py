"""ScheduledJob ↔ django-celery-beat PeriodicTask sync contract."""

import json
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.automation.workflow_graph import replace_graph
from apps.cmdb.models import AssetHost
from apps.jobs.models import ScheduledJob, WorkerPool
from apps.jobs.schedule_sync import (
    periodic_task_name,
    remove_periodic_task,
    upsert_periodic_task,
)
from apps.jobs.tasks import execute_scheduled_job
from apps.jobs.views import ScheduledJobViewSet


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_superuser(
        username="sync-admin",
        password="123456",
        email="sync@example.test",
        phone="13800008888",
    )


@pytest.fixture
def host(db):
    return AssetHost.objects.create(
        hostname="sync-host",
        internal_ip="10.0.0.88",
        os_family=AssetHost.OSFamily.LINUX,
    )


@pytest.fixture
def pool(db):
    return WorkerPool.objects.create(
        code="sync", name="sync", queue_name="ansible.sync", is_default=True
    )


@pytest.fixture
def version(db):
    command = CommandAtom.objects.create(name="sync", code="sync")
    command_version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="linux_shell",
        content="echo sync",
    )
    command_version.publish(None)
    template = WorkflowTemplate.objects.create(name="sync", code="sync")
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
        "name": "sync-job",
        "workflow_version": version,
        "worker_pool": pool,
        "host_ids": [host.id],
        "created_by": actor,
    }
    fields.update(overrides)
    return ScheduledJob.objects.create(**fields)


@pytest.mark.django_db
def test_upsert_creates_periodic_task_mirror(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)

    upsert_periodic_task(schedule)

    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.task == "jobs.execute_scheduled_job"
    assert json.loads(task.kwargs)["scheduled_job_id"] == schedule.pk
    assert json.loads(task.kwargs)["schedule_token"]
    assert task.enabled is True
    assert task.description == schedule.name
    assert task.interval_id is None
    crontab = task.crontab
    assert crontab.minute == "0" and crontab.hour == "*"
    assert crontab.day_of_month == "*" and crontab.month_of_year == "*"
    assert crontab.day_of_week == "*"
    assert str(crontab.timezone) == str(ZoneInfo("Asia/Shanghai"))


@pytest.mark.django_db
def test_upsert_is_idempotent_and_reuses_crontab(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)

    upsert_periodic_task(schedule)
    upsert_periodic_task(schedule)

    assert PeriodicTask.objects.count() == 1
    assert CrontabSchedule.objects.count() == 1

    other = make_schedule(version, pool, actor, host, name="sync-job-2")
    upsert_periodic_task(other)
    assert PeriodicTask.objects.count() == 2
    assert CrontabSchedule.objects.count() == 1


@pytest.mark.django_db
def test_upsert_mirrors_cron_and_enabled_changes(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)
    upsert_periodic_task(schedule)

    schedule.cron_expression = "30 2 * * *"
    schedule.timezone = "UTC"
    schedule.enabled = False
    schedule.save(
        update_fields=["cron_expression", "timezone", "enabled", "updated_at"]
    )
    upsert_periodic_task(schedule)

    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.enabled is False
    assert task.crontab.hour == "2" and task.crontab.minute == "30"
    assert str(task.crontab.timezone) == str(ZoneInfo("UTC"))


@pytest.mark.django_db
def test_remove_periodic_task(actor, host, pool, version):
    schedule = make_schedule(version, pool, actor, host)
    upsert_periodic_task(schedule)

    remove_periodic_task(schedule.pk)

    assert not PeriodicTask.objects.filter(
        name=periodic_task_name(schedule.pk)
    ).exists()


@pytest.mark.django_db
def test_viewset_create_and_delete_sync_periodic_task(actor, host, pool, version):
    request = APIRequestFactory().post(
        "/api/v1/jobs/scheduled-jobs",
        {
            "name": "api-sync-job",
            "workflow_version": version.id,
            "host_ids": [host.id],
            "cron_expression": "*/10 * * * *",
            "timezone": "Asia/Shanghai",
            "enabled": True,
        },
        format="json",
    )
    force_authenticate(request, user=actor)
    request.user = actor

    response = ScheduledJobViewSet.as_view({"post": "create"})(request)

    assert response.status_code == 200
    schedule = ScheduledJob.objects.get()
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.enabled is True
    assert task.crontab.minute == "*/10"

    delete_request = APIRequestFactory().delete(
        f"/api/v1/jobs/scheduled-jobs/{schedule.pk}"
    )
    force_authenticate(delete_request, user=actor)
    delete_request.user = actor
    ScheduledJobViewSet.as_view({"delete": "destroy"})(delete_request, pk=schedule.pk)

    assert not ScheduledJob.objects.filter(pk=schedule.pk).exists()
    assert not PeriodicTask.objects.filter(
        name=periodic_task_name(schedule.pk)
    ).exists()


@pytest.mark.django_db
def test_invalid_schedule_disable_mirrors_into_periodic_task(
    actor, host, pool, version
):
    template = WorkflowTemplate.objects.create(name="sync-unpub", code="sync-unpub")
    draft_version = WorkflowVersion.objects.create(workflow=template, version=1)
    schedule = make_schedule(version=draft_version, pool=pool, actor=actor, host=host)
    upsert_periodic_task(schedule)

    from apps.jobs.cron import prev_cron_time

    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    result = execute_scheduled_job(**json.loads(task.kwargs), scheduled_for=prev_cron_time(schedule.cron_expression, schedule.timezone).isoformat())

    assert result["status"] == "invalid"
    schedule.refresh_from_db()
    assert schedule.enabled is False
    task = PeriodicTask.objects.get(name=periodic_task_name(schedule.pk))
    assert task.enabled is False
