from common.workflow.node_types import ANSIBLE_NODE_TYPES
from uuid import uuid4
from apps.jobs.events import append_run_event
import logging
import time

from celery import current_task, shared_task
from billiard.exceptions import SoftTimeLimitExceeded

from django.conf import settings
from datetime import timedelta

from django.db import OperationalError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.jobs.models import (
    JobEventLog,
    NodeRun,
    NodeRunAttempt,
    ScheduledJob,
    WorkflowRun,
)
from apps.jobs.node_executors import execute_generic_node, record_generic_result
from apps.jobs.recovery import recover_stale_executions
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.application.dispatch import (
    enqueue_node_run,
    enqueue_workflow_run,
    recover_pending_dispatches,
)
from apps.jobs.application.runs import (
    create_workflow_run_from_host_ids,
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
                workflow_run_id, exc.args[0], retry + 1, attempts - 1,
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
        if node_run.node_type in ANSIBLE_NODE_TYPES:
            result = execute_ansible_node(node_run_id)
        else:
            context = runtime_context(
                node_run.workflow_run,
                {item.node_key: item for item in node_run.workflow_run.node_runs.all()},
            )
            output_vars = execute_generic_node(node_run_id, context)
            node_run.refresh_from_db()
            record_generic_result(node_run, True, output_vars=output_vars)
            result = node_run
    except SoftTimeLimitExceeded:
        node_run.refresh_from_db()
        record_generic_result(
            node_run,
            False,
            error="Node execution exceeded its time limit",
            failure_status=NodeRun.Status.TIMEOUT,
        )
        result = node_run
    except Exception as exc:
        node_run.refresh_from_db()
        record_generic_result(node_run, False, error=str(exc) or exc.__class__.__name__)
        result = node_run
    finally:
        finished_at = timezone.now()
        node_run.refresh_from_db()
        NodeRunAttempt.objects.filter(node_run_id=node_run_id, attempt=attempt,).update(
            status=_attempt_terminal_status(node_run.status),
            finished_at=finished_at,
            exit_code=node_run.exit_code,
            output_vars=node_run.output_vars,
            failure_reason=node_run.failure_reason,
            updated_at=finished_at,
        )
        ExecutionLease.touch(node_run.workflow_run_id, worker=worker_name)
        enqueue_workflow_run(node_run.workflow_run_id, record_dispatch_task=False)
        if node_run.node_type in ANSIBLE_NODE_TYPES:
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
    return {
        "dispatches": recover_pending_dispatches(),
        "recovered": recover_stale_executions(),
    }


@shared_task(name="jobs.dispatch_scheduled_jobs")
def dispatch_scheduled_jobs():
    from .cron import next_cron_time

    now = timezone.now()
    dispatched = 0
    skipped = 0
    due_jobs = ScheduledJob.objects.select_related(
        "workflow_version",
        "worker_pool",
    ).filter(
        enabled=True,
        next_run_at__lte=now,
        workflow_version__status="published",
        worker_pool__is_active=True,
    )
    for schedule in due_jobs:
        with transaction.atomic():
            locked = (
                ScheduledJob.objects.select_for_update()
                .select_related(
                    "workflow_version",
                    "worker_pool",
                )
                .get(pk=schedule.pk)
            )
            if not locked.enabled or not locked.next_run_at or locked.next_run_at > now:
                continue
            if (
                locked.workflow_version.status != "published"
                or not locked.worker_pool.is_active
            ):
                locked.enabled = False
                locked.next_run_at = None
                locked.save(update_fields=["enabled", "next_run_at", "updated_at"])
                skipped += 1
                continue
            try:
                run_options = scheduled_job_run_options(locked)
                run = create_workflow_run_from_host_ids(
                    workflow_version=locked.workflow_version,
                    host_ids=locked.host_ids or [],
                    input_vars={
                        **run_options["input_vars"],
                        "execution_source": "scheduled",
                        "scheduled_job_id": locked.id,
                    },
                    worker_pool=locked.worker_pool,
                    triggered_by=locked.created_by,
                    trigger_type=WorkflowRun.TriggerType.SCHEDULED,
                    timeout_seconds=run_options["timeout_seconds"],
                    queue_timeout_seconds=run_options["queue_timeout_seconds"],
                )
            except (PermissionDenied, ValidationError):
                skipped += 1
                locked.next_run_at = next_cron_time(
                    locked.cron_expression, locked.timezone, now
                )
                locked.save(update_fields=["next_run_at", "updated_at"])
                continue
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
            locked.next_run_at = next_cron_time(
                locked.cron_expression, locked.timezone, now
            )
            locked.save(
                update_fields=[
                    "last_run_at",
                    "last_workflow_run",
                    "next_run_at",
                    "updated_at",
                ]
            )
            dispatched += 1
    return {"dispatched": dispatched, "skipped": skipped}
