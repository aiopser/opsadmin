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


def settle_canceled_work(run):
    """Settle unstarted/confirmed-canceled work; never claim a running worker stopped."""
    from apps.jobs.execution.snapshots import ensure_node_runs
    from common.workflow.node_types import ANSIBLE_NODE_TYPES

    finished_at = timezone.now()
    for node_run in ensure_node_runs(run).values():
        if node_run.status not in {NodeRun.Status.PENDING, NodeRun.Status.QUEUED, NodeRun.Status.CANCELED}:
            continue
        if node_run.node_type in ANSIBLE_NODE_TYPES:
            HostRunResult.objects.filter(node_run=node_run, status__in=[HostRunResult.Status.PENDING, HostRunResult.Status.RUNNING]).update(status=HostRunResult.Status.CANCELED, finished_at=finished_at, updated_at=finished_at)
            for target in run.target_snapshot or []:
                host_id, hostname = target.get("host_id"), str(target.get("hostname") or "")
                if hostname:
                    HostRunResult.objects.get_or_create(
                        node_run=node_run, host_key=HostRunResult.host_key_for(host_id, hostname),
                        defaults={"host_id": host_id, "hostname": hostname, "ip": target.get("address") or "0.0.0.0", "status": HostRunResult.Status.CANCELED, "finished_at": finished_at},
                    )
        node_run.status = NodeRun.Status.CANCELED
        node_run.finished_at = node_run.finished_at or finished_at
        node_run.failure_reason = "Canceled by user"
        node_run.save(update_fields=["status", "finished_at", "failure_reason", "updated_at"])
        node_run.attempts.filter(status="queued").update(status="canceled", finished_at=finished_at)
        append_run_event(run_id=run.id, node_run_id=node_run.id, event_key="node_canceled", event={"event_type": "node_canceled", "message": "Node execution canceled.", "payload": {"node_run_id": node_run.id}})


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
