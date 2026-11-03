from .application.cancel import settle_canceled_work
from .execution.snapshots import ensure_node_runs
from common.workflow.node_types import NodeType
from common.workflow.conditions import InvalidCondition, expression_is_true
from common.workflow.node_types import ANSIBLE_NODE_TYPES, CONTROL_NODE_TYPES
from uuid import uuid4
from apps.jobs.events import append_run_event
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.automation.models import WorkflowNode
from common.workflow.schema import validate_graph
from apps.jobs.models import WorkerPool

from .input_secrets import resolve_workflow_inputs
from .worker_pools import queue_for_pool
from .models import JobEventLog, NodeRun, NodeRunAttempt, WorkflowRun


SUCCESS_NODE_STATUSES = {
    NodeRun.Status.SUCCESS,
    NodeRun.Status.SKIPPED,
    NodeRun.Status.IGNORED,
}
TERMINAL_NODE_STATUSES = SUCCESS_NODE_STATUSES | {
    NodeRun.Status.FAILED,
    NodeRun.Status.TIMEOUT,
    NodeRun.Status.CANCELED,
}
ACTIVE_NODE_STATUSES = {
    NodeRun.Status.QUEUED,
    NodeRun.Status.RUNNING,
}


def node_queue_name(node_type, worker_pool, run_domain=WorkflowRun.RunDomain.TASK):
    if node_type in ANSIBLE_NODE_TYPES:
        return queue_for_pool(worker_pool)
    return "ops" if run_domain == WorkflowRun.RunDomain.OPS else "task"


def runtime_context(run, node_runs, include_secrets=True):
    node_outputs = {
        node.node_key: {"status": node.status, "outputs": node.output_vars or {}}
        for node in node_runs.values()
        if node.node_key
    }
    return {
        "title": f"流程通知：{run.name or f'运行 #{run.pk}'}",
        "inputs": (
            resolve_workflow_inputs(run)
            if include_secrets
            else dict(run.input_vars or {})
        ),
        "system": {
            "workflow_run_id": run.id,
            "triggered_by_id": run.triggered_by_id,
            "trigger_type": run.trigger_type,
        },
        "nodes": node_outputs,
    }


def _graph_maps(graph):
    nodes = {str(item["id"]): item for item in graph.get("nodes") or []}
    edges = {str(item["id"]): item for item in graph.get("edges") or []}
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for edge in edges.values():
        incoming[str(edge["target"])].append(edge)
        outgoing[str(edge["source"])].append(edge)
    return nodes, edges, incoming, outgoing


def _engine_state(run):
    context_vars = dict(run.context_vars or {})
    state = dict(context_vars.get("_engine") or {})
    state.setdefault("active_edges", [])
    context_vars["_engine"] = state
    return context_vars, state


def _activate_edges(run, node_runs, state, edge_items):
    resolved = set(state.get("resolved_edges") or [])
    if all(str(edge["id"]) in resolved for edge in edge_items):
        return True
    try:
        context = runtime_context(run, node_runs)
        selected = [
            edge
            for edge in edge_items
            if not edge.get("isDefault")
            and (
                not edge.get("condition")
                or expression_is_true(edge["condition"], context)
            )
        ]
    except InvalidCondition:
        run.status = WorkflowRun.Status.FAILED
        run.failure_reason = "Invalid workflow branch condition"
        run.finished_at = timezone.now()
        run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        return False
    if not selected:
        selected = [edge for edge in edge_items if edge.get("isDefault")]
    active = set(state.get("active_edges") or [])
    active.update(str(item["id"]) for item in selected)
    resolved.update(str(item["id"]) for item in edge_items)
    state["active_edges"] = sorted(active)
    state["resolved_edges"] = sorted(resolved)
    return True


def _node_is_ready(
    node_key, node_type, incoming, active_edges, node_runs, resolved_edges
):
    incoming_edges = incoming.get(node_key) or []
    selected = [edge for edge in incoming_edges if str(edge["id"]) in active_edges]
    if not selected:
        return False
    if node_type == NodeType.PARALLEL_JOIN:
        if any(str(edge["id"]) not in resolved_edges for edge in incoming_edges):
            return False
        return all(
            node_runs[str(edge["source"])].status in SUCCESS_NODE_STATUSES
            for edge in selected
        )
    return any(
        node_runs[str(edge["source"])].status in SUCCESS_NODE_STATUSES
        for edge in selected
    )


def _mark_control_success(run, node_run):
    now = timezone.now()
    node_run.status = NodeRun.Status.SUCCESS
    node_run.started_at = node_run.started_at or now
    node_run.finished_at = now
    node_run.duration_ms = 0
    node_run.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
            "updated_at",
        ]
    )
    append_run_event(
        run_id=(run).id,
        node_run_id=(node_run).id,
        event_key=uuid4().hex,
        event={
            "event_type": "node_succeeded",
            "message": f"Control node {node_run.node_key} completed.",
            "payload": {"node_key": node_run.node_key, "node_type": node_run.node_type},
        },
    )


def _process_failed_node(run, node_run):
    node = next(
        item for item in run.graph_snapshot["nodes"] if item["id"] == node_run.node_key
    )
    max_attempts = int((node.get("retryPolicy") or {}).get("maxAttempts") or 1)
    if (
        node.get("failurePolicy") == WorkflowNode.FailurePolicy.RETRY
        and node_run.attempt_count < max_attempts
    ):
        node_run.status = NodeRun.Status.PENDING
        node_run.failure_reason = ""
        node_run.finished_at = None
        node_run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        return "retry"
    if node.get("failurePolicy") == WorkflowNode.FailurePolicy.IGNORE or node.get(
        "continueOnError", False
    ):
        node_run.status = NodeRun.Status.IGNORED
        node_run.save(update_fields=["status", "updated_at"])
        return "ignore"
    return "stop"


@transaction.atomic
def plan_dispatch(workflow_run_id):
    # Local import: application.dispatch imports this module for node_queue_name.
    from apps.jobs.application.dispatch import register_dispatch

    run = (
        WorkflowRun.objects.select_for_update()
        .select_related("workflow_version", "workflow_version__workflow", "worker_pool")
        .get(id=workflow_run_id)
    )
    if run.status == WorkflowRun.Status.CANCELED:
        settle_canceled_work(run)
        return []
    if run.status in {
        WorkflowRun.Status.SUCCESS,
        WorkflowRun.Status.FAILED,
        WorkflowRun.Status.TIMEOUT,
        WorkflowRun.Status.CANCELED,
    }:
        return []
    if run.status == WorkflowRun.Status.CANCEL_REQUESTED:
        settle_canceled_work(run)
        if not run.node_runs.filter(status=NodeRun.Status.RUNNING).exists():
            run.status = WorkflowRun.Status.CANCELED
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "finished_at", "updated_at"])
        return []

    worker_pool = WorkerPool.objects.select_for_update().get(id=run.worker_pool_id)
    if not worker_pool.is_active:
        run.status = WorkflowRun.Status.FAILED
        run.failure_reason = "Worker pool is disabled"
        run.finished_at = timezone.now()
        run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        return []

    now = timezone.now()
    if run.workflow_deadline_at and now >= run.workflow_deadline_at:
        run.status = WorkflowRun.Status.TIMEOUT
        run.finished_at = now
        run.failure_reason = "Workflow execution timed out"
        run.save(
            update_fields=["status", "finished_at", "failure_reason", "updated_at"]
        )
        return []

    graph = run.graph_snapshot
    errors = validate_graph(graph)
    if errors:
        run.status = WorkflowRun.Status.FAILED
        run.failure_reason = "; ".join(errors)
        run.finished_at = now
        run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        return []
    nodes, _, incoming, outgoing = _graph_maps(graph)
    node_runs = ensure_node_runs(run)

    context_vars, engine_state = _engine_state(run)
    active_edges = set(engine_state.get("active_edges") or [])
    if not engine_state.get("started"):
        starts = [
            key for key, item in nodes.items() if item.get("type") == NodeType.START
        ]
        if len(starts) != 1:
            run.status = WorkflowRun.Status.FAILED
            run.failure_reason = "Workflow graph must contain exactly one start node"
            run.finished_at = now
            run.save(
                update_fields=["status", "failure_reason", "finished_at", "updated_at"]
            )
            return []
        start_run = node_runs[starts[0]]
        _mark_control_success(run, start_run)
        if not _activate_edges(run, node_runs, engine_state, outgoing[starts[0]]):
            return []
        engine_state["started"] = True
        run.started_at = run.started_at or now
        run.workflow_deadline_at = run.workflow_deadline_at or now + timedelta(
            seconds=run.timeout_seconds
        )
        run.status = WorkflowRun.Status.RUNNING
        append_run_event(
            run_id=(run).id,
            node_run_id=None,
            event_key=uuid4().hex,
            event={
                "event_type": "workflow_started",
                "message": "Workflow graph execution started.",
                "payload": {"workflow_run_id": run.id},
            },
        )

    for node_run in node_runs.values():
        if node_run.status in {NodeRun.Status.FAILED, NodeRun.Status.TIMEOUT}:
            result = _process_failed_node(run, node_run)
            if result == "stop":
                NodeRun.objects.filter(
                    workflow_run=run, status=NodeRun.Status.PENDING
                ).exclude(pk=node_run.pk).update(
                    status=NodeRun.Status.SKIPPED,
                    failure_reason="前序步骤失败，未执行",
                    finished_at=now,
                    updated_at=now,
                )
                run.status = (
                    WorkflowRun.Status.TIMEOUT
                    if node_run.status == NodeRun.Status.TIMEOUT
                    else WorkflowRun.Status.FAILED
                )
                run.failure_reason = (
                    node_run.failure_reason or f"Node {node_run.node_key} failed"
                )
                run.finished_at = now
                run.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "finished_at",
                        "updated_at",
                    ]
                )
                return []
            if result == "ignore":
                if not _activate_edges(
                    run, node_runs, engine_state, outgoing[node_run.node_key]
                ):
                    return []
        elif (
            node_run.status in SUCCESS_NODE_STATUSES
            and node_run.node_type not in CONTROL_NODE_TYPES
            and node_run.status != NodeRun.Status.SKIPPED
        ):
            if not _activate_edges(
                run, node_runs, engine_state, outgoing[node_run.node_key]
            ):
                return []

    changed = True
    while changed:
        changed = False
        active_edges = set(engine_state.get("active_edges") or [])
        for node_key, item in nodes.items():
            node_run = node_runs[node_key]
            if node_run.status != NodeRun.Status.PENDING:
                continue
            node_type = item.get("type")
            active_edges = set(engine_state.get("active_edges") or [])
            inbound = incoming.get(node_key) or []
            resolved = set(engine_state.get("resolved_edges") or [])
            if (
                inbound
                and all(str(edge["id"]) in resolved for edge in inbound)
                and not any(str(edge["id"]) in active_edges for edge in inbound)
            ):
                node_run.status = NodeRun.Status.SKIPPED
                node_run.finished_at = now
                node_run.save(update_fields=["status", "finished_at", "updated_at"])
                resolved.update(str(edge["id"]) for edge in outgoing[node_key])
                engine_state["resolved_edges"] = sorted(resolved)
                changed = True
                continue
            if node_type not in CONTROL_NODE_TYPES:
                continue
            if not _node_is_ready(
                node_key,
                node_type,
                incoming,
                active_edges,
                node_runs,
                set(engine_state.get("resolved_edges") or []),
            ):
                continue
            _mark_control_success(run, node_run)
            if not _activate_edges(run, node_runs, engine_state, outgoing[node_key]):
                return []
            changed = True

    active_edges = set(engine_state.get("active_edges") or [])
    queued_node_ids = []
    active_ansible_count = NodeRun.objects.filter(
        workflow_run__worker_pool=worker_pool,
        node_type__in=ANSIBLE_NODE_TYPES,
        status__in=[NodeRun.Status.QUEUED, NodeRun.Status.RUNNING],
    ).count()
    available_ansible_slots = max(
        int(worker_pool.concurrency_limit) - active_ansible_count,
        0,
    )
    pool_capacity_blocked = False
    for node_key, item in nodes.items():
        node_run = node_runs[node_key]
        node_type = item.get("type")
        if node_run.status != NodeRun.Status.PENDING or node_type in CONTROL_NODE_TYPES:
            continue
        if not _node_is_ready(
            node_key,
            node_type,
            incoming,
            active_edges,
            node_runs,
            set(engine_state.get("resolved_edges") or []),
        ):
            continue
        if node_type in ANSIBLE_NODE_TYPES and available_ansible_slots <= 0:
            pool_capacity_blocked = True
            continue
        node_run.status = NodeRun.Status.QUEUED
        node_run.queued_at = now
        node_run.attempt_count += 1
        node_run.save(
            update_fields=["status", "queued_at", "attempt_count", "updated_at"]
        )
        NodeRunAttempt.objects.create(
            node_run=node_run,
            attempt=node_run.attempt_count,
            status=NodeRunAttempt.Status.QUEUED,
            queue_name=node_queue_name(node_type, worker_pool, run.run_domain),
        )
        register_dispatch(
            workflow_run_id=run.id,
            node_run_id=node_run.id,
            attempt=node_run.attempt_count,
        )
        queued_node_ids.append(node_run.id)
        if node_type in ANSIBLE_NODE_TYPES:
            available_ansible_slots -= 1

    if queued_node_ids:
        run.status = WorkflowRun.Status.RUNNING
    else:
        current_statuses = {item.status for item in node_runs.values()}
        if pool_capacity_blocked:
            run.status = WorkflowRun.Status.QUEUED
        elif not (current_statuses & ACTIVE_NODE_STATUSES):
            completed_ends = [
                node_runs[key]
                for key, item in nodes.items()
                if item.get("type") == NodeType.END
                and node_runs[key].status == NodeRun.Status.SUCCESS
            ]
            if completed_ends:
                run.status = WorkflowRun.Status.SUCCESS
                run.finished_at = now
                run.duration_ms = int(
                    (now - (run.started_at or run.created_at)).total_seconds() * 1000
                )
                run.failure_reason = ""
                run.node_runs.filter(status=NodeRun.Status.PENDING).update(
                    status=NodeRun.Status.SKIPPED, finished_at=now
                )
                append_run_event(
                    run_id=(run).id,
                    node_run_id=None,
                    event_key=uuid4().hex,
                    event={
                        "event_type": "workflow_succeeded",
                        "message": "Workflow graph execution succeeded.",
                        "payload": {"workflow_run_id": run.id},
                    },
                )
            else:
                run.status = WorkflowRun.Status.FAILED
                run.finished_at = now
                run.duration_ms = int(
                    (now - (run.started_at or run.created_at)).total_seconds() * 1000
                )
                run.failure_reason = "Workflow graph stalled before an end node"

    context_vars["_engine"] = engine_state
    context_vars.update(runtime_context(run, node_runs, include_secrets=False))
    run.context_vars = context_vars
    run.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "duration_ms",
            "failure_reason",
            "workflow_deadline_at",
            "context_vars",
            "graph_snapshot",
            "updated_at",
        ]
    )
    return queued_node_ids
