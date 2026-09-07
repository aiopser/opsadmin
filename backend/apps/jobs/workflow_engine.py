from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.automation.models import WorkflowNode
from apps.automation.workflow_graph import serialize_graph
from apps.cmdb.models import WorkerPool

from .input_secrets import resolve_workflow_inputs
from .models import JobEventLog, NodeRun, NodeRunAttempt, WorkflowRun


ANSIBLE_NODE_TYPES = {
    WorkflowNode.NodeType.COMMAND,
    WorkflowNode.NodeType.SCRIPT,
    WorkflowNode.NodeType.PLAYBOOK,
    WorkflowNode.NodeType.MODULE,
}
CONTROL_NODE_TYPES = {
    WorkflowNode.NodeType.START,
    WorkflowNode.NodeType.END,
    WorkflowNode.NodeType.PARALLEL_GATEWAY,
    WorkflowNode.NodeType.PARALLEL_JOIN,
}
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
        return str(worker_pool.queue_name or "").strip() or "ansible"
    return "ops" if run_domain == WorkflowRun.RunDomain.OPS else "task"


def runtime_context(run, node_runs, include_secrets=True):
    node_outputs = {
        node.node_key: {"status": node.status, "outputs": node.output_vars or {}}
        for node in node_runs.values()
        if node.node_key
    }
    return {
        "inputs": (
            resolve_workflow_inputs(run)
            if include_secrets
            else dict(run.input_vars or {})
        ),
        "global": getattr(run.workflow_version, "global_vars", {}) or {},
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


def _ensure_executable_graph(graph):
    graph = {
        "nodes": [dict(item) for item in (graph.get("nodes") or [])],
        "edges": [dict(item) for item in (graph.get("edges") or [])],
    }
    if any(item.get("type") == WorkflowNode.NodeType.START for item in graph["nodes"]):
        return graph
    task_nodes = graph["nodes"]
    graph["nodes"] = [
        {"id": "__start__", "name": "开始", "type": WorkflowNode.NodeType.START},
        *task_nodes,
        {"id": "__end__", "name": "结束", "type": WorkflowNode.NodeType.END},
    ]
    if not graph["edges"]:
        keys = ["__start__", *[str(item["id"]) for item in task_nodes], "__end__"]
        graph["edges"] = [
            {"id": f"__edge_{index}__", "source": source, "target": target}
            for index, (source, target) in enumerate(zip(keys, keys[1:]), start=1)
        ]
        return graph
    incoming_keys = {str(edge["target"]) for edge in graph["edges"]}
    outgoing_keys = {str(edge["source"]) for edge in graph["edges"]}
    roots = [
        str(item["id"]) for item in task_nodes if str(item["id"]) not in incoming_keys
    ]
    leaves = [
        str(item["id"]) for item in task_nodes if str(item["id"]) not in outgoing_keys
    ]
    graph["edges"].extend(
        {"id": f"__start_edge_{index}__", "source": "__start__", "target": key}
        for index, key in enumerate(roots, start=1)
    )
    graph["edges"].extend(
        {"id": f"__end_edge_{index}__", "source": key, "target": "__end__"}
        for index, key in enumerate(leaves, start=1)
    )
    return graph


def _engine_state(run):
    context_vars = dict(run.context_vars or {})
    state = dict(context_vars.get("_engine") or {})
    state.setdefault("active_edges", [])
    context_vars["_engine"] = state
    return context_vars, state


def _activate_edges(state, edge_items):
    active = set(state.get("active_edges") or [])
    active.update(str(item["id"]) for item in edge_items)
    state["active_edges"] = sorted(active)


def _node_is_ready(node_key, node_type, incoming, active_edges, node_runs):
    incoming_edges = incoming.get(node_key) or []
    selected = [edge for edge in incoming_edges if str(edge["id"]) in active_edges]
    if not selected:
        return False
    if node_type == WorkflowNode.NodeType.PARALLEL_JOIN:
        if len(selected) != len(incoming_edges):
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
    JobEventLog.objects.create(
        workflow_run=run,
        node_run=node_run,
        event_type="node_succeeded",
        message=f"Control node {node_run.node_key} completed.",
        payload={"node_key": node_run.node_key, "node_type": node_run.node_type},
    )


def _process_failed_node(run, node_run):
    node = node_run.workflow_node
    max_attempts = int((node.retry_policy or {}).get("maxAttempts") or 1)
    if (
        node.failure_policy == WorkflowNode.FailurePolicy.RETRY
        and node_run.attempt_count < max_attempts
    ):
        node_run.status = NodeRun.Status.PENDING
        node_run.failure_reason = ""
        node_run.finished_at = None
        node_run.save(
            update_fields=["status", "failure_reason", "finished_at", "updated_at"]
        )
        return "retry"
    if (
        node.failure_policy == WorkflowNode.FailurePolicy.IGNORE
        or node.continue_on_error
    ):
        node_run.status = NodeRun.Status.IGNORED
        node_run.save(update_fields=["status", "updated_at"])
        return "ignore"
    return "stop"


@transaction.atomic
def plan_dispatch(workflow_run_id):
    run = (
        WorkflowRun.objects.select_for_update()
        .select_related("workflow_version", "workflow_version__workflow", "worker_pool")
        .get(id=workflow_run_id)
    )
    if run.status in {
        WorkflowRun.Status.SUCCESS,
        WorkflowRun.Status.FAILED,
        WorkflowRun.Status.TIMEOUT,
        WorkflowRun.Status.CANCELED,
    }:
        return []
    if run.status == WorkflowRun.Status.CANCEL_REQUESTED:
        run.status = WorkflowRun.Status.CANCELED
        run.finished_at = timezone.now()
        run.node_runs.filter(
            status__in=list(ACTIVE_NODE_STATUSES | {NodeRun.Status.PENDING})
        ).update(status=NodeRun.Status.CANCELED, finished_at=timezone.now())
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

    graph = _ensure_executable_graph(
        run.graph_snapshot
        or run.workflow_version.graph_snapshot
        or serialize_graph(run.workflow_version)
    )
    run.graph_snapshot = graph
    nodes, _, incoming, outgoing = _graph_maps(graph)
    model_nodes = {node.node_key: node for node in run.workflow_version.nodes.all()}
    node_runs = {
        item.node_key: item
        for item in run.node_runs.select_related("workflow_node").all()
    }
    for node_key, item in nodes.items():
        if node_key not in node_runs:
            model_node = model_nodes.get(node_key)
            node_runs[node_key] = NodeRun.objects.create(
                workflow_run=run,
                workflow_node=model_node,
                command_version=model_node.command_version if model_node else None,
                node_key=node_key,
                node_name=item.get("name") or node_key,
                node_type=item.get("type") or WorkflowNode.NodeType.COMMAND,
                config_snapshot=item.get("config") or {},
                input_vars=item.get("inputMapping") or {},
            )

    context_vars, engine_state = _engine_state(run)
    active_edges = set(engine_state.get("active_edges") or [])
    if not engine_state.get("started"):
        starts = [
            key
            for key, item in nodes.items()
            if item.get("type") == WorkflowNode.NodeType.START
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
        _activate_edges(engine_state, outgoing[starts[0]])
        engine_state["started"] = True
        run.started_at = run.started_at or now
        run.workflow_deadline_at = run.workflow_deadline_at or now + timedelta(
            seconds=run.timeout_seconds
        )
        run.status = WorkflowRun.Status.RUNNING
        JobEventLog.objects.create(
            workflow_run=run,
            event_type="workflow_started",
            message="Workflow graph execution started.",
            payload={"workflow_run_id": run.id},
        )

    for node_run in node_runs.values():
        if node_run.status == NodeRun.Status.FAILED:
            result = _process_failed_node(run, node_run)
            if result == "stop":
                run.status = WorkflowRun.Status.FAILED
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
                _activate_edges(engine_state, outgoing[node_run.node_key])
        elif (
            node_run.status in SUCCESS_NODE_STATUSES
            and node_run.node_type not in CONTROL_NODE_TYPES
        ):
            _activate_edges(engine_state, outgoing[node_run.node_key])

    changed = True
    while changed:
        changed = False
        active_edges = set(engine_state.get("active_edges") or [])
        for node_key, item in nodes.items():
            node_run = node_runs[node_key]
            if node_run.status != NodeRun.Status.PENDING:
                continue
            node_type = item.get("type")
            if node_type not in CONTROL_NODE_TYPES:
                continue
            if not _node_is_ready(
                node_key, node_type, incoming, active_edges, node_runs
            ):
                continue
            _mark_control_success(run, node_run)
            _activate_edges(engine_state, outgoing[node_key])
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
        if (
            node_run.status != NodeRun.Status.PENDING
            or node_type in CONTROL_NODE_TYPES
        ):
            continue
        if not _node_is_ready(node_key, node_type, incoming, active_edges, node_runs):
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
                if item.get("type") == WorkflowNode.NodeType.END
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
                JobEventLog.objects.create(
                    workflow_run=run,
                    event_type="workflow_succeeded",
                    message="Workflow graph execution succeeded.",
                    payload={"workflow_run_id": run.id},
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
