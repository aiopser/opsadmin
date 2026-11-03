"""Type-specific parameters are handed to the native executor without Jinja rendering."""
import json
import re


RESERVED = frozenset(
    {
        "command_content",
        "execution_source",
        "source_command_version_id",
        "source_module_version_id",
        "risk_level",
        "playbook_id",
        "playbook_name",
        "playbook_content",
        "module",
        "module_args",
        "gateway_id",
        "host_strategy",
        "ansible_forks",
        "serial_batch",
        "max_fail_percentage",
        "extra_vars",
        "check_mode",
        "bypass_host_gateway",
        "python_executable",
    }
)


def native_variable_values(kind, config):
    if kind == "module":
        field = "args" if "args" in config else "moduleArgs"
        if field in config:
            value = config[field]
            if not isinstance(value, (str, dict)):
                raise ValueError("模块参数必须为字符串或 JSON 对象")
            if isinstance(value, str) and re.match(r'^\s*\{\s*(?:"|}|$)', value):
                try:
                    parsed = json.loads(value)
                except ValueError as exc:
                    raise ValueError("模块参数必须为有效 JSON 对象") from exc
                if not isinstance(parsed, dict):
                    raise ValueError("模块参数必须为 JSON 对象")
        return {}
    field = {
        "script": "environment",
        "command": "environment",
        "playbook": "extraVars",
    }.get(kind)
    if not field or field not in config:
        return {}
    values = config[field]
    if not isinstance(values, dict):
        raise ValueError(f"{field} 必须为 JSON 对象")
    for key, value in values.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"{field} 参数名必须由字母、数字或下划线组成，且不能以数字开头")
        if key in RESERVED or key.startswith("ansible_"):
            raise ValueError(f"{field} 不能覆盖平台执行配置：{key}")
        if field == "environment" and type(value) not in {str, int, float, bool}:
            raise ValueError("脚本环境变量仅支持字符串、数字和布尔值")
    return values
