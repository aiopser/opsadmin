"""Business contracts for the shared graph protocol and frozen definitions."""

from copy import deepcopy

import pytest

from common.workflow.schema import validate_graph


def valid_graph():
    return {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "work", "type": "command", "timeoutSeconds": 60},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "work"},
            {"id": "b", "source": "work", "target": "end"},
        ],
    }


def test_shared_validation_preserves_valid_input():
    graph = valid_graph()
    original = deepcopy(graph)
    assert validate_graph(graph) == []
    assert graph == original


@pytest.mark.parametrize(
    "node", [None, [], "old", {"id": "work", "type": "unknown", "timeoutSeconds": 60}]
)
def test_rejects_unknown_or_malformed_nodes(node):
    graph = valid_graph()
    graph["nodes"][1] = node
    assert validate_graph(graph)


@pytest.mark.parametrize("timeout", ["invalid", True, 1.5, -1, 0])
def test_rejects_invalid_timeout(timeout):
    graph = valid_graph()
    graph["nodes"][1]["timeoutSeconds"] = timeout
    assert validate_graph(graph)


def test_rejects_reachable_cycle():
    graph = valid_graph()
    graph["nodes"].append({"id": "loop", "type": "command", "timeoutSeconds": 60})
    graph["edges"].extend(
        [
            {"id": "c", "source": "work", "target": "loop"},
            {"id": "d", "source": "loop", "target": "work"},
        ]
    )
    assert any("环" in error for error in validate_graph(graph))


@pytest.mark.parametrize(
    "edge", [None, [], {"id": "bad", "source": "work", "target": "missing"}]
)
def test_rejects_malformed_or_dangling_edges(edge):
    graph = valid_graph()
    graph["edges"].append(edge)
    assert validate_graph(graph)


def test_rejects_legacy_linear_graph():
    assert validate_graph(
        {
            "nodes": [{"id": "task", "type": "command", "timeoutSeconds": 60}],
            "edges": [],
        }
    )


@pytest.mark.parametrize(
    "expression, expected",
    [
        ("inputs.environment == 'production'", True),
        ("inputs.environment == 'development'", False),
        ("inputs.count > 1 and inputs.count < 5", True),
    ],
)
def test_condition_data_comparisons(expression, expected):
    from common.workflow.conditions import expression_is_true

    assert (
        expression_is_true(
            expression, {"inputs": {"environment": "production", "count": 3}}
        )
        is expected
    )


@pytest.mark.parametrize(
    "expression",
    [
        "inputs.clear()",
        "inputs.__class__",
        "range(100)",
        "inputs.missing == 1",
        "'x' * 999999999",
    ],
)
def test_condition_rejects_calls_private_access_and_invalid_data(expression):
    from common.workflow.conditions import InvalidCondition, expression_is_true

    with pytest.raises(InvalidCondition):
        expression_is_true(expression, {"inputs": {}})


@pytest.mark.django_db
def test_published_command_cannot_be_edited_or_reverted_to_draft():
    from apps.automation.models import CommandAtom, CommandVersion

    atom = CommandAtom.objects.create(name="immutable", code="immutable")
    version = CommandVersion.objects.create(
        command=atom, version=1, command_type="linux_shell", content="echo original"
    )
    version.publish(None)
    version.content = "echo changed"
    with pytest.raises(ValueError):
        version.save()
    version.refresh_from_db()
    version.status = "draft"
    with pytest.raises(ValueError):
        version.save(update_fields=["status"])
    version.refresh_from_db()
    assert version.content == "echo original"


@pytest.mark.django_db
def test_published_command_queryset_cannot_change_content():
    from apps.automation.models import CommandAtom, CommandVersion

    atom = CommandAtom.objects.create(name="bulk", code="bulk")
    version = CommandVersion.objects.create(
        command=atom, version=1, command_type="linux_shell", content="echo original"
    )
    version.publish(None)
    with pytest.raises(ValueError):
        CommandVersion.objects.filter(pk=version.pk).update(content="echo changed")


@pytest.mark.django_db
def test_published_definition_survives_workflow_deletion():
    from apps.automation.models import (
        CommandAtom,
        CommandVersion,
        WorkflowTemplate,
        WorkflowVersion,
    )
    from apps.automation.workflow_graph import replace_graph
    from apps.jobs.execution.snapshots import execution_node
    from apps.jobs.models import NodeRun, WorkflowRun, WorkerPool
    from apps.jobs.workflow_engine import runtime_context

    command = CommandAtom.objects.create(name="frozen", code="frozen")
    command_version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="linux_shell",
        content="echo frozen",
        default_vars={"value": "original"},
    )
    command_version.publish(None)
    template = WorkflowTemplate.objects.create(name="frozen", code="frozen")
    version = WorkflowVersion.objects.create(
        workflow=template, version=1, global_vars={"environment": "test"}
    )
    graph = valid_graph()
    graph["nodes"][1]["commandVersionId"] = command_version.pk
    assert replace_graph(version, graph) == []
    version.publish(None)
    pool = WorkerPool.objects.create(code="frozen", name="frozen", queue_name="ansible")
    run = WorkflowRun.objects.create(
        worker_pool=pool,
        workflow_version=version,
        graph_snapshot=deepcopy(version.graph_snapshot),
    )
    node = NodeRun.objects.create(workflow_run=run, node_key="work")
    with pytest.raises(ValueError):
        WorkflowVersion.objects.filter(pk=version.pk).update(
            global_vars={"environment": "changed"}
        )
    template.delete()
    command.delete()
    run.refresh_from_db()
    node.refresh_from_db()
    assert run.workflow_version_id is None
    assert execution_node(node).command_version.content == "echo frozen"
    assert runtime_context(run, {})["global"] == {"environment": "test"}


@pytest.mark.django_db
def test_api_resource_uses_frozen_body_and_rechecks_credential_binding():
    from apps.automation.models import ApiEndpoint, WorkflowTemplate, WorkflowVersion
    from apps.automation.workflow_graph import replace_graph
    from apps.jobs.execution.snapshots import execution_resource
    from apps.jobs.models import NodeRun, WorkflowRun, WorkerPool

    endpoint = ApiEndpoint.objects.create(
        name="api",
        url="https://example.test/api",
        body="original",
        secret_encrypted="encrypted-reference-only",
    )
    template = WorkflowTemplate.objects.create(name="api", code="api")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = valid_graph()
    graph["nodes"][1].update(type="api", resourceId=endpoint.pk)
    assert replace_graph(version, graph) == []
    version.publish(None)
    assert "encrypted-reference-only" not in str(version.graph_snapshot)
    pool = WorkerPool.objects.create(code="api", name="api", queue_name="ansible")
    run = WorkflowRun.objects.create(
        worker_pool=pool,
        workflow_version=version,
        graph_snapshot=version.graph_snapshot,
    )
    node = NodeRun.objects.create(workflow_run=run, node_key="work")
    ApiEndpoint.objects.filter(pk=endpoint.pk).update(body="changed")
    template.delete()
    node.refresh_from_db()
    assert execution_resource(node).body == "original"
    ApiEndpoint.objects.filter(pk=endpoint.pk).update(url="https://changed.test/api")
    with pytest.raises(ValueError, match="binding changed"):
        execution_resource(node)


@pytest.mark.parametrize("mode", ["steps", "bpmn"])
def test_serializer_rejects_old_editor_modes(mode):
    from apps.automation.serializers import WorkflowVersionSerializer

    serializer = WorkflowVersionSerializer(data={"editorMode": mode})
    assert not serializer.is_valid()
    assert "editorMode" in serializer.errors or "editor_mode" in serializer.errors
