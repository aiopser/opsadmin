"""T13 scheduled-job dispatch policies: overlap, misfire, skip reasons and
ownership transfer.

Since the django-celery-beat migration each occurrence is fired as
``execute_scheduled_job``; QUEUE catch-ups are delivered by the
``deliver_scheduled_catchups`` sweeper.
"""

from datetime import timedelta
import json
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.automation.workflow_graph import replace_graph
from apps.cmdb.models import AssetHost
from apps.jobs.cron import prev_cron_time
from apps.jobs.models import ScheduledJob, ScheduledJobOutcome, WorkerPool, WorkflowRun
from apps.jobs.application.runs import create_workflow_run
from apps.jobs.tasks import deliver_scheduled_catchups, execute_scheduled_job
from apps.jobs.schedule_sync import periodic_task_name, upsert_periodic_task
from django_celery_beat.models import PeriodicTask


def valid_graph():
    return {
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


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_superuser(
        username="policy-admin",
        password="123456",
        email="policy@example.test",
        phone="13800007777",
    )


@pytest.fixture
def host(db):
    return AssetHost.objects.create(
        hostname="policy-host",
        internal_ip="10.0.0.77",
        os_family=AssetHost.OSFamily.LINUX,
    )


@pytest.fixture
def pool(db):
    return WorkerPool.objects.create(
        code="policy", name="policy", queue_name="ansible.policy"
    )


@pytest.fixture
def version(db):
    command = CommandAtom.objects.create(name="policy", code="policy")
    command_version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="linux_shell",
        content="echo policy",
    )
    command_version.publish(None)
    template = WorkflowTemplate.objects.create(name="policy", code="policy")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = valid_graph()
    graph["nodes"][1]["commandVersionId"] = command_version.pk
    assert replace_graph(version, graph) == []
    version.publish(None)
    return version


def overdue_daily_cron(minutes_ago=120, tz_name="Asia/Shanghai"):
    """Daily cron expression whose only recent slot is ``minutes_ago`` old.

    Derives the slot from the schedule timezone so the misfire assertions are
    deterministic regardless of when the suite runs.
    """
    anchor = timezone.now() - timedelta(minutes=minutes_ago)
    slot = prev_cron_time("* * * * *", tz_name, anchor)
    local = slot.astimezone(ZoneInfo(tz_name))
    return f"{local.minute} {local.hour} * * *"


def make_schedule(version, pool, actor, host, **overrides):
    fields = {
        "name": "policy-job",
        "workflow_version": version,
        "worker_pool": pool,
        "host_ids": [host.id],
        "created_by": actor,
        "next_run_at": timezone.now() - timedelta(minutes=2),
    }
    fields.update(overrides)
    schedule = ScheduledJob.objects.create(**fields)
    upsert_periodic_task(schedule)
    return schedule


def fire(schedule):
    payload = json.loads(PeriodicTask.objects.get(name=periodic_task_name(schedule.pk)).kwargs)
    return execute_scheduled_job(**payload, scheduled_for=prev_cron_time(schedule.cron_expression, schedule.timezone).isoformat())


@pytest.mark.django_db
def test_overlap_skip_defers_until_previous_run_finishes(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, overlap_policy=ScheduledJob.OverlapPolicy.SKIP)
    previous = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    schedule.last_workflow_run = previous
    schedule.save(update_fields=["last_workflow_run", "updated_at"])

    result = fire(schedule)

    assert result["status"] == "overlap_skipped"
    schedule.refresh_from_db()
    assert WorkflowRun.objects.count() == 1
    assert schedule.next_run_at > timezone.now()
    assert schedule.last_skip_reason == "overlap skipped: previous run still active"


@pytest.mark.django_db
def test_overlap_allow_dispatches_beside_active_run(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, overlap_policy=ScheduledJob.OverlapPolicy.ALLOW)
    previous = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    schedule.last_workflow_run = previous
    schedule.save(update_fields=["last_workflow_run", "updated_at"])

    result = fire(schedule)

    assert result["status"] == "dispatched"
    schedule.refresh_from_db()
    assert WorkflowRun.objects.count() == 2
    assert schedule.last_skip_reason == ""
    assert schedule.last_workflow_run_id != previous.id


@pytest.mark.django_db
def test_overlap_queue_dispatches_once_after_previous_finishes(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, overlap_policy=ScheduledJob.OverlapPolicy.QUEUE)
    previous = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    schedule.last_workflow_run = previous
    schedule.save(update_fields=["last_workflow_run", "updated_at"])

    # Beat fires while the previous run is still active -> queue one catch-up.
    result = fire(schedule)
    assert result["status"] == "overlap_skipped"
    schedule.refresh_from_db()
    assert schedule.pending_dispatch is True
    assert schedule.last_skip_reason == "overlap queued: previous run still active"
    assert WorkflowRun.objects.count() == 1

    # Sweeper tick while the previous run is still active -> nothing fires.
    result = deliver_scheduled_catchups()
    assert result["dispatched"] == 0
    assert WorkflowRun.objects.count() == 1

    # Previous run finished -> exactly one catch-up run fires.
    WorkflowRun.objects.filter(pk=previous.pk).update(status=WorkflowRun.Status.SUCCESS)
    result = deliver_scheduled_catchups()
    assert result["dispatched"] == 1
    schedule.refresh_from_db()
    assert schedule.pending_dispatch is False
    assert schedule.last_skip_reason == ""
    assert WorkflowRun.objects.count() == 2

    # Next sweeper tick: no duplicate catch-up dispatch.
    result = deliver_scheduled_catchups()
    assert result["dispatched"] == 0
    assert WorkflowRun.objects.count() == 2


@pytest.mark.django_db
def test_misfire_skip_jumps_to_next_cron_slot(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression=overdue_daily_cron(minutes_ago=120),
        misfire_policy=ScheduledJob.MisfirePolicy.SKIP,
        misfire_grace_seconds=60,
    )

    result = fire(schedule)

    assert result["status"] == "misfire_skipped"
    schedule.refresh_from_db()
    assert WorkflowRun.objects.count() == 0
    assert schedule.next_run_at > timezone.now()
    assert schedule.last_skip_reason.startswith("misfire skipped: overdue by ")


@pytest.mark.django_db
def test_misfire_fire_still_dispatches_late_run(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression=overdue_daily_cron(minutes_ago=120),
        misfire_policy=ScheduledJob.MisfirePolicy.FIRE,
        misfire_grace_seconds=60,
    )

    result = fire(schedule)

    assert result["status"] == "dispatched"
    assert WorkflowRun.objects.count() == 1


@pytest.mark.django_db
def test_within_grace_window_occurrence_fires_normally(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression=overdue_daily_cron(minutes_ago=5),
        misfire_policy=ScheduledJob.MisfirePolicy.SKIP,
        misfire_grace_seconds=3600,
    )

    result = fire(schedule)

    assert result["status"] == "dispatched"


@pytest.mark.django_db
def test_inactive_schedule_is_skipped_silently(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, enabled=False)

    result = fire(schedule)

    assert result["status"] == "inactive"
    assert WorkflowRun.objects.count() == 0


@pytest.mark.django_db
def test_orphan_schedule_ownership_remains_revoked_without_automatic_elevation(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    departed = get_user_model().objects.create_user(
        username="departed-owner", password="pass-123456", job_status=False
    )
    schedule = make_schedule(version, pool, departed, host, pending_dispatch=True)

    result = deliver_scheduled_catchups()

    schedule = ScheduledJob.objects.get()
    assert schedule.created_by_id == departed.id
    assert result["ownershipTransferred"] == 0
    assert result["dispatched"] == 0
    assert "dispatch rejected" in schedule.last_skip_reason
    assert not WorkflowRun.objects.exists()


@pytest.mark.django_db
def test_dispatch_rejection_records_skip_reason(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host, host_ids=[host.id + 10000])

    result = fire(schedule)

    assert result["status"] == "rejected"
    schedule = ScheduledJob.objects.get()
    assert schedule.last_skip_reason.startswith("dispatch rejected")
    assert schedule.next_run_at > timezone.now()


@pytest.mark.django_db
def test_successful_dispatch_clears_previous_skip_reason(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version, pool, actor, host, last_skip_reason="overlap skipped: previous run still active"
    )

    fire(schedule)

    schedule.refresh_from_db()
    assert schedule.last_skip_reason == ""
    assert schedule.last_workflow_run is not None


@pytest.mark.django_db
def test_successful_dispatch_records_outcome(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(version, pool, actor, host)

    fire(schedule)

    schedule.refresh_from_db()
    outcome = ScheduledJobOutcome.objects.get(scheduled_job=schedule)
    assert outcome.outcome == ScheduledJobOutcome.Outcome.DISPATCHED
    assert outcome.workflow_run_id == schedule.last_workflow_run_id


@pytest.mark.django_db
def test_overlap_skip_records_outcome(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version, pool, actor, host, overlap_policy=ScheduledJob.OverlapPolicy.SKIP
    )
    previous = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    schedule.last_workflow_run = previous
    schedule.save(update_fields=["last_workflow_run", "updated_at"])

    fire(schedule)

    outcome = ScheduledJobOutcome.objects.get(scheduled_job=schedule)
    assert outcome.outcome == ScheduledJobOutcome.Outcome.OVERLAP_SKIPPED
    assert outcome.reason == "overlap skipped: previous run still active"
    assert outcome.workflow_run_id is None


@pytest.mark.django_db
def test_overlap_queue_outcome_is_rewritten_to_dispatched(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version, pool, actor, host, overlap_policy=ScheduledJob.OverlapPolicy.QUEUE
    )
    previous = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    schedule.last_workflow_run = previous
    schedule.save(update_fields=["last_workflow_run", "updated_at"])

    fire(schedule)  # queued while the previous run is still active
    outcome = ScheduledJobOutcome.objects.get(scheduled_job=schedule)
    assert outcome.outcome == ScheduledJobOutcome.Outcome.OVERLAP_QUEUED
    queued_for = outcome.scheduled_for

    WorkflowRun.objects.filter(pk=previous.pk).update(status=WorkflowRun.Status.SUCCESS)
    deliver_scheduled_catchups()  # the catch-up run fires for the same occurrence

    assert ScheduledJobOutcome.objects.filter(scheduled_job=schedule).count() == 1
    outcome.refresh_from_db()
    schedule.refresh_from_db()
    assert outcome.scheduled_for == queued_for
    assert outcome.outcome == ScheduledJobOutcome.Outcome.DISPATCHED
    assert outcome.workflow_run_id == schedule.last_workflow_run_id


@pytest.mark.django_db
def test_misfire_skip_records_outcome(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    schedule = make_schedule(
        version,
        pool,
        actor,
        host,
        cron_expression=overdue_daily_cron(minutes_ago=120),
        misfire_policy=ScheduledJob.MisfirePolicy.SKIP,
        misfire_grace_seconds=60,
    )

    fire(schedule)

    outcome = ScheduledJobOutcome.objects.get(scheduled_job=schedule)
    assert outcome.outcome == ScheduledJobOutcome.Outcome.MISFIRE_SKIPPED
    assert outcome.reason.startswith("misfire skipped: overdue by ")
