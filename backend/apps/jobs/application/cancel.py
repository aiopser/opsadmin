from uuid import uuid4
from apps.jobs.events import append_run_event
from django.db import transaction
from apps.jobs.state_machine import ExecutionStateMachine
from django.utils import timezone
from apps.automation.models import WorkflowNode
from apps.jobs.models import HostRunResult, JobEventLog, NodeRun, WorkflowRun


def should_stop_workflow_run(run):
    return run.status in {
        WorkflowRun.Status.CANCEL_REQUESTED,
        WorkflowRun.Status.CANCELED,
        WorkflowRun.Status.TIMEOUT,
    }


def _is_workflow_run_canceled(run):
    run.refresh_from_db(fields=["status"])
    return should_stop_workflow_run(run)


def _mark_node_run_canceled(node_run):
    if node_run.status not in {NodeRun.Status.PENDING, NodeRun.Status.RUNNING}:
        return False

    finished_at = timezone.now()
    node_run.status = NodeRun.Status.CANCELED
    node_run.finished_at = finished_at
    node_run.duration_ms = int(
        (finished_at - (node_run.started_at or finished_at)).total_seconds() * 1000
    )
    node_run.failure_reason = "Canceled by user"
    node_run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "failure_reason",
            "updated_at",
        ]
    )
    append_run_event(
        run_id=(node_run.workflow_run).id,
        node_run_id=(node_run).id,
        event_key=uuid4().hex,
        event={
            "event_type": "node_canceled",
            "message": "Node execution canceled by user.",
            "payload": {"node_run_id": node_run.id},
        },
    )
    return True


def _mark_workflow_work_canceled(run):
    finished_at = timezone.now()
    node_runs_by_workflow_node_id = {
        node_run.workflow_node_id: node_run
        for node_run in NodeRun.objects.filter(workflow_run=run)
    }
    workflow_nodes = (
        WorkflowNode.objects.filter(workflow_version=run.workflow_version)
        .select_related("command_version")
        .order_by("order_index", "id")
    )
    terminal_statuses = {
        NodeRun.Status.SUCCESS,
        NodeRun.Status.FAILED,
        NodeRun.Status.SKIPPED,
        NodeRun.Status.CANCELED,
    }

    for workflow_node in workflow_nodes:
        node_run = node_runs_by_workflow_node_id.get(workflow_node.id)
        if node_run is None:
            node_run = NodeRun.objects.create(
                workflow_run=run,
                workflow_node=workflow_node,
                command_version=workflow_node.command_version,
                status=NodeRun.Status.PENDING,
                input_vars=workflow_node.input_mapping,
            )
        if node_run.status in terminal_statuses:
            continue

        HostRunResult.objects.filter(
            node_run=node_run,
            status__in=[HostRunResult.Status.PENDING, HostRunResult.Status.RUNNING],
        ).update(
            status=HostRunResult.Status.CANCELED,
            finished_at=finished_at,
            updated_at=finished_at,
        )
        for target in run.target_snapshot or []:
            host_id = target.get("host_id")
            hostname = str(target.get("hostname") or "")
            if not hostname:
                continue
            host_key = HostRunResult.host_key_for(host_id, hostname)
            HostRunResult.objects.get_or_create(
                node_run=node_run,
                host_key=host_key,
                defaults={
                    "host_id": host_id,
                    "hostname": hostname,
                    "ip": target.get("address") or "0.0.0.0",
                    "status": HostRunResult.Status.CANCELED,
                    "raw_event_data": {
                        "event": "workflow_canceled",
                        "event_data": {"host": hostname},
                    },
                    "finished_at": finished_at,
                },
            )
        _mark_node_run_canceled(node_run)


@transaction.atomic
def request_execution_cancel(run_id):
    run = WorkflowRun.objects.select_for_update().get(id=run_id)
    if run.status in ExecutionStateMachine.TERMINAL_STATES:
        return run
    if run.status in {
        WorkflowRun.Status.PENDING,
        WorkflowRun.Status.QUEUED,
        WorkflowRun.Status.RUNNING,
        WorkflowRun.Status.WAITING,
    }:
        ExecutionStateMachine.transition(
            run,
            WorkflowRun.Status.CANCEL_REQUESTED,
            reason="Cancellation requested by user.",
        )
        run.cancel_requested_at = timezone.now()
        run.save(update_fields=["cancel_requested_at", "updated_at"])
    return run
