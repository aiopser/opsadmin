from django.db import transaction
from django.utils import timezone

from .models import NodeRun, WorkflowRun
from .state_machine import ExecutionLease, ExecutionStateMachine


def heartbeat_execution(run_id, task_id=None, worker=None):
    ExecutionLease.touch(run_id, task_id=task_id, worker=worker)


def recover_stale_executions(now=None):
    now = now or timezone.now()
    active_runs = WorkflowRun.objects.filter(
        status__in=[
            WorkflowRun.Status.PENDING,
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.CANCEL_REQUESTED,
        ]
    )
    recovered = 0
    for run in active_runs:
        if recover_stale_execution(run.id, now=now):
            recovered += 1
    return recovered


@transaction.atomic
def recover_stale_execution(run_id, now=None):
    """Reconcile one stale run, including when Celery is temporarily down."""
    now = now or timezone.now()
    run = WorkflowRun.objects.select_for_update().get(id=run_id)
    if run.status not in {
        WorkflowRun.Status.PENDING,
        WorkflowRun.Status.QUEUED,
        WorkflowRun.Status.RUNNING,
        WorkflowRun.Status.CANCEL_REQUESTED,
    }:
        return False

    if run.status in {WorkflowRun.Status.PENDING, WorkflowRun.Status.QUEUED}:
        if run.queue_deadline_at and run.queue_deadline_at > now:
            return False
        if not run.queue_deadline_at and not ExecutionLease.is_expired(run, now=now):
            return False
    elif run.workflow_deadline_at:
        if run.workflow_deadline_at > now:
            return False
    elif not ExecutionLease.is_expired(run, now=now):
        return False

    cancel_requested = run.status == WorkflowRun.Status.CANCEL_REQUESTED
    run.status = WorkflowRun.Status.TIMEOUT
    run.failure_reason = (
        "Cancellation could not be confirmed after worker heartbeat expired; execution outcome is unknown."
        if cancel_requested
        else "Execution worker heartbeat expired."
    )
    run.finished_at = now
    run.duration_ms = int(
        (now - (run.started_at or run.created_at)).total_seconds() * 1000
    )
    run.save(
        update_fields=[
            "status",
            "failure_reason",
            "finished_at",
            "duration_ms",
            "updated_at",
        ]
    )
    return True
