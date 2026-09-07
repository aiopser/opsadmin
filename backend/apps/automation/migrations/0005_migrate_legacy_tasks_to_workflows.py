from django.db import migrations


TYPE_MAP = {
    "script": "script",
    "command": "command",
    "job": "command",
    "jenkins": "jenkins",
    "api": "api",
    "approval": "approval",
    "notify": "notify",
    "alert": "notify",
}


def migrate_legacy_tasks(apps, schema_editor):
    TaskTemplate = apps.get_model("automation", "TaskTemplate")
    WorkflowTemplate = apps.get_model("automation", "WorkflowTemplate")
    WorkflowVersion = apps.get_model("automation", "WorkflowVersion")
    WorkflowNode = apps.get_model("automation", "WorkflowNode")
    WorkflowEdge = apps.get_model("automation", "WorkflowEdge")

    for legacy in TaskTemplate.objects.all().iterator():
        code = legacy.code
        if WorkflowTemplate.objects.filter(code=code).exists():
            code = f"legacy_task_{legacy.pk}_{code}"[:128]
        workflow = WorkflowTemplate.objects.create(
            name=legacy.name,
            code=code,
            description=legacy.description,
            owner_team=legacy.project,
            # Legacy resource references cannot be converted reliably. Keep every
            # imported definition editable until an operator validates and
            # publishes it in the new designer.
            status="draft",
            created_by_id=legacy.created_by_id,
            updated_by_id=legacy.updated_by_id,
        )
        version = WorkflowVersion.objects.create(
            workflow=workflow,
            version=1,
            status="draft",
            input_schema=legacy.params or [],
            validation_report=[
                {
                    "level": "warning",
                    "code": "legacy_import_requires_review",
                    "message": (
                        "Imported from the legacy task system. Review node types, "
                        "resource bindings and parameters before publishing."
                    ),
                }
            ],
            created_by_id=legacy.created_by_id,
        )
        start = WorkflowNode.objects.create(
            workflow_version=version,
            node_key="start",
            name="开始",
            node_type="start",
            order_index=0,
            timeout_seconds=60,
        )
        previous = start
        graph_nodes = [
            {
                "id": "start",
                "name": "开始",
                "type": "start",
                "config": {},
                "timeoutSeconds": 60,
            }
        ]
        graph_edges = []
        for index, subtask in enumerate(
            legacy.subtasks.all().order_by("order", "id"), start=1
        ):
            node_key = f"legacy_{subtask.pk}"
            node_type = TYPE_MAP.get(subtask.type, "script")
            config = {
                "content": subtask.script or "",
                "hosts": subtask.hosts or legacy.default_hosts,
                "user": subtask.user or legacy.default_user,
                "legacyType": subtask.type,
            }
            node = WorkflowNode.objects.create(
                workflow_version=version,
                node_key=node_key,
                name=subtask.name,
                node_type=node_type,
                config=config,
                order_index=index,
                timeout_seconds=max(int(subtask.timeout_seconds or 60), 1),
                failure_policy=(
                    "ignore"
                    if legacy.exec_strategy == "skip_on_fail"
                    else "retry"
                    if legacy.exec_strategy == "retry"
                    else "stop"
                ),
            )
            edge_key = f"edge_{previous.node_key}_{node_key}"
            WorkflowEdge.objects.create(
                workflow_version=version,
                edge_key=edge_key,
                source_node=previous,
                target_node=node,
                order_index=index,
            )
            graph_nodes.append(
                {
                    "id": node_key,
                    "name": subtask.name,
                    "type": node_type,
                    "config": config,
                    "timeoutSeconds": max(int(subtask.timeout_seconds or 60), 1),
                    "failurePolicy": node.failure_policy,
                }
            )
            graph_edges.append(
                {"id": edge_key, "source": previous.node_key, "target": node_key}
            )
            previous = node

        end = WorkflowNode.objects.create(
            workflow_version=version,
            node_key="end",
            name="结束",
            node_type="end",
            order_index=legacy.subtasks.count() + 1,
            timeout_seconds=60,
        )
        edge_key = f"edge_{previous.node_key}_end"
        WorkflowEdge.objects.create(
            workflow_version=version,
            edge_key=edge_key,
            source_node=previous,
            target_node=end,
            order_index=legacy.subtasks.count() + 1,
        )
        graph_nodes.append(
            {
                "id": "end",
                "name": "结束",
                "type": "end",
                "config": {},
                "timeoutSeconds": 60,
            }
        )
        graph_edges.append(
            {"id": edge_key, "source": previous.node_key, "target": "end"}
        )
        version.graph_snapshot = {"nodes": graph_nodes, "edges": graph_edges}
        version.save(update_fields=["graph_snapshot"])


class Migration(migrations.Migration):
    dependencies = [("automation", "0004_workflow_graph_resources")]

    operations = [
        migrations.RunPython(migrate_legacy_tasks, migrations.RunPython.noop),
    ]
