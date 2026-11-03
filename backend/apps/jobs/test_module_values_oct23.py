import shlex

from apps.jobs.execution.plan_builder import parse_module_args, serialize_module_args


def test_module_values_preserve_json_objects_arrays_and_scalar_strings():
    arguments = shlex.join(
        [
            'headers={"X-Name":"hello world","nested":{"enabled":true}}',
            'name=["nginx","git"]',
            "comment=true",
            "version=001",
        ]
    )
    assert parse_module_args(arguments) == {
        "headers": {"X-Name": "hello world", "nested": {"enabled": True}},
        "name": ["nginx", "git"],
        "comment": "true",
        "version": "001",
    }


def test_module_non_json_brackets_remain_literal_strings():
    assert parse_module_args(shlex.join(["regexp=[a-z]+", "msg={value}"])) == {
        "regexp": "[a-z]+",
        "msg": "{value}",
    }


def test_default_module_values_roundtrip_without_python_repr():
    defaults = {
        "headers": {"Agent": "agent's test"},
        "name": ["nginx", "git"],
        "comment": "hello world",
    }
    assert parse_module_args(serialize_module_args(defaults)) == defaults
