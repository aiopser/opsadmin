"""Build execution definitions exclusively from a run's persisted graph."""

from copy import deepcopy
from types import SimpleNamespace


def execution_node(node_run):
    graph = node_run.workflow_run.graph_snapshot or {}
    item = next(
        (
            item
            for item in graph.get("nodes", [])
            if item.get("id") == node_run.node_key
        ),
        None,
    )
    if item is None:
        raise ValueError("Run snapshot does not contain this node")
    command = item.get("commandVersion")
    return SimpleNamespace(
        node_key=item["id"],
        node_type=item["type"],
        name=item.get("name") or item["id"],
        config=deepcopy(item.get("config") or {}),
        input_mapping=deepcopy(item.get("inputMapping") or {}),
        resource_id=item.get("resourceId"),
        resource_snapshot=deepcopy(item.get("resourceSnapshot")),
        timeout_seconds=item["timeoutSeconds"],
        command_version=SimpleNamespace(**deepcopy(command)) if command else None,
    )


def execution_resource(node_run):
    from apps.automation.models import (
        ApiEndpoint,
        JenkinsJob,
        JenkinsServer,
        NotificationChannel,
        NotificationTemplate,
    )

    node = execution_node(node_run)
    if not node.resource_snapshot:
        raise ValueError("Run snapshot does not contain the resource definition")
    fields = deepcopy(node.resource_snapshot["definition"])
    if node.node_type == "api":
        live = ApiEndpoint.objects.get(pk=fields["id"], is_active=True)
        if any(
            getattr(live, name) != fields[name]
            for name in ("url", "username", "auth_type")
        ):
            raise ValueError("API credential binding changed since publication")
        resource = ApiEndpoint(**fields)
        resource.secret_encrypted = live.secret_encrypted
        return resource
    if node.node_type == "jenkins":
        server_fields = fields.pop("server")
        JenkinsJob.objects.get(pk=fields["id"], is_active=True)
        live = JenkinsServer.objects.get(pk=server_fields["id"], is_active=True)
        if any(
            getattr(live, name) != server_fields[name]
            for name in ("base_url", "username")
        ):
            raise ValueError("Jenkins credential binding changed since publication")
        server = JenkinsServer(**server_fields)
        server.token_encrypted = live.token_encrypted
        return JenkinsJob(**fields, server=server)
    if node.node_type == "notify":
        channel_fields = fields.pop("channel")
        NotificationTemplate.objects.get(pk=fields["id"], is_active=True)
        live = NotificationChannel.objects.get(pk=channel_fields["id"], is_active=True)
        if live.channel_type != channel_fields["channel_type"]:
            raise ValueError(
                "Notification credential binding changed since publication"
            )
        channel = NotificationChannel(**channel_fields)
        channel.secret_encrypted = live.secret_encrypted
        return NotificationTemplate(**fields, channel=channel)
    raise ValueError("Unsupported resource type")


def ensure_node_runs(run):
    from apps.jobs.models import NodeRun
    definitions = {node.node_key: node for node in run.workflow_version.nodes.select_related("command_version").all()} if run.workflow_version_id else {}
    existing = {node.node_key: node for node in run.node_runs.all()}
    for item in (run.graph_snapshot or {}).get("nodes", []):
        key = str(item["id"])
        if key in existing:
            continue
        definition = definitions.get(key)
        existing[key] = NodeRun.objects.create(
            workflow_run=run, workflow_node=definition,
            command_version=definition.command_version if definition else None,
            node_key=key, node_name=item.get("name") or key, node_type=item["type"],
            config_snapshot=deepcopy(item.get("config") or {}), input_vars=deepcopy(item.get("inputMapping") or {}),
        )
    return existing
