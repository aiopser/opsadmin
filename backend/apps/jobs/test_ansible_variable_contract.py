"""Ansible variables and orchestration outputs remain separate contracts."""
from types import SimpleNamespace

from common.workflow.schema import validate_graph
from apps.jobs.execution.plan_builder import (
    _extract_version_outputs,
    _node_command_spec,
)
from apps.jobs.serializers import validate_ansible_extra_vars
from rest_framework.exceptions import ValidationError
import pytest


@pytest.mark.parametrize("kind", ["quick_command", "playbook", "module"])
def test_runner_receives_inherited_variables_and_typed_overrides(kind):
    from apps.jobs.execution.plan_builder import _merge_node_vars
    from apps.ops.contracts import ExecutionPlan
    from apps.ops.executor import AnsibleExecutor

    defaults = {"message": "default", "enabled": True, "count": 1}
    node = SimpleNamespace(
        command_version=SimpleNamespace(default_vars=defaults, content="echo ok"),
        input_mapping=None,
    )
    run = SimpleNamespace(
        execution_kind=kind,
        input_vars={
            "extra_vars": {"message": "hello world", "count": 3, "items": ["a", "b"]}
        },
    )
    values = _merge_node_vars(run, node)
    captured = {}

    def runner(**options):
        captured.update(options["extravars"])
        options["event_handler"](
            {"event": "runner_on_ok", "event_data": {"host": "localhost", "res": {}}}
        )
        return SimpleNamespace(status="successful", rc=0)

    plan = ExecutionPlan(
        run_id=1,
        node_run_id=1,
        command_type="linux_shell",
        target_hosts=[],
        inventory="[all]\nlocalhost",
        playbook=[],
        extra_vars=values,
        env_vars={},
        private_data_dir="",
        timeout_seconds=30,
    )
    result = AnsibleExecutor(runner).execute(plan, lambda event: None, lambda: False)
    assert result.status == "success"
    assert captured["message"] == "hello world"
    assert captured["enabled"] is True
    assert captured["count"] == 3
    assert captured["items"] == ["a", "b"]
    assert defaults["count"] == 1


@pytest.mark.parametrize(
    "module",
    [
        "shell",
        "ansible.builtin.shell",
        "ansible.builtin.command",
        "ansible.builtin.raw",
    ],
)
def test_free_form_module_names_preserve_command_arguments(module):
    from apps.jobs.execution.plan_builder import build_source_playbook, _node_playbook

    run = SimpleNamespace(
        input_vars={
            "execution_source": "module",
            "module": module,
            "module_args": "echo hello world",
        }
    )
    task = build_source_playbook(run)[0]["tasks"][0]
    assert task[module] == {"_raw_params": "echo hello world"}
    node = SimpleNamespace(
        node_type="module",
        command_version=None,
        config={"module": module, "args": "echo hello world"},
    )
    workflow = SimpleNamespace(input_vars={})
    task = _node_playbook(workflow, node, _node_command_spec(node), {})[0]["tasks"][0]
    assert task[module] == {"_raw_params": "echo hello world"}


@pytest.mark.parametrize("kind", ["command", "script", "playbook", "module"])
def test_inline_ansible_steps_apply_output_rules(kind):
    node = SimpleNamespace(
        command_version=None,
        node_type=kind,
        config={"outputExtractors": [{"name": "release", "pattern": "RELEASE=(.*)"}]},
    )
    assert _extract_version_outputs("RELEASE=v2", _node_command_spec(node)) == {
        "release": "v2"
    }


def test_parameter_mapping_preserves_composite_templates_and_native_types(monkeypatch):
    from apps.jobs.execution.plan_builder import _merge_node_vars
    from apps.jobs import workflow_engine

    run = SimpleNamespace(
        input_vars={"dir": "/tmp", "file": "result", "count": 3},
        execution_kind="workflow",
        node_runs=SimpleNamespace(all=lambda: []),
    )
    monkeypatch.setattr(
        workflow_engine,
        "runtime_context",
        lambda run, nodes: {"inputs": run.input_vars},
    )
    node = SimpleNamespace(
        command_version=None,
        config={},
        input_mapping={
            "path": "{{ inputs.dir }}/{{ inputs.file }}",
            "label": "{{ inputs.dir }} {{ inputs.file }}",
            "count": "{{ inputs.count }}",
        },
    )
    values = _merge_node_vars(run, node)
    assert values["path"] == "/tmp/result"
    assert values["label"] == "/tmp result"
    assert values["count"] == 3


def test_step_output_rules_override_legacy_resource_rules():
    resource = SimpleNamespace(
        output_extractors=[{"name": "old", "pattern": r"OLD=(\w+)"}]
    )
    node = SimpleNamespace(
        command_version=resource,
        config={"outputExtractors": [{"name": "release", "pattern": r"RELEASE=(\w+)"}]},
    )
    spec = _node_command_spec(node)
    assert _extract_version_outputs("RELEASE=v2 OLD=v1", spec) == {"release": "v2"}
    assert resource.output_extractors[0]["name"] == "old"


def test_invalid_step_output_regex_is_rejected_before_publish():
    graph = {
        "nodes": [
            {"id": "start", "type": "start"},
            {
                "id": "work",
                "type": "script",
                "commandVersionId": 1,
                "config": {"outputExtractors": [{"name": "value", "pattern": "("}]},
            },
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "work"},
            {"id": "b", "source": "work", "target": "end"},
        ],
    }
    assert any("输出提取" in error for error in validate_graph(graph))


@pytest.mark.parametrize(
    "key", ["command_content", "module_args", "gateway_id", "extra_vars"]
)
def test_extra_vars_cannot_replace_platform_execution_configuration(key):
    with pytest.raises(ValidationError):
        validate_ansible_extra_vars({key: "override"})


@pytest.mark.parametrize(
    "command_type,task_key,extra_key",
    [
        ("linux_shell", "ansible.builtin.shell", "ansible.builtin.shell"),
        (
            "windows_powershell",
            "ansible.windows.win_shell",
            "ansible.windows.win_shell",
        ),
    ],
)
def test_shell_body_is_inlined_for_ansible_templating(
    command_type, task_key, extra_key
):
    """脚本正文内联进任务参数，{{ 变量 }} 由 extra_vars 模板求值而非原样透传。

    若经 "{{ command_content }}" 变量注入，Ansible 不做递归渲染，
    正文中的 {{ }} 会被原样交给 shell（历史缺陷）。
    """
    from apps.ops.workflow.playbooks import build_playbook

    body = 'echo "RELEASE={{ version }}"'
    version = SimpleNamespace(command_type=command_type, content=body)
    playbook = build_playbook(version, {"command_content": body, "version": "1.2.3"})
    assert playbook[0]["tasks"][0][task_key] == body
    assert playbook[0]["tasks"][0][extra_key] == body


def test_shell_task_environment_injects_scalar_extra_vars_only():
    """脚本 = 原生 shell：$var 直接读环境变量。

    标量 extra_vars（资源默认变量/任务单参数/步骤映射）进 environment；
    嵌套结构与平台保留 key 剔除。
    """
    from apps.ops.workflow.playbooks import build_playbook, shell_task_environment

    version = SimpleNamespace(command_type="linux_shell", content="echo $version")
    playbook = build_playbook(
        version,
        {
            "command_content": "echo $version",
            "version": "1.2.3",
            "enabled": True,
            "retries": 3,
            "items": ["a", "b"],
            "target": {"host": "h1"},
            "gateway_id": 7,
            "execution_source": "workflow",
            "module_args": "k=v",
        },
    )
    assert playbook[0]["tasks"][0]["environment"] == {
        "version": "1.2.3",
        "enabled": "True",
        "retries": "3",
    }
    assert shell_task_environment(None) == {}
