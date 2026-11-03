"""Durable broker publication; broker outages leave recoverable dispatch records.

Every publication intent is mirrored in a DispatchRecord row created inside the
same transaction as its business row (run creation / node queueing). If the
process dies between commit and publish, the periodic scanner republishes from
those rows; worker-side attempt fencing keeps a republish safe when the broker
actually accepted the message.
"""
from datetime import timedelta
from uuid import uuid4

from django.db.models import Q
from django.utils import timezone

from apps.jobs.events import append_run_event
from apps.jobs.models import (
    DispatchRecord,
    NodeRun,
    NodeRunAttempt,
    WorkflowRun,
)
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.workflow_engine import node_queue_name

RECOVER_BATCH_SIZE = 100
RETRY_BACKOFF_BASE_SECONDS = 30
RETRY_BACKOFF_CAP_SECONDS = 900
SENT_RECORD_RETENTION_DAYS = 7

DISPATCHABLE_RUN_STATUSES = [
    WorkflowRun.Status.PENDING,
    WorkflowRun.Status.QUEUED,
    WorkflowRun.Status.RUNNING,
    WorkflowRun.Status.WAITING,
]


def _append_dispatch_event(*, run_id, node_run_id, event_type, message, payload):
    append_run_event(
        run_id=run_id,
        node_run_id=node_run_id,
        event_key=uuid4().hex,
        event={"event_type": event_type, "message": message, "payload": payload},
    )


def register_dispatch(*, workflow_run_id, node_run_id=None, attempt=0):
    """Create or fetch the durable pending record. Call inside the business transaction."""
    record, _ = DispatchRecord.objects.get_or_create(
        kind=(
            DispatchRecord.Kind.NODE if node_run_id else DispatchRecord.Kind.WORKFLOW
        ),
        workflow_run_id=workflow_run_id,
        node_run_id=node_run_id,
        attempt=attempt,
        defaults={"status": DispatchRecord.Status.PENDING},
    )
    return record


def _node_queue_and_timeout(node):
    run = node.workflow_run
    queue = node_queue_name(node.node_type, run.worker_pool, run.run_domain)
    from apps.jobs.execution.settings_snapshot import effective_node_timeout

    timeout = effective_node_timeout(run, node.node_key)
    return queue, timeout


def _attempt_publish(record, *, record_dispatch_task=True):
    """Publish once and update the record; returns (task, queue).

    Workflow-level records are republished even when SENT: run_workflow is
    idempotent and repeat calls drive graph progression. Failures mark the
    record FAILED with exponential backoff for the recovery scanner.
    """
    from apps.jobs.tasks import execute_node, run_workflow

    node = None
    if record.node_run_id:
        node = NodeRun.objects.select_related(
            "workflow_node", "workflow_run__worker_pool"
        ).get(pk=record.node_run_id)
        run = node.workflow_run
        queue, timeout = _node_queue_and_timeout(node)
        publish = lambda: execute_node.apply_async(
            args=[node.id, record.attempt],
            queue=queue,
            soft_time_limit=timeout,
            time_limit=timeout + 5,
        )
    else:
        run = WorkflowRun.objects.get(pk=record.workflow_run_id)
        queue = "ops" if run.run_domain == WorkflowRun.RunDomain.OPS else "task"
        publish = lambda: run_workflow.apply_async(args=[run.id], queue=queue)

    record.delivery_attempts += 1
    try:
        task = publish()
    except Exception as exc:
        backoff = min(
            RETRY_BACKOFF_BASE_SECONDS * (2 ** min(record.delivery_attempts - 1, 5)),
            RETRY_BACKOFF_CAP_SECONDS,
        )
        record.status = DispatchRecord.Status.FAILED
        record.next_retry_at = timezone.now() + timedelta(seconds=backoff)
        record.last_error = type(exc).__name__
        record.save(
            update_fields=[
                "status",
                "next_retry_at",
                "delivery_attempts",
                "last_error",
                "updated_at",
            ]
        )
        _append_dispatch_event(
            run_id=run.id,
            node_run_id=node.id if node else None,
            event_type="dispatch_failed",
            message="Broker publication failed; pending recovery.",
            payload={
                "attempt": record.attempt,
                "error_type": type(exc).__name__,
            },
        )
        return None, queue

    task_id = getattr(task, "id", "") or ""
    record.status = DispatchRecord.Status.SENT
    record.celery_task_id = task_id
    record.next_retry_at = None
    record.last_error = ""
    record.save(
        update_fields=[
            "status",
            "celery_task_id",
            "next_retry_at",
            "delivery_attempts",
            "last_error",
            "updated_at",
        ]
    )
    if node:
        NodeRun.objects.filter(pk=node.id, attempt_count=record.attempt).update(
            celery_task_id=task_id
        )
        NodeRunAttempt.objects.filter(
            node_run_id=node.id, attempt=record.attempt
        ).update(celery_task_id=task_id)
    elif record_dispatch_task and task_id:
        ExecutionLease.touch(run.id, task_id=task_id)
    _append_dispatch_event(
        run_id=run.id,
        node_run_id=node.id if node else None,
        event_type="dispatch_sent",
        message="Broker accepted publication.",
        payload={"attempt": record.attempt},
    )
    return task, queue


def enqueue_node_run(node_run_id):
    node = NodeRun.objects.select_related(
        "workflow_node", "workflow_run__worker_pool"
    ).get(pk=node_run_id)
    if node.status != NodeRun.Status.QUEUED:
        return {"nodeRunId": node.id, "dispatched": False}
    record = register_dispatch(
        workflow_run_id=node.workflow_run_id,
        node_run_id=node.id,
        attempt=node.attempt_count,
    )
    if record.status == DispatchRecord.Status.SENT:
        # Already published for this attempt (e.g. duplicate enqueue); never republish.
        queue, _timeout = _node_queue_and_timeout(node)
        return {
            "nodeRunId": node.id,
            "taskId": record.celery_task_id,
            "queue": queue,
            "dispatched": False,
        }
    task, queue = _attempt_publish(record)
    return {
        "nodeRunId": node.id,
        "taskId": getattr(task, "id", "") or "",
        "queue": queue,
        "dispatched": task is not None,
    }


def enqueue_workflow_run(workflow_run_id, record_dispatch_task=True):
    run = WorkflowRun.objects.get(pk=workflow_run_id)
    record = register_dispatch(workflow_run_id=run.id)
    task, queue = _attempt_publish(record, record_dispatch_task=record_dispatch_task)
    return {
        "workflowRunId": run.id,
        "dispatchMode": "celery",
        "taskId": getattr(task, "id", "") or "",
        "queue": queue,
        "dispatched": task is not None,
    }


def dispatch_after_commit(run_id, *, record_dispatch_task=True):
    transaction_on_commit = _on_commit
    transaction_on_commit(
        lambda: enqueue_workflow_run(run_id, record_dispatch_task=record_dispatch_task)
    )


def _on_commit(callback):
    from django.db import transaction

    transaction.on_commit(callback)


def deliver_pending_dispatches(now=None):
    """Republish pending/failed records whose business rows still need dispatch."""
    now = now or timezone.now()
    records = list(
        DispatchRecord.objects.filter(
            status__in=[
                DispatchRecord.Status.PENDING,
                DispatchRecord.Status.FAILED,
            ]
        )
        .filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now))
        .order_by("id")[:RECOVER_BATCH_SIZE]
    )
    delivered = 0
    for record in records:
        if record.node_run_id:
            dispatchable = NodeRun.objects.filter(
                pk=record.node_run_id,
                attempt_count=record.attempt,
                status=NodeRun.Status.QUEUED,
            ).exists()
        else:
            dispatchable = WorkflowRun.objects.filter(
                pk=record.workflow_run_id,
                status__in=DISPATCHABLE_RUN_STATUSES,
            ).exists()
        if not dispatchable:
            record.status = DispatchRecord.Status.STALE
            record.save(update_fields=["status", "updated_at"])
            continue
        task, _queue = _attempt_publish(record)
        delivered += int(task is not None)
    DispatchRecord.objects.filter(
        status=DispatchRecord.Status.SENT,
        updated_at__lt=now - timedelta(days=SENT_RECORD_RETENTION_DAYS),
    ).delete()
    return delivered
