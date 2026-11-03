"""Pure graph validation and canonical digest."""
import hashlib
import json
import re
from collections import defaultdict, deque

from common.workflow.node_types import CONTROL_NODE_TYPES, NODE_TYPES
from common.workflow.native_parameters import native_variable_values


def _output_extractor_errors(config, key):
    rules = config.get("outputExtractors")
    if rules is None:
        return []
    error = f"节点 {key} 的输出提取规则无效"
    if not isinstance(rules, list):
        return [error + "：必须为数组"]
    names = set()
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("name"), str)
            or not rule["name"].strip()
        ):
            return [error + "：每条规则需要变量名"]
        if rule["name"] in names or rule["name"] == "hosts":
            return [error + "：变量名重复或为保留名称 hosts"]
        names.add(rule["name"])
        try:
            if not isinstance(rule.get("pattern"), str) or not rule["pattern"]:
                return [error + "：需要正则表达式"]
            pattern = re.compile(rule["pattern"])
            group = rule.get("group", 1)
            if (
                isinstance(group, bool)
                or not isinstance(group, int)
                or group < 0
                or group > pattern.groups
            ):
                return [error + "：捕获组不存在"]
        except re.error:
            return [error + "：正则表达式错误"]
        if rule.get("type", "string") not in {
            "string",
            "json",
            "integer",
            "number",
            "boolean",
        }:
            return [error + "：不支持的输出类型"]
    return []


def validate_graph(graph):
    errors = []
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    edges = graph.get("edges") if isinstance(graph, dict) else None
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return ["流程图必须包含 nodes 和 edges 数组"]

    if any(not isinstance(node, dict) for node in nodes):
        return ["节点必须是对象"]
    if any(not isinstance(edge, dict) for edge in edges):
        return ["连线必须是对象"]
    node_by_key = {}
    for node in nodes:
        key = str(node.get("id") or "").strip()
        if not key:
            errors.append("节点缺少唯一标识")
            continue
        if key in node_by_key:
            errors.append(f"节点标识重复：{key}")
        if node.get("type") not in NODE_TYPES:
            errors.append(f"未知节点类型：{node.get('type')}")
        node_by_key[key] = node

    starts = [node for node in nodes if node.get("type") == "start"]
    ends = [node for node in nodes if node.get("type") == "end"]
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
        forbidden_targets = {
            "hostIds",
            "groupIds",
            "tagIds",
            "targetSelector",
            "host_ids",
            "group_ids",
            "tag_ids",
        }
        config = node.get("config") or {}
        if isinstance(config, dict):
            errors.extend(_output_extractor_errors(config, key))
            if node_type == "playbook" and config.get("hostPolicy", "native") not in {
                "native",
                "platform",
            }:
                errors.append(f"节点 {key} 的 hostPolicy 必须是 native 或 platform")
            try:
                native_variable_values(node_type, config)
            except ValueError as exc:
                errors.append(f"节点 {key}：{exc}")
        if forbidden_targets.intersection(node) or (
            isinstance(config, dict) and forbidden_targets.intersection(config)
        ):
            errors.append(f"节点 {key} 不能重新指定目标主机；目标由本次运行统一确定")
        if sum(bool(edge.get("isDefault")) for edge in outgoing[key]) > 1:
            errors.append(f"节点 {key} 最多允许一条默认出口")
        if node_type != "start" and not incoming[key]:
            errors.append(f"节点 {key} 没有入口")
        if node_type != "end" and not outgoing[key]:
            errors.append(f"节点 {key} 没有出口")
        if node_type == "parallel_gateway" and len(outgoing[key]) < 2:
            errors.append(f"并行分支 {key} 至少需要两条出口")
        if node_type == "parallel_join":
            if len(incoming[key]) < 2:
                errors.append(f"并行汇聚 {key} 至少需要两条入口")
            if len(outgoing[key]) != 1:
                errors.append(f"并行汇聚 {key} 必须且只能有一条出口")
        if node_type == "start":
            if incoming[key]:
                errors.append(f"开始节点 {key} 不能有入口")
            if len(outgoing[key]) != 1:
                errors.append(f"开始节点 {key} 必须且只能有一条出口")
        if node_type == "end" and outgoing[key]:
            errors.append(f"结束节点 {key} 不能有出口")
        if node_type not in CONTROL_NODE_TYPES:
            timeout = node.get("timeoutSeconds")
            if timeout is not None and (type(timeout) is not int or timeout <= 0):
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

    degrees = {key: len(incoming[key]) for key in node_by_key}
    ready = deque(key for key, degree in degrees.items() if degree == 0)
    visited_count = 0
    while ready:
        key = ready.popleft()
        visited_count += 1
        for edge in outgoing[key]:
            target = str(edge["target"])
            degrees[target] -= 1
            if degrees[target] == 0:
                ready.append(target)
    if visited_count != len(node_by_key):
        errors.append("流程图不允许环路")
    return errors


def graph_hash(graph):
    canonical = json.dumps(
        graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
