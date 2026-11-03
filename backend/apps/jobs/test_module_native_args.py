from types import SimpleNamespace

import pytest

from apps.jobs.execution.plan_builder import (
    build_source_playbook,
    parse_module_args,
    serialize_module_args,
)


def test_native_json_module_arguments_keep_scalar_types():
    values = {
        "enabled": False,
        "count": 2,
        "empty": None,
        "text": "001",
        "items": ["a"],
    }
    assert parse_module_args(serialize_module_args(values)) == values


def test_native_json_freeform_module_uses_real_argument_names():
    run = SimpleNamespace(
        input_vars={
            "execution_source": "module",
            "module": "ansible.builtin.shell",
            "module_args": '{"cmd":"echo hello", "chdir":"/tmp"}',
        }
    )
    assert build_source_playbook(run)[0]["tasks"][0]["ansible.builtin.shell"] == {
        "cmd": "echo hello",
        "chdir": "/tmp",
    }


def test_duplicate_module_argument_names_are_rejected():
    with pytest.raises(ValueError):
        parse_module_args("state=started state=stopped")


def test_legacy_shell_group_command_is_not_json():
    from apps.jobs.execution.plan_builder import resolve_module_arguments

    assert resolve_module_arguments("shell", "{ echo hello; }") == {
        "_raw_params": "{ echo hello; }"
    }
