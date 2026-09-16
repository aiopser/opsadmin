from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from .models import NodeRun, WorkflowRun


class InvalidExecutionTransition(ValueError):
    """Raised when an execution state transition is not allowed."""


class ExecutionStateMachine:
    TERMINAL_STATES = {
        WorkflowRun.Status.SUCCESS,
        WorkflowRun.Status.FAILED,
        WorkflowRun.Status.TIMEOUT,
        WorkflowRun.Status.CANCELED,
    }

    TRANSITIONS = {
        WorkflowRun.Status.PENDING: {
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.TIMEOUT,
            WorkflowRun.Status.CANCEL_REQUESTED,
        },
        WorkflowRun.Status.QUEUED: {
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.TIMEOUT,
            WorkflowRun.Status.CANCEL_REQUESTED,
        },
        WorkflowRun.Status.RUNNING: {
            WorkflowRun.Status.WAITING,
            WorkflowRun.Status.SUCCESS,
            WorkflowRun.Status.FAILED,
            WorkflowRun.Status.TIMEOUT,
            WorkflowRun.Status.CANCEL_REQUESTED,
        },
        WorkflowRun.Status.WAITING: {
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.SUCCESS,
            WorkflowRun.Status.FAILED,
            WorkflowRun.Status.TIMEOUT,
            WorkflowRun.Status.CANCEL_REQUESTED,
        },
        WorkflowRun.Status.CANCEL_REQUESTED: {
            WorkflowRun.Status.CANCELED,
            WorkflowRun.Status.FAILED,
            WorkflowRun.Status.TIMEOUT,
        },
    }

    @classmethod
    def can_transition(cls, current, target):
        if current == target:
            return True
        return target in cls.TRANSITIONS.get(current, set())

    @classmethod
    def transition(cls, run, target, *, reason=""):
        current = run.status
        if current == target:
            return run
        if not cls.can_transition(current, target):
            raise InvalidExecutionTransition(
                f"Cannot transition workflow run from {current!r} to {target!r}."
            )

        run.status = target
        if reason:
            run.failure_reason = reason
            run.save(update_fields=["status", "failure_reason", "updated_at"])
        else:
            run.save(update_fields=["status", "updated_at"])
        return run


class ExecutionLease:
    """Worker liveness lease, decoupled from the overall execution timeout."""

    DEFAULT_LEASE_SECONDS = 900
    NODE_TIMEOUT_GRACE_SECONDS = 60

    @staticmethod
    def touch(run_id, *, task_id=None, worker=None):
        values = {"heartbeat_at": timezone.now()}
        if task_id is not None:
            values["celery_task_id"] = task_id
        if worker is not None:
            values["worker_name"] = worker
        WorkflowRun.objects.filter(id=run_id).update(**values)

    @staticmethod
    def lease_seconds(run):
        """Heartbeat lease: the longest still-running node's timeout plus grace.

        Node tasks are hard-killed at their own time_limit, so a live worker
        always touches the run again within node timeout + grace. The floor
        (settings.JOBS_WORKER_LEASE_SECONDS, default 900s) covers runs whose
        nodes are short so a wedged worker is reported quickly.
        """
        configured = int(
            getattr(settings, "JOBS_WORKER_LEASE_SECONDS", ExecutionLease.DEFAULT_LEASE_SECONDS)
        )
        running_max = run.node_runs.filter(
            status=NodeRun.Status.RUNNING
        ).aggregate(value=Max("workflow_node__timeout_seconds"))["value"] or 0
        return max(
            configured,
            int(running_max) + ExecutionLease.NODE_TIMEOUT_GRACE_SECONDS,
        )

    @staticmethod
    def is_expired(run, now=None):
        last_activity = (
            getattr(run, "heartbeat_at", None)
            or getattr(run, "started_at", None)
            or getattr(run, "created_at", None)
        )
        if not last_activity:
            return False
        now = now or timezone.now()
        return last_activity + timedelta(seconds=ExecutionLease.lease_seconds(run)) < now
