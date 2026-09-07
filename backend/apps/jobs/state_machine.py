from datetime import timedelta

from django.utils import timezone

from .models import WorkflowRun


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
            WorkflowRun.Status.CANCEL_REQUESTED,
        },
        WorkflowRun.Status.QUEUED: {
            WorkflowRun.Status.RUNNING,
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
    @staticmethod
    def touch(run_id, *, task_id=None, worker=None):
        values = {"heartbeat_at": timezone.now()}
        if task_id is not None:
            values["celery_task_id"] = task_id
        if worker is not None:
            values["worker_name"] = worker
        WorkflowRun.objects.filter(id=run_id).update(**values)

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
        timeout_seconds = max(int(run.timeout_seconds or 0), 1)
        return last_activity + timedelta(seconds=timeout_seconds) < now
