from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.db import transaction
from django.utils import timezone

from apps.jobs.application.dispatch import deliver_pending_dispatches, dispatch_after_commit, enqueue_workflow_run
from apps.jobs.models import JobEventLog, NodeRun, NodeRunAttempt, WorkerPool, WorkflowRun
from apps.jobs.tasks import _claim_node_run, execute_node
from apps.jobs.workflow_engine import plan_dispatch


@pytest.fixture
def run():
    pool = WorkerPool.objects.create(code="dispatch-test", name="Test", queue_name="test")
    return WorkflowRun.objects.create(worker_pool=pool, status="queued")


@pytest.mark.django_db(transaction=True)
def test_rollback_does_not_publish(run):
    with patch("apps.jobs.tasks.run_workflow.apply_async") as publish:
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                dispatch_after_commit(run.id)
                raise RuntimeError("rollback")
        publish.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_publication_waits_for_commit(run):
    with patch("apps.jobs.tasks.run_workflow.apply_async", return_value=SimpleNamespace(id="task")) as publish:
        with transaction.atomic():
            dispatch_after_commit(run.id)
            publish.assert_not_called()
        publish.assert_called_once()


@pytest.mark.django_db
def test_broker_failure_is_durable_and_recoverable(run):
    with patch("apps.jobs.tasks.run_workflow.apply_async", side_effect=ConnectionError("password=never-store")):
        assert not enqueue_workflow_run(run.id)["dispatched"]
    run.refresh_from_db()
    assert run.status == "queued"
    event = JobEventLog.objects.get(workflow_run=run)
    assert event.event_type == "dispatch_failed"
    assert "never-store" not in str(event.payload)
    with patch("apps.jobs.tasks.run_workflow.apply_async", return_value=SimpleNamespace(id="task")):
        future = timezone.now() + timedelta(seconds=60)
        assert deliver_pending_dispatches(now=future) == 1
        assert deliver_pending_dispatches(now=future) == 0


@pytest.mark.django_db
def test_claim_is_fenced_by_attempt_and_duplicates(run):
    node = NodeRun.objects.create(workflow_run=run, status="queued", attempt_count=2)
    NodeRunAttempt.objects.create(node_run=node, attempt=2)
    assert not _claim_node_run(node.id, "stale", timezone.now(), 1)
    assert _claim_node_run(node.id, "first", timezone.now(), 2)
    assert not _claim_node_run(node.id, "duplicate", timezone.now(), 2)


@pytest.mark.django_db
def test_old_delivery_cannot_execute_new_attempt(run):
    node = NodeRun.objects.create(workflow_run=run, status="queued", attempt_count=2)
    with patch("apps.jobs.tasks.execute_ansible_node") as execute:
        execute_node(node.id, 1)
        execute.assert_not_called()
    node.refresh_from_db()
    assert node.status == "queued"


@pytest.mark.django_db
def test_cancel_waits_for_running_worker_confirmation(run):
    run.status = "cancel_requested"
    run.save()
    node = NodeRun.objects.create(workflow_run=run, status="running", attempt_count=1)
    assert plan_dispatch(run.id) == []
    run.refresh_from_db()
    node.refresh_from_db()
    assert run.status == "cancel_requested"
    assert node.status == "running"


@pytest.mark.django_db
def test_retry_creates_new_attempt_and_old_delivery_stays_fenced(run):
    from apps.jobs.application.retry import retry_failed_node
    node = NodeRun.objects.create(workflow_run=run, status="failed", attempt_count=1)
    old = NodeRunAttempt.objects.create(node_run=node, attempt=1, status="failed")
    result = retry_failed_node(node.id)
    assert result.attempt_count == 2
    assert result.status == "queued"
    assert NodeRunAttempt.objects.get(node_run=node, attempt=2).status == "queued"
    old.refresh_from_db()
    assert old.status == "failed"
    assert not _claim_node_run(node.id, "late", timezone.now(), 1)


@pytest.mark.django_db
def test_cancel_request_prevents_new_claim(run):
    run.status = "cancel_requested"
    run.save()
    node = NodeRun.objects.create(workflow_run=run, status="queued", attempt_count=1)
    assert not _claim_node_run(node.id, "late", timezone.now(), 1)


@pytest.mark.django_db
def test_recovery_does_not_claim_worker_cancellation_or_reexecute(run):
    from apps.jobs.recovery import recover_stale_execution
    run.status = "cancel_requested"
    run.workflow_deadline_at = timezone.now() - timedelta(seconds=1)
    run.save()
    NodeRun.objects.create(workflow_run=run, status="running", attempt_count=1)
    with patch("apps.jobs.tasks.execute_node.apply_async") as execute:
        assert recover_stale_execution(run.id)
        execute.assert_not_called()
    run.refresh_from_db()
    assert run.status == "timeout"
    assert "could not be confirmed" in run.failure_reason
