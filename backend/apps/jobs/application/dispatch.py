"""Commit-aware publication; broker outages leave durable recovery records."""

from django.db import transaction
from django.utils import timezone

from apps.jobs.models import JobEventLog, NodeRun, NodeRunAttempt, WorkflowRun
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.workflow_engine import node_queue_name


def _publish(*, run_id, node_run_id, attempt, publish):
    try:
        task = publish()
    except Exception as exc:
        JobEventLog.objects.create(workflow_run_id=run_id, node_run_id=node_run_id,
            event_type="dispatch_failed", message="Broker publication failed; pending recovery.",
            payload={"attempt": attempt, "error_type": type(exc).__name__})
        return None
    JobEventLog.objects.create(workflow_run_id=run_id, node_run_id=node_run_id,
        event_type="dispatch_sent", message="Broker accepted publication.", payload={"attempt": attempt})
    return task


def enqueue_node_run(node_run_id):
    from apps.jobs.tasks import execute_node
    node = NodeRun.objects.select_related("workflow_node", "workflow_run__worker_pool").get(pk=node_run_id)
    if node.status != NodeRun.Status.QUEUED:
        return {"nodeRunId": node.id, "dispatched": False}
    queue = node_queue_name(node.node_type, node.workflow_run.worker_pool, node.workflow_run.run_domain)
    timeout = max(min(int(getattr(node.workflow_node, "timeout_seconds", 0) or node.workflow_run.timeout_seconds), node.workflow_run.timeout_seconds), 1)
    task = _publish(run_id=node.workflow_run_id, node_run_id=node.id, attempt=node.attempt_count,
        publish=lambda: execute_node.apply_async(args=[node.id, node.attempt_count], queue=queue,
            soft_time_limit=timeout, time_limit=timeout + 5))
    task_id = getattr(task, "id", "") or ""
    if task_id:
        NodeRun.objects.filter(pk=node.id, attempt_count=node.attempt_count).update(celery_task_id=task_id)
        NodeRunAttempt.objects.filter(node_run_id=node.id, attempt=node.attempt_count).update(celery_task_id=task_id)
    return {"nodeRunId": node.id, "taskId": task_id, "queue": queue, "dispatched": task is not None}


def enqueue_workflow_run(workflow_run_id, record_dispatch_task=True):
    from apps.jobs.tasks import run_workflow
    run = WorkflowRun.objects.get(pk=workflow_run_id)
    queue = "ops" if run.run_domain == WorkflowRun.RunDomain.OPS else "task"
    task = _publish(run_id=run.id, node_run_id=None, attempt=None,
        publish=lambda: run_workflow.apply_async(args=[run.id], queue=queue))
    task_id = getattr(task, "id", "") or ""
    if task_id and record_dispatch_task:
        ExecutionLease.touch(run.id, task_id=task_id)
    return {"workflowRunId": run.id, "dispatchMode": "celery", "taskId": task_id,
            "queue": queue, "dispatched": task is not None}


def dispatch_after_commit(run_id, *, record_dispatch_task=True):
    transaction.on_commit(lambda: enqueue_workflow_run(run_id, record_dispatch_task=record_dispatch_task))


def recover_pending_dispatches():
    # Re-publish only unclaimed work; attempt fencing makes ambiguous broker acceptance safe.
    latest = {}
    for event in JobEventLog.objects.filter(event_type__in=["dispatch_failed", "dispatch_sent"]).order_by("id").iterator(chunk_size=500):
        latest[(event.workflow_run_id, event.node_run_id, event.payload.get("attempt"))] = event.event_type
    recovered = 0
    for (run_id, node_id, attempt), status in latest.items():
        if status != "dispatch_failed":
            continue
        if node_id:
            if NodeRun.objects.filter(pk=node_id, attempt_count=attempt, status=NodeRun.Status.QUEUED).exists():
                recovered += int(enqueue_node_run(node_id)["dispatched"])
        elif WorkflowRun.objects.filter(pk=run_id, status__in=[WorkflowRun.Status.PENDING, WorkflowRun.Status.QUEUED, WorkflowRun.Status.RUNNING]).exists():
            recovered += int(enqueue_workflow_run(run_id)["dispatched"])
    return recovered
