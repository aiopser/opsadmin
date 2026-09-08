"""Explicit retries create a new fenced attempt; recovery never invokes this."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.jobs.application.dispatch import enqueue_node_run
from apps.jobs.models import NodeRun, NodeRunAttempt, WorkflowRun
from apps.jobs.workflow_engine import node_queue_name


@transaction.atomic
def retry_failed_node(node_id):
    run_id = NodeRun.objects.values_list("workflow_run_id", flat=True).get(pk=node_id)
    run = WorkflowRun.objects.select_for_update().select_related("worker_pool").get(pk=run_id)
    node = NodeRun.objects.select_for_update().get(pk=node_id)
    if node.status not in {NodeRun.Status.FAILED, NodeRun.Status.TIMEOUT}:
        raise ValidationError("Only failed or timed-out nodes can be retried")
    if run.status in {WorkflowRun.Status.CANCEL_REQUESTED, WorkflowRun.Status.CANCELED, WorkflowRun.Status.SUCCESS}:
        raise ValidationError("Run cannot be retried in its current state")
    now = timezone.now()
    node.status = NodeRun.Status.QUEUED
    node.attempt_count += 1
    node.failure_reason = ""
    node.finished_at = None
    node.started_at = None
    node.queued_at = now
    node.exit_code = None
    node.output_vars = {}
    node.save(update_fields=["status", "attempt_count", "failure_reason", "finished_at", "started_at", "queued_at", "exit_code", "output_vars", "updated_at"])
    NodeRunAttempt.objects.create(node_run=node, attempt=node.attempt_count,
        queue_name=node_queue_name(node.node_type, run.worker_pool, run.run_domain))
    run.status = WorkflowRun.Status.RUNNING
    run.finished_at = None
    run.failure_reason = ""
    run.workflow_deadline_at = now + timedelta(seconds=run.timeout_seconds)
    run.save(update_fields=["status", "finished_at", "failure_reason", "workflow_deadline_at", "updated_at"])
    transaction.on_commit(lambda: enqueue_node_run(node.id))
    return node
