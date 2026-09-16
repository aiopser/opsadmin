"""T13 scheduled-job dispatch policies: overlap, misfire, skip reasons and
ownership transfer."""

from datetime import timedelta

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
from apps.jobs.models import ScheduledJob, WorkerPool, WorkflowRun
from apps.jobs.application.runs import create_workflow_run
from apps.jobs.tasks import dispatch_scheduled_jobs


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
        primary_ip="10.0.0.77",
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
    return ScheduledJob.objects.create(**fields)


def dispatch():
    return dispatch_scheduled_jobs()


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

    result = dispatch()

    assert result["dispatched"] == 0
    assert result["skipped"] == 1
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

    result = dispatch()

    assert result["dispatched"] == 1
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

    # Tick 1: previous run still active -> queue one catch-up dispatch.
    result = dispatch()
    assert result["dispatched"] == 0
    schedule.refresh_from_db()
    assert schedule.pending_dispatch is True
    assert schedule.last_skip_reason == "overlap queued: previous run still active"
    assert WorkflowRun.objects.count() == 1

    # Tick 2: previous run finished -> exactly one catch-up run fires.
    WorkflowRun.objects.filter(pk=previous.pk).update(status=WorkflowRun.Status.SUCCESS)
    result = dispatch()
    assert result["dispatched"] == 1
    schedule.refresh_from_db()
    assert schedule.pending_dispatch is False
    assert schedule.last_skip_reason == ""
    assert WorkflowRun.objects.count() == 2

    # Tick 3: no duplicate catch-up dispatch.
    result = dispatch()
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
        misfire_policy=ScheduledJob.MisfirePolicy.SKIP,
        misfire_grace_seconds=60,
        next_run_at=timezone.now() - timedelta(hours=2),
    )

    result = dispatch()

    assert result["dispatched"] == 0
    assert result["skipped"] == 1
    schedule.refresh_from_db()
    assert WorkflowRun.objects.count() == 0
    assert schedule.next_run_at > timezone.now()
    assert schedule.last_skip_reason.startswith("misfire skipped: overdue by ")


@pytest.mark.django_db
def test_misfire_fire_still_dispatches_late_run(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    make_schedule(
        version,
        pool,
        actor,
        host,
        misfire_policy=ScheduledJob.MisfirePolicy.FIRE,
        misfire_grace_seconds=60,
        next_run_at=timezone.now() - timedelta(hours=2),
    )

    result = dispatch()

    assert result["dispatched"] == 1
    assert WorkflowRun.objects.count() == 1


@pytest.mark.django_db
def test_within_grace_window_occurrence_fires_normally(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    make_schedule(
        version,
        pool,
        actor,
        host,
        misfire_policy=ScheduledJob.MisfirePolicy.SKIP,
        misfire_grace_seconds=3600,
        next_run_at=timezone.now() - timedelta(minutes=2),
    )

    result = dispatch()

    assert result["dispatched"] == 1


@pytest.mark.django_db
def test_orphan_schedule_ownership_transfers_to_active_superuser(
    actor, host, pool, version, monkeypatch
):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    departed = get_user_model().objects.create_user(
        username="departed-owner", password="pass-123456", job_status=False
    )
    make_schedule(version, pool, departed, host)

    result = dispatch()

    schedule = ScheduledJob.objects.get()
    assert schedule.created_by_id == actor.id
    assert result["ownershipTransferred"] == 1
    assert result["dispatched"] == 1
    run = WorkflowRun.objects.get()
    assert run.triggered_by_id == actor.id


@pytest.mark.django_db
def test_dispatch_rejection_records_skip_reason(actor, host, pool, version, monkeypatch):
    monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
    make_schedule(version, pool, actor, host, host_ids=[host.id + 10000])

    result = dispatch()

    assert result["dispatched"] == 0
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

    dispatch()

    schedule.refresh_from_db()
    assert schedule.last_skip_reason == ""
    assert schedule.last_workflow_run is not None
