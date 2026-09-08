from common.workflow.node_types import NodeType
from copy import deepcopy

from django.db import transaction

from common.workflow import schema

from .models import WorkflowEdge, WorkflowNode


@transaction.atomic
def publish_version(workflow_version, user):
    from django.utils import timezone
    from .models import WorkflowVersion

    locked = WorkflowVersion.objects.select_for_update().get(pk=workflow_version.pk)
    locked.assert_mutable()
    graph = serialize_graph(locked, freeze_resources=True)
    errors = schema.validate_graph(graph)
    if errors:
        raise ValueError("; ".join(errors))
    locked.graph_snapshot = graph
    locked.published_hash = schema.graph_hash(graph)
    locked.validation_report = []
    locked.status = locked.Status.PUBLISHED
    locked.published_by = user
    locked.published_at = timezone.now()
    locked.save()
    for field in (
        "graph_snapshot",
        "published_hash",
        "validation_report",
        "status",
        "published_by",
        "published_at",
    ):
        setattr(workflow_version, field, getattr(locked, field))


def serialize_graph(workflow_version, *, freeze_resources=False):
    from .resource_snapshots import resource_snapshot

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
        "globalVars": deepcopy(workflow_version.global_vars or {}),
        "inputSchema": deepcopy(workflow_version.input_schema or {}),
        "nodes": [
            {
                "id": node.node_key,
                "name": node.name,
                "type": node.node_type,
                "resourceType": node.resource_type,
                "resourceId": node.resource_id,
                "resourceSnapshot": resource_snapshot(node)
                if freeze_resources
                else None,
                "commandVersionId": node.command_version_id,
                "commandVersion": {
                    field: deepcopy(getattr(node.command_version, field))
                    for field in (
                        "id",
                        "version",
                        "command_type",
                        "content",
                        "default_vars",
                        "argument_schema",
                        "timeout_seconds",
                        "become_enabled",
                        "check_mode_supported",
                        "output_extractors",
                    )
                }
                if node.command_version
                else None,
                "config": node.config or {},
                "inputMapping": node.input_mapping or {},
                "inputSchema": node.input_schema or [],
                "outputSchema": node.output_schema or [],
                "retryPolicy": node.retry_policy or {},
                "failurePolicy": node.failure_policy,
                "continueOnError": node.continue_on_error,
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


@transaction.atomic
def replace_graph(workflow_version, graph):
    workflow_version = (
        type(workflow_version).objects.select_for_update().get(pk=workflow_version.pk)
    )
    workflow_version.assert_mutable()
    errors = schema.validate_graph(graph)
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
            node_type=item.get("type") or NodeType.COMMAND,
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
