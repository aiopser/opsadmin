from types import SimpleNamespace
import pytest

from apps.jobs.execution.plan_builder import _merge_node_vars


def node(kind, config, mapping=None):
    return SimpleNamespace(
        node_type=kind,
        command_version=SimpleNamespace(
            default_vars={"version": "default"}, content="echo ok"
        ),
        input_mapping=mapping,
        config=config,
    )


@pytest.mark.parametrize(
    "kind,key", [("script", "environment"), ("playbook", "extraVars")]
)
def test_native_parameters_keep_ansible_expressions_literal(kind, key):
    run = SimpleNamespace(input_vars={"version": "task"}, execution_kind="workflow")
    values = _merge_node_vars(
        run, node(kind, {key: {"version": "step", "host": "{{ inventory_hostname }}"}})
    )
    assert values["version"] == "step"
    assert values["host"] == "{{ inventory_hostname }}"


def test_native_parameters_do_not_replace_other_types_configuration():
    run = SimpleNamespace(input_vars={"version": "task"}, execution_kind="workflow")
    assert (
        _merge_node_vars(run, node("script", {"extraVars": {"version": "wrong"}}))[
            "version"
        ]
        == "task"
    )


def test_native_parameters_reject_reserved_execution_fields():
    run = SimpleNamespace(input_vars={}, execution_kind="workflow")
    with pytest.raises(ValueError):
        _merge_node_vars(
            run, node("playbook", {"extraVars": {"command_content": "replaced"}})
        )


def test_shell_environment_rejects_nested_values():
    run = SimpleNamespace(input_vars={}, execution_kind="workflow")
    with pytest.raises(ValueError):
        _merge_node_vars(
            run, node("script", {"environment": {"version": {"bad": True}}})
        )


@pytest.mark.parametrize(
    "kind,config",
    [
        ("script", {"environment": {"nested": []}}),
        ("playbook", {"extraVars": {"command_content": "bad"}}),
        ("playbook", {"extraVars": []}),
    ],
)
def test_graph_rejects_invalid_native_parameters_before_execution(kind, config):
    from common.workflow.schema import validate_graph

    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "step", "type": kind, "config": config},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "step"},
            {"id": "b", "source": "step", "target": "end"},
        ],
    }
    assert any(
        "environment" in error or "extraVars" in error or "环境变量" in error
        for error in validate_graph(graph)
    )


@pytest.mark.parametrize("value", [[], 12, True, None, '{"name":'])
def test_module_parameter_validation_rejects_invalid_value(value):
    from common.workflow.native_parameters import native_variable_values

    with pytest.raises(ValueError):
        native_variable_values("module", {"args": value})


def test_module_native_jinja_is_not_platform_rendered():
    from common.workflow.native_parameters import native_variable_values

    assert (
        native_variable_values("module", {"args": "{{ executable }} --version"}) == {}
    )
