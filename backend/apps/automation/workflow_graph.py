import hashlib
import json
from collections import defaultdict, deque

from django.db import transaction

from .models import WorkflowEdge, WorkflowNode


CONTROL_NODE_TYPES = {
    WorkflowNode.NodeType.START,
    WorkflowNode.NodeType.END,
    WorkflowNode.NodeType.PARALLEL_GATEWAY,
    WorkflowNode.NodeType.PARALLEL_JOIN,
}


def serialize_graph(workflow_version):
    nodes = list(
        workflow_version.nodes.select_related("command_version").order_by(
            "order_index", "id"
        )
    )
    edges = list(
        workflow_version.edges.select_related("source_node", "target_node").order_by(
            "order_index", "id"
        )
    )
    return {
        "nodes": [
            {
                "id": node.node_key,
                "name": node.name,
                "type": node.node_type,
                "resourceType": node.resource_type,
                "resourceId": node.resource_id,
                "commandVersionId": node.command_version_id,
                "config": node.config or {},
                "inputMapping": node.input_mapping or {},
                "inputSchema": node.input_schema or [],
                "outputSchema": node.output_schema or [],
                "retryPolicy": node.retry_policy or {},
                "failurePolicy": node.failure_policy,
                "timeoutSeconds": node.timeout_seconds,
                "position": (node.config or {}).get("position", {}),
            }
            for node in nodes
        ],
        "edges": [
            {
                "id": edge.edge_key,
                "source": edge.source_node.node_key,
                "target": edge.target_node.node_key,
                "condition": edge.condition_expression,
                "isDefault": edge.is_default,
            }
            for edge in edges
        ],
    }


def validate_graph(graph):
    errors = []
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    edges = graph.get("edges") if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["流程图必须包含 nodes 和 edges 数组"]

    node_by_key = {}
    for node in nodes:
        key = str(node.get("id") or "").strip()
        if not key:
            errors.append("节点缺少唯一标识")
            continue
        if key in node_by_key:
            errors.append(f"节点标识重复：{key}")
        node_by_key[key] = node

    starts = [node for node in nodes if node.get("type") == WorkflowNode.NodeType.START]
    ends = [node for node in nodes if node.get("type") == WorkflowNode.NodeType.END]
    if len(starts) != 1:
        errors.append("流程必须且只能包含一个开始节点")
    if not ends:
        errors.append("流程至少需要一个结束节点")

    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    edge_keys = set()
    for edge in edges:
        edge_key = str(edge.get("id") or "").strip()
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        if not edge_key or edge_key in edge_keys:
            errors.append(f"连线标识无效或重复：{edge_key or '空'}")
        edge_keys.add(edge_key)
        if source not in node_by_key or target not in node_by_key:
            errors.append(f"连线 {edge_key or '未命名'} 指向不存在的节点")
            continue
        if source == target:
            errors.append(f"节点 {source} 不能连接自身")
        outgoing[source].append(edge)
        incoming[target].append(edge)

    for node in nodes:
        key = str(node.get("id") or "")
        node_type = node.get("type")
        if node_type != WorkflowNode.NodeType.START and not incoming[key]:
            errors.append(f"节点 {key} 没有入口")
        if node_type != WorkflowNode.NodeType.END and not outgoing[key]:
            errors.append(f"节点 {key} 没有出口")
        if (
            node_type == WorkflowNode.NodeType.PARALLEL_GATEWAY
            and len(outgoing[key]) < 2
        ):
            errors.append(f"并行分支 {key} 至少需要两条出口")
        if node_type == WorkflowNode.NodeType.PARALLEL_JOIN:
            if len(incoming[key]) < 2:
                errors.append(f"并行汇聚 {key} 至少需要两条入口")
            if len(outgoing[key]) != 1:
                errors.append(f"并行汇聚 {key} 必须且只能有一条出口")
        if node_type == WorkflowNode.NodeType.START:
            if incoming[key]:
                errors.append(f"开始节点 {key} 不能有入口")
            if len(outgoing[key]) != 1:
                errors.append(f"开始节点 {key} 必须且只能有一条出口")
        if node_type == WorkflowNode.NodeType.END and outgoing[key]:
            errors.append(f"结束节点 {key} 不能有出口")
        if node_type not in CONTROL_NODE_TYPES:
            timeout = int(node.get("timeoutSeconds") or 0)
            if timeout <= 0:
                errors.append(f"节点 {key} 的超时时间必须大于 0")

    if len(starts) == 1:
        visited = set()
        queue = deque([str(starts[0].get("id"))])
        while queue:
            key = queue.popleft()
            if key in visited:
                continue
            visited.add(key)
            queue.extend(str(edge.get("target")) for edge in outgoing[key])
        unreachable = set(node_by_key) - visited
        if unreachable:
            errors.append(f"存在不可达节点：{', '.join(sorted(unreachable))}")

    return errors


def graph_hash(graph):
    canonical = json.dumps(
        graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@transaction.atomic
def replace_graph(workflow_version, graph):
    workflow_version.assert_mutable()
    errors = validate_graph(graph)
    if errors:
        return errors

    workflow_version.edges.all().delete()
    workflow_version.nodes.all().delete()
    node_map = {}
    for index, item in enumerate(graph["nodes"], start=1):
        config = dict(item.get("config") or {})
        if item.get("position"):
            config["position"] = item["position"]
        node = WorkflowNode.objects.create(
            workflow_version=workflow_version,
            node_key=item["id"],
            name=item.get("name") or item["id"],
            node_type=item.get("type") or WorkflowNode.NodeType.COMMAND,
            command_version_id=item.get("commandVersionId"),
            resource_type=item.get("resourceType") or "",
            resource_id=item.get("resourceId"),
            config=config,
            input_mapping=item.get("inputMapping") or {},
            input_schema=item.get("inputSchema") or [],
            output_schema=item.get("outputSchema") or [],
            retry_policy=item.get("retryPolicy") or {},
            failure_policy=item.get("failurePolicy") or WorkflowNode.FailurePolicy.STOP,
            timeout_seconds=int(item.get("timeoutSeconds") or 60),
            order_index=index,
        )
        node_map[node.node_key] = node

    for index, item in enumerate(graph["edges"], start=1):
        WorkflowEdge.objects.create(
            workflow_version=workflow_version,
            edge_key=item["id"],
            source_node=node_map[item["source"]],
            target_node=node_map[item["target"]],
            condition_expression=item.get("condition") or "",
            is_default=bool(item.get("isDefault")),
            order_index=index,
        )

    workflow_version.graph_snapshot = serialize_graph(workflow_version)
    workflow_version.validation_report = []
    workflow_version.save(
        update_fields=["graph_snapshot", "validation_report", "updated_at"]
    )
    return []
