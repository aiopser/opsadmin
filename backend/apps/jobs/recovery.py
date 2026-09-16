"""Stale-run reconciliation: worker loss, queue/execution timeouts, unknown outcomes.

Terminal handling is centralized in `finalize_stale_run`: one entry point that
applies the state-machine transition, settles node runs and attempts, and
records the terminal audit event. Outcomes that cannot be confirmed remotely
are marked as unknown and never retried automatically — deployment or restart
actions must not repeat themselves; an operator decides.
"""

from django.db import transaction
from django.utils import timezone

from .events import append_run_event
from .models import NodeRun, NodeRunAttempt, WorkflowRun
from .state_machine import (
    ExecutionLease,
    ExecutionStateMachine,
    InvalidExecutionTransition,
)


class StaleFinalizeKind:
    """Why a stale run is being terminalized."""

    QUEUE_TIMEOUT = "queue_timeout"
    EXECUTION_TIMEOUT = "execution_timeout"
    WORKER_LOST = "worker_lost"


_FAILURE_REASONS = {
    StaleFinalizeKind.QUEUE_TIMEOUT: (
        "Queued execution timed out before a worker claimed it."
    ),
    StaleFinalizeKind.EXECUTION_TIMEOUT: (
        "Workflow execution exceeded its overall deadline; "
        "the remote outcome is unknown."
    ),
    StaleFinalizeKind.WORKER_LOST: (
        "Worker heartbeat expired; remote execution outcome is unknown."
    ),
}

_CANCELLATION_REASONS = {
    StaleFinalizeKind.EXECUTION_TIMEOUT: (
        "Cancellation could not be confirmed before the execution deadline; "
        "the outcome is unknown."
    ),
    StaleFinalizeKind.WORKER_LOST: (
        "Cancellation could not be confirmed after worker heartbeat expired; "
        "execution outcome is unknown."
    ),
}

_FINALIZE_EVENT_TYPES = {
    StaleFinalizeKind.QUEUE_TIMEOUT: "queue_timeout",
    StaleFinalizeKind.EXECUTION_TIMEOUT: "workflow_timeout",
    StaleFinalizeKind.WORKER_LOST: "worker_lost_contact",
}

_ACTIVE_RUN_STATUSES = [
    WorkflowRun.Status.PENDING,
    WorkflowRun.Status.QUEUED,
    WorkflowRun.Status.RUNNING,
    WorkflowRun.Status.CANCEL_REQUESTED,
]


def recover_stale_executions(now=None):
    now = now or timezone.now()
    active_runs = WorkflowRun.objects.filter(status__in=_ACTIVE_RUN_STATUSES)
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
    if run.status not in _ACTIVE_RUN_STATUSES:
        return False
    kind = _stale_kind(run, now)
    if kind is None:
        return False
    finalize_stale_run(run, kind, now=now)
    return True


def _stale_kind(run, now):
    if run.status in {WorkflowRun.Status.PENDING, WorkflowRun.Status.QUEUED}:
        # The run never started, so it can only expire while queueing; a run
        # cannot be "worker lost" before any worker claimed it.
        if run.queue_deadline_at:
            return (
                StaleFinalizeKind.QUEUE_TIMEOUT
                if run.queue_deadline_at <= now
                else None
            )
        return (
            StaleFinalizeKind.QUEUE_TIMEOUT
            if ExecutionLease.is_expired(run, now=now)
            else None
        )
    # Started (or cancellation pending): worker liveness is checked first so a
    # dead worker is reported before the overall deadline elapses.
    if ExecutionLease.is_expired(run, now=now):
        return StaleFinalizeKind.WORKER_LOST
    if run.workflow_deadline_at and run.workflow_deadline_at <= now:
        return StaleFinalizeKind.EXECUTION_TIMEOUT
    return None


@transaction.atomic
def finalize_stale_run(run, kind, now=None):
    """Single terminal-state entry for stale runs.

    Transitions through the state machine, settles the node runs and attempts
    left behind by the execution, and records the terminal audit event.
    """
    now = now or timezone.now()
    cancel_requested = run.status == WorkflowRun.Status.CANCEL_REQUESTED
    if cancel_requested and kind not in _CANCELLATION_REASONS:
        # queue_timeout cannot co-occur with cancel_requested; keep it explicit.
        raise InvalidExecutionTransition(
            f"Unexpected stale kind {kind!r} for a cancel_requested run."
        )
    if not ExecutionStateMachine.can_transition(
        run.status, WorkflowRun.Status.TIMEOUT
    ):
        raise InvalidExecutionTransition(
            f"Cannot transition workflow run from {run.status!r} to timeout."
        )
    run.status = WorkflowRun.Status.TIMEOUT
    run.failure_reason = (
        _CANCELLATION_REASONS[kind] if cancel_requested else _FAILURE_REASONS[kind]
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
    _settle_stale_nodes(run, now)
    append_run_event(
        run_id=run.id,
        event_key=f"stale-finalize:{kind}",
        event={
            "event_type": _FINALIZE_EVENT_TYPES[kind],
            "message": run.failure_reason,
            "payload": {"kind": kind},
        },
    )
    return run


def _settle_stale_nodes(run, now):
    """Converge node runs and attempts left behind by the dead execution."""
    unknown_reason = (
        "Remote outcome unknown; the execution was not confirmed to finish."
    )
    never_started_reason = (
        "Never started; the run reached a terminal state first."
    )
    run.node_runs.filter(status=NodeRun.Status.RUNNING).update(
        status=NodeRun.Status.TIMEOUT,
        finished_at=now,
        failure_reason=unknown_reason,
    )
    run.node_runs.filter(
        status__in=[NodeRun.Status.PENDING, NodeRun.Status.QUEUED]
    ).update(
        status=NodeRun.Status.CANCELED,
        finished_at=now,
        failure_reason=never_started_reason,
    )
    NodeRunAttempt.objects.filter(
        node_run__workflow_run=run, status=NodeRunAttempt.Status.RUNNING
    ).update(
        status=NodeRunAttempt.Status.TIMEOUT,
        finished_at=now,
        failure_reason=unknown_reason,
    )
    NodeRunAttempt.objects.filter(
        node_run__workflow_run=run, status=NodeRunAttempt.Status.QUEUED
    ).update(
        status=NodeRunAttempt.Status.CANCELED,
        finished_at=now,
        failure_reason=never_started_reason,
    )
