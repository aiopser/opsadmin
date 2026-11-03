from common.workflow.node_types import ANSIBLE_NODE_TYPES
from uuid import uuid4
from apps.jobs.events import append_run_event
import logging
import json
import time

from celery import current_task, shared_task
from billiard.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from datetime import datetime, timedelta

from django.db import OperationalError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.jobs.models import (
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    ScheduledJob,
    ScheduledJobOutcome,
    WorkflowRun,
)
from apps.jobs.cron import database_instant, next_cron_time, prev_cron_time
from apps.jobs.schedule_sync import periodic_task_name, upsert_periodic_task
from apps.jobs.node_executors import (
    NodeExecutionCanceled,
    execute_generic_node,
    record_generic_result,
)
from apps.jobs.application.authorization import authorize_execution
from apps.jobs.input_secrets import resolve_workflow_inputs
from apps.jobs.recovery import recover_stale_executions
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.application.dispatch import (
    deliver_pending_dispatches,
    enqueue_node_run,
    enqueue_workflow_run,
)
from apps.jobs.application.runs import (
    create_workflow_run_from_selector,
    scheduled_job_run_options,
)
from apps.jobs.execution.registry import execute_ansible_node
from apps.jobs.workflow_engine import (
    node_queue_name,
    plan_dispatch,
    runtime_context,
)


logger = logging.getLogger(__name__)
TERMINAL_WORKFLOW_STATUSES = {
    WorkflowRun.Status.SUCCESS,
    WorkflowRun.Status.FAILED,
    WorkflowRun.Status.TIMEOUT,
    WorkflowRun.Status.CANCELED,
}
ACTIVE_WORKFLOW_STATUSES = {
    WorkflowRun.Status.PENDING,
    WorkflowRun.Status.QUEUED,
    WorkflowRun.Status.RUNNING,
    WorkflowRun.Status.WAITING,
    WorkflowRun.Status.CANCEL_REQUESTED,
}


def _claim_node_run(node_run_id, task_id, now, attempt):
    return bool(
        NodeRun.objects.filter(
            id=node_run_id,
            attempt_count=attempt,
            status=NodeRun.Status.QUEUED,
        )
        .exclude(
            workflow_run__status__in=TERMINAL_WORKFLOW_STATUSES
            | {WorkflowRun.Status.CANCEL_REQUESTED}
        )
        .update(
            status=NodeRun.Status.RUNNING,
            celery_task_id=task_id,
            started_at=now,
            heartbeat_at=now,
            updated_at=now,
        )
    )


def _attempt_terminal_status(node_status):
    return {
        NodeRun.Status.SUCCESS: NodeRunAttempt.Status.SUCCESS,
        NodeRun.Status.TIMEOUT: NodeRunAttempt.Status.TIMEOUT,
        NodeRun.Status.CANCELED: NodeRunAttempt.Status.CANCELED,
    }.get(node_status, NodeRunAttempt.Status.FAILED)


def _mark_dispatch_failed(workflow_run_id, exc):
    reason = str(exc) or exc.__class__.__name__
    now = timezone.now()
    run = WorkflowRun.objects.filter(id=workflow_run_id).first()
    if not run or run.status in TERMINAL_WORKFLOW_STATUSES:
        return
    run.status = WorkflowRun.Status.FAILED
    run.failure_reason = f"Workflow dispatch failed: {reason}"
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
    run.node_runs.filter(
        status__in=[NodeRun.Status.PENDING, NodeRun.Status.QUEUED]
    ).update(status=NodeRun.Status.CANCELED, finished_at=now, updated_at=now)
    append_run_event(
        run_id=(run).id,
        node_run_id=None,
        event_key=uuid4().hex,
        event={
            "event_type": "workflow_failed",
            "message": run.failure_reason,
            "payload": {
                "workflow_run_id": run.id,
                "error_type": exc.__class__.__name__,
            },
        },
    )


def _dispatch_with_deadlock_retry(workflow_run_id, attempts=3):
    """按 events.py 同样的策略重试 MySQL 1205/1213；ensure_node_runs 幂等保证重试安全。"""
    last_exc = None
    for retry in range(attempts):
        try:
            node_run_ids = plan_dispatch(workflow_run_id)
            for node_run_id in node_run_ids:
                enqueue_node_run(node_run_id)
            return node_run_ids
        except OperationalError as exc:
            if not exc.args or exc.args[0] not in {1205, 1213} or retry == attempts - 1:
                raise
            last_exc = exc
            logger.warning(
                "Workflow dispatch %s hit lock wait/deadlock (%s), retry %s/%s",
                workflow_run_id,
                exc.args[0],
                retry + 1,
                attempts - 1,
            )
            time.sleep(0.2 * (retry + 1))
    raise last_exc


@shared_task(name="jobs.run_workflow")
def run_workflow(workflow_run_id):
    WorkflowRun.objects.filter(
        id=workflow_run_id,
        status=WorkflowRun.Status.PENDING,
    ).update(
        status=WorkflowRun.Status.QUEUED,
        updated_at=timezone.now(),
    )
    run = WorkflowRun.objects.get(id=workflow_run_id)
    task_request = getattr(current_task, "request", None)
    worker_name = (
        getattr(task_request, "hostname", "")
        or getattr(settings, "CELERY_WORKER_HOSTNAME", "")
        or "local"
    )
    ExecutionLease.touch(workflow_run_id, worker=worker_name)
    try:
        node_run_ids = _dispatch_with_deadlock_retry(workflow_run_id)
    except Exception as exc:
        logger.exception("Workflow dispatch %s failed", workflow_run_id)
        _mark_dispatch_failed(workflow_run_id, exc)
        return {
            "workflowRunId": workflow_run_id,
            "status": WorkflowRun.Status.FAILED,
            "queuedNodes": [],
        }
    ExecutionLease.touch(workflow_run_id, worker=worker_name)
    status = WorkflowRun.objects.values_list("status", flat=True).get(
        id=workflow_run_id
    )
    return {
        "workflowRunId": workflow_run_id,
        "status": status,
        "queuedNodes": node_run_ids,
    }


@shared_task(name="jobs.execute_node")
def execute_node(node_run_id, attempt):
    node_run = NodeRun.objects.select_related("workflow_run", "workflow_node").get(
        id=node_run_id
    )
    if node_run.attempt_count != attempt:
        return {"nodeRunId": node_run_id, "status": node_run.status}
    if node_run.workflow_run.status in TERMINAL_WORKFLOW_STATUSES:
        if node_run.status in {NodeRun.Status.PENDING, NodeRun.Status.QUEUED}:
            now = timezone.now()
            NodeRun.objects.filter(id=node_run_id).update(
                status=NodeRun.Status.CANCELED,
                finished_at=now,
                updated_at=now,
            )
            node_run.status = NodeRun.Status.CANCELED
        return {"nodeRunId": node_run_id, "status": node_run.status}
    if node_run.status != NodeRun.Status.QUEUED:
        return {"nodeRunId": node_run_id, "status": node_run.status}
    task_request = getattr(current_task, "request", None)
    task_id = getattr(task_request, "id", "") or ""
    worker_name = getattr(task_request, "hostname", "") or "local"
    now = timezone.now()
    claimed = _claim_node_run(node_run_id, task_id, now, attempt)
    if not claimed:
        status = NodeRun.objects.values_list("status", flat=True).get(id=node_run_id)
        return {"nodeRunId": node_run_id, "status": status}
    NodeRunAttempt.objects.filter(node_run_id=node_run_id, attempt=attempt,).update(
        status=NodeRunAttempt.Status.RUNNING,
        celery_task_id=task_id,
        worker_name=worker_name,
        started_at=now,
        updated_at=now,
    )
    ExecutionLease.touch(node_run.workflow_run_id, worker=worker_name)
    node_run.refresh_from_db()
    try:

        deadline = node_run.workflow_run.workflow_deadline_at
        if deadline is not None and timezone.now() >= deadline:
            raise SoftTimeLimitExceeded()
        authorize_execution(
            actor=node_run.workflow_run.triggered_by,
            graph_snapshot=node_run.workflow_run.graph_snapshot,
            input_vars=resolve_workflow_inputs(node_run.workflow_run),
        )
        if node_run.node_type in ANSIBLE_NODE_TYPES:
            result = execute_ansible_node(
                node_run_id, expected_attempt=attempt, expected_task_id=task_id
            )
        else:
            context = runtime_context(
                node_run.workflow_run,
                {item.node_key: item for item in node_run.workflow_run.node_runs.all()},
            )
            output_vars = execute_generic_node(
                node_run_id, context, expected_attempt=attempt, expected_task_id=task_id
            )
            record_generic_result(node_run, True, output_vars=output_vars)
            result = node_run
    except NodeExecutionCanceled as exc:
        record_generic_result(
            node_run, False, error=str(exc), failure_status=NodeRun.Status.CANCELED
        )
        result = node_run
    except SoftTimeLimitExceeded:
        record_generic_result(
            node_run,
            False,
            error="Node execution exceeded its time limit",
            failure_status=NodeRun.Status.TIMEOUT,
        )
        result = node_run
    except Exception as exc:
        record_generic_result(node_run, False, error=str(exc) or exc.__class__.__name__)
        result = node_run
    finally:
        finished_at = timezone.now()
        with transaction.atomic():
            current = (
                NodeRun.objects.select_for_update()
                .filter(
                    pk=node_run_id,
                    attempt_count=attempt,
                    celery_task_id=task_id,
                    status__in=[
                        NodeRun.Status.SUCCESS,
                        NodeRun.Status.FAILED,
                        NodeRun.Status.TIMEOUT,
                        NodeRun.Status.CANCELED,
                    ],
                )
                .first()
            )
            settled = bool(
                current
                and NodeRunAttempt.objects.filter(
                    node_run_id=node_run_id,
                    attempt=attempt,
                    status=NodeRunAttempt.Status.RUNNING,
                    celery_task_id=task_id,
                ).update(
                    status=_attempt_terminal_status(current.status),
                    finished_at=finished_at,
                    exit_code=current.exit_code,
                    output_vars=current.output_vars,
                    failure_reason=current.failure_reason,
                    updated_at=finished_at,
                )
            )
        if settled:
            ExecutionLease.touch(node_run.workflow_run_id, worker=worker_name)
            enqueue_workflow_run(node_run.workflow_run_id, record_dispatch_task=False)
        if settled and node_run.node_type in ANSIBLE_NODE_TYPES:
            waiting_run_ids = (
                WorkflowRun.objects.filter(
                    worker_pool_id=node_run.workflow_run.worker_pool_id,
                    status__in=[
                        WorkflowRun.Status.PENDING,
                        WorkflowRun.Status.QUEUED,
                        WorkflowRun.Status.RUNNING,
                    ],
                    node_runs__status=NodeRun.Status.PENDING,
                )
                .exclude(id=node_run.workflow_run_id)
                .values_list("id", flat=True)
                .distinct()[:50]
            )
            for waiting_run_id in waiting_run_ids:
                enqueue_workflow_run(waiting_run_id, record_dispatch_task=False)
    return {"nodeRunId": node_run_id, "status": result.status}


@shared_task(name="jobs.recover_stale_workflow_runs")
def recover_stale_workflow_runs():
    from .log_artifacts import (
        purge_expired_archives,
        rearchive_failed_chunks,
        recover_pending_archives,
    )
    from .alerts import recover_alerts

    operations = (
        ("dispatches", deliver_pending_dispatches),
        ("recovered", recover_stale_executions),
        ("archives", rearchive_failed_chunks),
        ("purgedArchives", purge_expired_archives),
        ("archiveRequests", recover_pending_archives),
        ("notificationAlerts", recover_alerts),
    )
    result = {}
    errors = []
    for name, operation in operations:
        try:
            result[name] = operation()
        except Exception:
            # Independent maintenance must not block dispatch or alert recovery.
            logger.exception("Workflow maintenance operation failed: %s", name)
            result[name] = None
            errors.append(name)
    if errors:
        result["errors"] = errors
    return result


@shared_task(name="jobs.dispatch_notification_alert")
def dispatch_notification_alert(record_id):
    from .alerts import deliver_alert

    return {"delivered": deliver_alert(record_id)}


@shared_task(name="jobs.archive_pending_run_logs")
def archive_pending_run_logs(request_id):
    from .log_artifacts import process_archive_request

    return {"archived": process_archive_request(request_id)}


def _transfer_orphan_schedule_ownerships() -> int:
    """Never elevate an orphaned definition to a privileged service actor.

    Kept as a compatibility counter for scheduler responses. The original actor
    is reauthorized when dispatching; reassignment requires a human decision.
    """
    return 0


def _previous_scheduled_run_active(schedule) -> bool:
    return bool(
        schedule.last_workflow_run_id
        and WorkflowRun.objects.filter(
            pk=schedule.last_workflow_run_id,
            status__in=ACTIVE_WORKFLOW_STATUSES,
        ).exists()
    )


def _exception_reason(exc) -> str:
    """Flatten a DRF exception into a short single-line reason string."""
    detail = getattr(exc, "detail", None)
    if detail is None:
        return str(exc)
    if isinstance(detail, dict):
        return "; ".join(f"{key}: {value}" for key, value in detail.items())
    if isinstance(detail, (list, tuple)):
        return "; ".join(str(item) for item in detail)
    return str(detail)


def _record_schedule_outcome(schedule, scheduled_for, outcome, reason="", run=None):
    """Persist one dispatch outcome per occurrence (unique per job and time).

    A queued overlap occurrence is rewritten as dispatched once the catch-up
    run fires, so the row always carries the occurrence's final outcome.
    """
    if scheduled_for is None:
        return
    ScheduledJobOutcome.objects.update_or_create(
        scheduled_job=schedule,
        scheduled_for=scheduled_for,
        defaults={"outcome": outcome, "reason": reason[:255], "workflow_run": run},
    )


def _load_locked_schedule(scheduled_job_id):
    return (
        ScheduledJob.objects.select_for_update()
        .select_related(
            "workflow_version",
            "worker_pool",
        )
        .filter(pk=scheduled_job_id)
        .first()
    )


def _disable_invalid_schedule(locked, scheduled_for) -> None:
    """Auto-disable a schedule whose workflow version or worker pool is gone.

    Mirrors the disabled state into the PeriodicTask so beat stops firing it.
    """
    if locked.workflow_version_id is None:
        reason = "disabled: workflow version deleted"
    elif locked.workflow_version.status != "published":
        reason = "disabled: workflow version unpublished"
    else:
        reason = "disabled: worker pool inactive"
    _retire_schedule(locked, reason)
    _record_schedule_outcome(
        locked,
        scheduled_for,
        ScheduledJobOutcome.Outcome.INVALID,
        locked.last_skip_reason,
    )


def _next_occurrence(locked, now):
    """Next planned trigger: a cron slot for periodic jobs, none for one-off jobs."""
    if locked.schedule_type == ScheduledJob.ScheduleType.ONCE:
        return None
    return next_cron_time(locked.cron_expression, locked.timezone, now)


def _expired(locked, now) -> bool:
    return locked.expires_at is not None and now >= locked.expires_at


def _retire_schedule(locked, reason) -> None:
    """Stop a schedule for good and mirror the disabled state into beat."""
    locked.enabled = False
    locked.next_run_at = None
    locked.last_skip_reason = reason[:255]
    locked.save(
        update_fields=["enabled", "next_run_at", "last_skip_reason", "updated_at"]
    )
    upsert_periodic_task(locked)


def _dispatch_scheduled_run(locked, scheduled_for, now):
    """Create and enqueue one workflow run for ``locked``; returns run or None."""
    try:
        run_options = scheduled_job_run_options(locked)
        run = create_workflow_run_from_selector(
            workflow_version=locked.workflow_version,
            host_ids=locked.host_ids or [],
            group_ids=locked.group_ids or [],
            tag_ids=locked.tag_ids or [],
            input_vars={
                **run_options["input_vars"],
                "execution_source": "scheduled",
                "scheduled_job_id": locked.id,
                "scheduled_job_name": locked.name,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
            },
            worker_pool=locked.worker_pool,
            triggered_by=locked.created_by,
            trigger_type=WorkflowRun.TriggerType.SCHEDULED,
            timeout_seconds=run_options["timeout_seconds"],
            queue_timeout_seconds=run_options["queue_timeout_seconds"],
        )
    except (PermissionDenied, ValidationError) as exc:
        locked.next_run_at = _next_occurrence(locked, now)
        locked.last_skip_reason = f"dispatch rejected: {_exception_reason(exc)}"[:255]
        locked.pending_dispatch = False
        locked.save(
            update_fields=[
                "next_run_at",
                "pending_dispatch",
                "last_skip_reason",
                "updated_at",
            ]
        )
        _record_schedule_outcome(
            locked,
            scheduled_for,
            ScheduledJobOutcome.Outcome.INVALID,
            locked.last_skip_reason,
        )
        return None
    append_run_event(
        run_id=(run).id,
        node_run_id=None,
        event_key=uuid4().hex,
        event={
            "event_type": "workflow_dispatch_requested",
            "message": "Scheduled workflow run dispatch requested.",
            "payload": {
                "scheduled_job_id": locked.id,
                "workflow_run_id": run.id,
            },
        },
    )
    transaction.on_commit(lambda run_id=run.id: enqueue_workflow_run(run_id))
    locked.last_run_at = now
    locked.last_workflow_run = run
    locked.pending_dispatch = False
    locked.next_run_at = _next_occurrence(locked, now)
    locked.last_skip_reason = ""
    update_fields = [
        "last_run_at",
        "last_workflow_run",
        "next_run_at",
        "pending_dispatch",
        "last_skip_reason",
        "updated_at",
    ]
    if locked.schedule_type == ScheduledJob.ScheduleType.ONCE:
        # One occurrence only: retire the job so beat stops firing and the list
        # reflects the finished state instead of a stale "enabled" switch.
        locked.enabled = False
        update_fields.append("enabled")
    locked.save(update_fields=update_fields)
    if not locked.enabled:
        upsert_periodic_task(locked)
    _record_schedule_outcome(
        locked,
        scheduled_for,
        ScheduledJobOutcome.Outcome.DISPATCHED,
        run=run,
    )
    return run


@shared_task(name="jobs.execute_scheduled_job")
def execute_scheduled_job(scheduled_job_id, scheduled_for=None, schedule_token=None):
    """Beat-triggered entry point for one ScheduledJob occurrence.

    The DatabaseScheduler fires this task once per occurrence — a cron slot for
    periodic jobs, the single clocked moment for one-off jobs; misfire, expiry
    and overlap policies are evaluated here so their outcomes stay auditable.
    """
    now = timezone.now()
    with transaction.atomic():
        locked = _load_locked_schedule(scheduled_job_id)
        if locked is None or not locked.enabled:
            return {"scheduledJobId": scheduled_job_id, "status": "inactive"}
        from django_celery_beat.models import PeriodicTask

        if not scheduled_for or not schedule_token:
            return {"scheduledJobId": locked.id, "status": "invalid_trigger"}
        # Beat retires a one-off trigger immediately after publishing. The
        # business row and definition token govern already-published messages.
        payload = (
            PeriodicTask.objects.filter(name=periodic_task_name(locked.pk))
            .values_list("kwargs", flat=True)
            .first()
        )
        if not payload or json.loads(payload).get("schedule_token") != schedule_token:
            return {"scheduledJobId": locked.id, "status": "stale"}
        try:
            scheduled_for = database_instant(datetime.fromisoformat(scheduled_for))
            if scheduled_for > now:
                return {"scheduledJobId": locked.id, "status": "invalid_trigger"}
            if locked.schedule_type == ScheduledJob.ScheduleType.ONCE:
                # The clocked moment is the only valid occurrence for a one-off.
                if locked.run_at is None or scheduled_for != locked.run_at:
                    return {"scheduledJobId": locked.id, "status": "invalid_trigger"}
            elif (
                prev_cron_time(locked.cron_expression, locked.timezone, scheduled_for)
                != scheduled_for
            ):
                return {"scheduledJobId": locked.id, "status": "invalid_trigger"}
        except (TypeError, ValueError):
            return {"scheduledJobId": locked.id, "status": "invalid_trigger"}
        # Expiry: no run may start at or after expires_at, whatever the policy.
        if _expired(locked, now):
            reason = f"expired at {locked.expires_at:%Y-%m-%d %H:%M}"
            _retire_schedule(locked, reason)
            _record_schedule_outcome(
                locked,
                scheduled_for,
                ScheduledJobOutcome.Outcome.EXPIRED,
                reason,
            )
            return {"scheduledJobId": locked.id, "status": "expired"}
        # Celery delivery is at-least-once. Once this cron slot has an outcome,
        # a duplicate/retried trigger must not create another run (especially
        # when overlap_policy=ALLOW). QUEUED outcomes are finalized by the
        # catch-up sweeper and are also already claimed.
        if ScheduledJobOutcome.objects.filter(
            scheduled_job=locked,
            scheduled_for=scheduled_for,
        ).exists():
            return {
                "scheduledJobId": locked.id,
                "status": "duplicate",
                "scheduledFor": scheduled_for.isoformat(),
            }
        if (
            locked.workflow_version_id is None
            or locked.workflow_version.status != "published"
            or not locked.worker_pool.is_active
        ):
            _disable_invalid_schedule(locked, scheduled_for)
            return {"scheduledJobId": locked.id, "status": "invalid"}
        # Misfire policy: an occurrence missed beyond the grace window
        # (beat downtime, broker backlog) either fires late or is skipped.
        overdue_seconds = (now - scheduled_for).total_seconds()
        if (
            locked.misfire_policy == ScheduledJob.MisfirePolicy.SKIP
            and overdue_seconds > locked.misfire_grace_seconds
        ):
            reason = f"misfire skipped: overdue by {int(overdue_seconds)}s"
            if locked.schedule_type == ScheduledJob.ScheduleType.ONCE:
                # A skipped one-off is over; there is no next slot to wait for.
                _retire_schedule(locked, reason)
            else:
                locked.next_run_at = _next_occurrence(locked, now)
                locked.last_skip_reason = reason
                locked.save(
                    update_fields=["next_run_at", "last_skip_reason", "updated_at"]
                )
            _record_schedule_outcome(
                locked,
                scheduled_for,
                ScheduledJobOutcome.Outcome.MISFIRE_SKIPPED,
                reason,
            )
            return {"scheduledJobId": locked.id, "status": "misfire_skipped"}
        # Overlap policy: decide what happens while the previous
        # scheduled run is still active.
        if (
            locked.overlap_policy != ScheduledJob.OverlapPolicy.ALLOW
            and _previous_scheduled_run_active(locked)
        ):
            if locked.overlap_policy == ScheduledJob.OverlapPolicy.QUEUE:
                # Mark one catch-up dispatch; the catchups sweeper fires it
                # on its first tick after the previous run reaches a
                # terminal state.
                # Coalesce into one catch-up, while claiming every occurrence
                # so redeliveries never become fresh runs after it finishes.
                already_pending = locked.pending_dispatch
                locked.pending_dispatch = True
                locked.next_run_at = _next_occurrence(locked, now)
                locked.last_skip_reason = "overlap queued: previous run still active"
                locked.save(
                    update_fields=[
                        "pending_dispatch",
                        "next_run_at",
                        "last_skip_reason",
                        "updated_at",
                    ]
                )
                _record_schedule_outcome(
                    locked,
                    scheduled_for,
                    ScheduledJobOutcome.Outcome.OVERLAP_SKIPPED
                    if already_pending
                    else ScheduledJobOutcome.Outcome.OVERLAP_QUEUED,
                    "coalesced into pending catch-up"
                    if already_pending
                    else locked.last_skip_reason,
                )
            elif locked.schedule_type == ScheduledJob.ScheduleType.ONCE:
                # The single occurrence lost the overlap race and is not queued,
                # so the one-off has nothing left to do.
                _retire_schedule(locked, "overlap skipped: previous run still active")
                _record_schedule_outcome(
                    locked,
                    scheduled_for,
                    ScheduledJobOutcome.Outcome.OVERLAP_SKIPPED,
                    locked.last_skip_reason,
                )
            else:
                locked.next_run_at = _next_occurrence(locked, now)
                locked.last_skip_reason = "overlap skipped: previous run still active"
                locked.save(
                    update_fields=["next_run_at", "last_skip_reason", "updated_at"]
                )
                _record_schedule_outcome(
                    locked,
                    scheduled_for,
                    ScheduledJobOutcome.Outcome.OVERLAP_SKIPPED,
                    locked.last_skip_reason,
                )
            return {"scheduledJobId": locked.id, "status": "overlap_skipped"}
        run = _dispatch_scheduled_run(locked, scheduled_for, now)
        if run is None:
            return {"scheduledJobId": locked.id, "status": "rejected"}
        return {
            "scheduledJobId": locked.id,
            "status": "dispatched",
            "workflowRunId": run.id,
        }


@shared_task(name="jobs.deliver_scheduled_catchups")
def deliver_scheduled_catchups():
    """Deliver overlap-queued catch-up dispatches.

    QUEUE policy marks ``pending_dispatch`` while the previous run is still
    active; the occurrence fires on the first sweep after that run reaches a
    terminal state.
    """
    now = timezone.now()
    transferred = _transfer_orphan_schedule_ownerships()
    dispatched = 0
    skipped = 0
    due_jobs = ScheduledJob.objects.select_related(
        "workflow_version",
        "worker_pool",
    ).filter(
        enabled=True,
        pending_dispatch=True,
    )
    for schedule in due_jobs:
        with transaction.atomic():
            locked = _load_locked_schedule(schedule.pk)
            if locked is None or not locked.enabled or not locked.pending_dispatch:
                continue
            if _expired(locked, now):
                reason = f"expired at {locked.expires_at:%Y-%m-%d %H:%M}"
                locked.pending_dispatch = False
                locked.save(update_fields=["pending_dispatch", "updated_at"])
                ScheduledJobOutcome.objects.filter(
                    scheduled_job=locked,
                    outcome=ScheduledJobOutcome.Outcome.OVERLAP_QUEUED,
                ).update(outcome=ScheduledJobOutcome.Outcome.EXPIRED, reason=reason)
                _retire_schedule(locked, reason)
                skipped += 1
                continue
            if (
                locked.workflow_version_id is None
                or locked.workflow_version.status != "published"
                or not locked.worker_pool.is_active
            ):
                _disable_invalid_schedule(locked, None)
                skipped += 1
                continue
            if _previous_scheduled_run_active(locked):
                skipped += 1
                continue
            # The queued occurrence keeps its original slot so the
            # OVERLAP_QUEUED outcome row is rewritten as DISPATCHED.
            scheduled_for = (
                ScheduledJobOutcome.objects.filter(
                    scheduled_job=locked,
                    outcome=ScheduledJobOutcome.Outcome.OVERLAP_QUEUED,
                )
                .order_by("-scheduled_for")
                .values_list("scheduled_for", flat=True)
                .first()
            )
            run = _dispatch_scheduled_run(locked, scheduled_for, now)
            if run is None:
                skipped += 1
            else:
                dispatched += 1
    return {
        "dispatched": dispatched,
        "skipped": skipped,
        "ownershipTransferred": transferred,
    }
