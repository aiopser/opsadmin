"""Explicit retries create a new fenced attempt; recovery never invokes this."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.jobs.application.dispatch import enqueue_node_run
from apps.jobs.application.authorization import authorize_execution
from apps.jobs.input_secrets import resolve_workflow_inputs
from apps.jobs.models import NodeRun, NodeRunAttempt, WorkflowRun
from apps.jobs.workflow_engine import node_queue_name


@transaction.atomic
def retry_failed_node(node_id, actor=None):
    run_id = NodeRun.objects.values_list("workflow_run_id", flat=True).get(pk=node_id)
    run = (
        WorkflowRun.objects.select_for_update()
        .select_related("worker_pool")
        .get(pk=run_id)
    )
    node = NodeRun.objects.select_for_update().get(pk=node_id)

    authorize_execution(
        actor=actor or run.triggered_by,
        graph_snapshot=run.graph_snapshot,
        input_vars=resolve_workflow_inputs(run),
    )
    if node.status not in {NodeRun.Status.FAILED, NodeRun.Status.TIMEOUT}:
        raise ValidationError("Only failed or timed-out nodes can be retried")
    if run.status in {
        WorkflowRun.Status.CANCEL_REQUESTED,
        WorkflowRun.Status.CANCELED,
        WorkflowRun.Status.SUCCESS,
    }:
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
    node.console_output = ""
    node.celery_task_id = ""
    node.save(
        update_fields=[
            "status",
            "attempt_count",
            "failure_reason",
            "finished_at",
            "started_at",
            "queued_at",
            "exit_code",
            "output_vars",
            "console_output",
            "celery_task_id",
            "updated_at",
        ]
    )
    NodeRunAttempt.objects.create(
        node_run=node,
        attempt=node.attempt_count,
        queue_name=node_queue_name(node.node_type, run.worker_pool, run.run_domain),
    )
    # Branch skips are final graph decisions. Only failure-blocked work resumes.
    run.node_runs.filter(
        status=NodeRun.Status.SKIPPED,
        failure_reason="前序步骤失败，未执行",
    ).update(
        status=NodeRun.Status.PENDING,
        failure_reason="",
        finished_at=None,
        updated_at=now,
    )
    # Recovery also cancels work that never started when the worker is lost.
    # Resume only this explicit reason, never user-canceled work or branch skips.
    run.node_runs.filter(
        status=NodeRun.Status.CANCELED,
        failure_reason="Never started; the run reached a terminal state first.",
    ).update(
        status=NodeRun.Status.PENDING,
        failure_reason="",
        finished_at=None,
        queued_at=None,
        heartbeat_at=None,
        celery_task_id="",
        updated_at=now,
    )
    run.status = WorkflowRun.Status.RUNNING
    run.finished_at = None
    run.failure_reason = ""
    run.workflow_deadline_at = now + timedelta(seconds=run.timeout_seconds)
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "failure_reason",
            "workflow_deadline_at",
            "updated_at",
        ]
    )
    transaction.on_commit(lambda: enqueue_node_run(node.id))
    return node
