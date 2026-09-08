import json
import os
import re
import shlex
import shutil
import tempfile
from types import SimpleNamespace
import yaml
from apps.automation.models import CommandVersion, WorkflowNode
from apps.cmdb.crypto import decrypt_secret
from apps.ops.workflow.inventory import build_inventory
from apps.ops.workflow.playbooks import build_playbook
from apps.jobs.input_secrets import resolve_workflow_inputs
from apps.jobs.models import Gateway
from apps.jobs.quick_commands import is_quick_command_workflow_version
from apps.jobs.settings_service import get_engine_settings


FREE_FORM_MODULES = frozenset({"shell", "command", "script", "raw"})


INTERNAL_INPUT_VAR_KEYS = frozenset(
    {
        "command_content",
        "execution_source",
        "source_command_version_id",
        "risk_level",
        "playbook_id",
        "playbook_name",
        "playbook_content",
        "module",
        "module_args",
        "gateway_id",
        "bypass_host_gateway",
        "host_strategy",
        "ansible_forks",
        "serial_batch",
        "max_fail_percentage",
    }
)


class InvalidSourcePlaybook(ValueError):
    """execution_source 为 playbook/module 时资产内容无法构造可执行计划。"""


def parse_module_args(module_args):
    """解析 Ansible ad-hoc 风格参数字符串（k=v k2=v2）为 dict。"""
    parsed = {}
    for token in shlex.split(module_args or ""):
        key, separator, value = token.partition("=")
        if not separator or not key:
            raise InvalidSourcePlaybook(f"Module 参数格式不合法: {token}")
        parsed[key] = value
    return parsed


def build_source_playbook(run):
    """按 execution_source 构造真实 playbook；返回 None 表示沿用节点自身命令。

    - playbook: 解析 Playbook 资产 YAML，强制 hosts=all（目标由主机快照决定）
    - module: 构造单任务 ad-hoc 风格 play
    """
    input_vars = resolve_workflow_inputs(run)
    source = input_vars.get("execution_source")
    if source == "playbook":
        content = str(input_vars.get("playbook_content") or "")
        try:
            plays = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise InvalidSourcePlaybook(f"Playbook YAML 解析失败: {exc}") from exc
        if isinstance(plays, dict):
            plays = [plays]
        if (
            not isinstance(plays, list)
            or not plays
            or not all(isinstance(play, dict) for play in plays)
        ):
            raise InvalidSourcePlaybook("Playbook 内容必须是 play 列表")
        normalized = []
        for play in plays:
            play = dict(play)
            play["hosts"] = "all"
            normalized.append(play)
        return normalized
    if source == "module":
        module = str(input_vars.get("module") or "").strip()
        module_args = str(input_vars.get("module_args") or "")
        if not module:
            raise InvalidSourcePlaybook("缺少 Module 名称")
        if module in FREE_FORM_MODULES:
            task_args = {"_raw_params": module_args}
        else:
            task_args = parse_module_args(module_args)
        return [
            {
                "hosts": "all",
                "gather_facts": False,
                "tasks": [
                    {
                        "name": f"Run Ansible module {module}",
                        module: task_args,
                        "register": "command_result",
                    }
                ],
            }
        ]
    return None


class InvalidGateway(ValueError):
    """选择的网关不存在或不可用。"""


def _load_gateway(gateway_id):
    try:
        gateway = Gateway.objects.get(id=gateway_id)
    except Gateway.DoesNotExist as exc:
        raise InvalidGateway("所选网关不存在") from exc
    if gateway.status != Gateway.Status.NORMAL:
        raise InvalidGateway(f"网关「{gateway.name}」状态异常，请先在作业配置中测试连接")
    return gateway


def _gateway_proxy_vars(gateway, private_data_dir="", key_filename="gateway_key"):
    host, _, port = gateway.address.rpartition(":")
    host = host or gateway.address
    try:
        port = int(port or 22)
    except ValueError:
        port = 22
    user = gateway.username or "root"
    secret = (
        decrypt_secret(gateway.secret_encrypted) if gateway.secret_encrypted else ""
    )

    if gateway.auth_type == Gateway.AuthType.KEY:
        if not secret:
            raise InvalidGateway(f"网关「{gateway.name}」未配置密钥")
        if not private_data_dir:
            raise InvalidGateway(f"网关「{gateway.name}」缺少 Runner 临时工作目录")
        key_path = os.path.join(private_data_dir, key_filename)
        with open(key_path, "w", encoding="utf-8") as key_file:
            key_file.write(secret)
        os.chmod(key_path, 0o600)
        inner = (
            f"ssh -i {shlex.quote(key_path)} -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -p {port} -W %h:%p {user}@{host}"
        )
    else:
        if not secret:
            raise InvalidGateway(f"网关「{gateway.name}」未配置密码")
        inner = (
            f"sshpass -p {shlex.quote(secret)} ssh -o StrictHostKeyChecking=no "
            f"-o UserKnownHostsFile=/dev/null -p {port} -W %h:%p {user}@{host}"
        )
    return {"ansible_ssh_common_args": f'-o ProxyCommand="{inner}"'}


def prepare_gateway_execution(input_vars):
    """按 input_vars 中的 gateway_id 准备网关通道执行参数。

    返回 (group_vars, private_data_dir)：未选网关时为 ({}, "")。
    不选网关即默认由本机 ansible-runner（跳板机）直连目标主机；
    选网关时通过 SSH ProxyCommand 经网关转发：
    - 密码认证：sshpass 代理建连
    - 密钥认证：临时密钥文件 + ssh -i（随 private_data_dir 执行后自动清理）
    """
    gateway_id = (input_vars or {}).get("gateway_id")
    if not gateway_id:
        return {}, ""
    gateway = _load_gateway(gateway_id)
    private_data_dir = (
        tempfile.mkdtemp(prefix="devops-gateway-")
        if gateway.auth_type == Gateway.AuthType.KEY
        else ""
    )
    try:
        return _gateway_proxy_vars(gateway, private_data_dir), private_data_dir
    except Exception:
        if private_data_dir:
            shutil.rmtree(private_data_dir, ignore_errors=True)
        raise


def prepare_host_gateway_execution(host_snapshots, input_vars=None):
    """Apply a run-level gateway override or each host's default gateway.

    Returns ``(prepared_hosts, group_vars, private_data_dir)``. Gateway proxy
    variables are written per host so one inventory may safely contain hosts
    from multiple network regions.
    """
    snapshots = [dict(host) for host in (host_snapshots or [])]
    if (input_vars or {}).get("bypass_host_gateway"):
        return snapshots, {}, ""
    override_gateway_id = (input_vars or {}).get("gateway_id")
    gateway_ids = {
        override_gateway_id or (host.get("variables") or {}).get("gateway_ref_id")
        for host in snapshots
        if override_gateway_id or (host.get("variables") or {}).get("gateway_ref_id")
    }
    if not gateway_ids:
        return snapshots, {}, ""

    gateways = {gateway_id: _load_gateway(gateway_id) for gateway_id in gateway_ids}
    key_gateways = [
        gateway
        for gateway in gateways.values()
        if gateway.auth_type == Gateway.AuthType.KEY
    ]
    private_data_dir = (
        tempfile.mkdtemp(prefix="devops-gateway-") if key_gateways else ""
    )
    try:
        proxy_vars = {
            gateway_id: _gateway_proxy_vars(
                gateway,
                private_data_dir,
                key_filename=f"gateway_{gateway_id}_key",
            )
            for gateway_id, gateway in gateways.items()
        }
    except Exception:
        if private_data_dir:
            shutil.rmtree(private_data_dir, ignore_errors=True)
        raise

    prepared_hosts = []
    for host in snapshots:
        gateway_id = override_gateway_id or (host.get("variables") or {}).get("gateway_ref_id")
        if not gateway_id:
            prepared_hosts.append(host)
            continue
        if str(host.get("connection_type") or "ssh").lower() != "ssh":
            raise InvalidGateway("Gateway proxy is only supported for SSH hosts")
        variables = dict(host.get("variables") or {})
        variables.update(proxy_vars[gateway_id])
        host["variables"] = variables
        prepared_hosts.append(host)
    return prepared_hosts, {}, private_data_dir


def build_gateway_inventory(host_snapshots, input_vars=None):
    prepared_hosts, group_vars, private_data_dir = prepare_host_gateway_execution(
        host_snapshots,
        input_vars,
    )
    private_data_dir = private_data_dir or tempfile.mkdtemp(prefix="devops-inventory-")
    try:
        return build_inventory(prepared_hosts, group_vars, key_directory=private_data_dir), private_data_dir
    except Exception:
        if private_data_dir:
            shutil.rmtree(private_data_dir, ignore_errors=True)
        raise


COMMAND_OUTPUT_MARKER = "###DEVOPS_CMD###"


def wrap_command_lines_with_markers(command_content, command_type):
    """为多行命令的每条有效行注入输出分段标记。

    标记行由 echo / Write-Output 在真实命令之前打印，前端解析 stdout
    中的标记即可区分每行命令各自的输出；单行命令原样返回不注入。
    """
    lines = [line for line in str(command_content or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return command_content
    is_powershell = command_type == CommandVersion.CommandType.WINDOWS_POWERSHELL
    total = len(lines)
    wrapped = []
    for index, line in enumerate(lines, start=1):
        marker = f"{COMMAND_OUTPUT_MARKER} [{index}/{total}] {line.strip()}"
        if is_powershell:
            escaped = marker.replace("'", "''")
            wrapped.append(f"Write-Output '{escaped}'")
        else:
            wrapped.append(f"echo {shlex.quote(marker)}")
        wrapped.append(line)
    return "\n".join(wrapped)


def _merge_node_vars(run, node):
    extra_vars = {}
    command_version = node.command_version
    if command_version and isinstance(command_version.default_vars, dict):
        extra_vars.update(command_version.default_vars)
    resolved_inputs = resolve_workflow_inputs(run)
    if isinstance(resolved_inputs, dict):
        extra_vars.update(resolved_inputs)
    if isinstance(node.input_mapping, dict):
        from apps.jobs.node_executors import render_value
        from apps.jobs.workflow_engine import runtime_context

        node_runs = {
            item.node_key: item for item in run.node_runs.all() if item.node_key
        }
        extra_vars.update(
            render_value(node.input_mapping, runtime_context(run, node_runs))
        )
    if command_version:
        # Resource source is immutable after publish. Runtime inputs may override
        # declared variables, but never the executable body itself.
        workflow_version = getattr(run, "workflow_version", None)
        if workflow_version is not None and is_quick_command_workflow_version(
            workflow_version
        ):
            # Quick-command workflows carry a literal "{{ command_content }}"
            # placeholder body; the real command is injected via run inputs.
            # Overwriting with the placeholder makes the variable reference
            # itself and triggers infinite Ansible templating recursion.
            extra_vars.setdefault("command_content", command_version.content)
        else:
            extra_vars["command_content"] = command_version.content
    elif isinstance(node.config, dict):
        extra_vars.setdefault("command_content", node.config.get("content") or "")
    return extra_vars


def _node_command_spec(node):
    if node.command_version:
        return node.command_version
    config = node.config or {}
    node_type = node.node_type
    if node_type in {WorkflowNode.NodeType.COMMAND, WorkflowNode.NodeType.SCRIPT}:
        language = config.get("language") or "linux_shell"
        command_type = {
            "shell": CommandVersion.CommandType.LINUX_SHELL,
            "linux_shell": CommandVersion.CommandType.LINUX_SHELL,
            "powershell": CommandVersion.CommandType.WINDOWS_POWERSHELL,
            "python": CommandVersion.CommandType.PYTHON,
        }.get(language, CommandVersion.CommandType.LINUX_SHELL)
        return SimpleNamespace(
            command_type=command_type,
            content=config.get("content") or "",
            default_vars={},
        )
    if node_type == WorkflowNode.NodeType.PLAYBOOK:
        return SimpleNamespace(
            command_type=CommandVersion.CommandType.PLAYBOOK,
            content=config.get("content") or "",
            default_vars={},
        )
    if node_type == WorkflowNode.NodeType.MODULE:
        return SimpleNamespace(
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content=config.get("module") or "",
            default_vars={},
        )
    raise ValueError(f"Node type {node_type} is not an Ansible node")


def _node_playbook(run, node, command_spec, extra_vars):
    config = node.config or {}
    has_version = bool(getattr(node, "command_version", None))
    if node.node_type == WorkflowNode.NodeType.PLAYBOOK:
        try:
            source = (
                command_spec.content
                if has_version
                else config.get("content") or command_spec.content
            )
            plays = yaml.safe_load(source or "")
        except yaml.YAMLError as exc:
            raise InvalidSourcePlaybook(f"Playbook YAML 解析失败: {exc}") from exc
        if isinstance(plays, dict):
            plays = [plays]
        if not isinstance(plays, list) or not plays:
            raise InvalidSourcePlaybook("Playbook 内容必须是非空 play 列表")
        normalized_plays = [
            {**play, "hosts": "all"} for play in plays if isinstance(play, dict)
        ]
        if getattr(command_spec, "become_enabled", False):
            for play in normalized_plays:
                play["become"] = True
        return normalized_plays
    if node.node_type == WorkflowNode.NodeType.MODULE:
        module = str(
            command_spec.content
            if has_version
            else config.get("module") or command_spec.content
        ).strip()
        module_args = (
            config.get("args")
            or config.get("moduleArgs")
            or command_spec.default_vars.get("module_args")
            or {}
        )
        if isinstance(module_args, str):
            module_args = (
                {"_raw_params": module_args}
                if module in FREE_FORM_MODULES
                else parse_module_args(module_args)
            )
        extra_vars["module_name"] = module
        extra_vars["module_args"] = module_args
    if resolve_workflow_inputs(run).get("execution_source") in {"playbook", "module"}:
        source_playbook = build_source_playbook(run)
        if source_playbook:
            return source_playbook
    playbook = build_playbook(command_spec, extra_vars)
    if getattr(command_spec, "become_enabled", False):
        for play in playbook:
            if isinstance(play, dict):
                play["become"] = True
    return playbook


def _quick_command_adhoc_spec(run, command_spec, extra_vars):
    """Return the ad-hoc module invocation for a quick command.

    Reusable workflow command/script nodes intentionally keep playbook
    execution.  Only the dedicated quick-command workflow bypasses playbook
    construction and uses Ansible Runner's ad-hoc entry point.
    """
    if resolve_workflow_inputs(run).get("execution_source") != "quick_command":
        return None

    command_content = str(extra_vars.get("command_content") or "")
    if command_spec.command_type == CommandVersion.CommandType.LINUX_SHELL:
        return "raw", f"/bin/bash -c {shlex.quote(command_content)}"
    if command_spec.command_type == CommandVersion.CommandType.WINDOWS_POWERSHELL:
        return "win_shell", command_content
    return None


def _effective_ansible_timeout(run, node, command_spec):
    candidates = [run.timeout_seconds, node.timeout_seconds]
    version_timeout = getattr(command_spec, "timeout_seconds", None)
    if version_timeout:
        candidates.append(version_timeout)
    return max(min(int(value) for value in candidates if value), 1)


def _ansible_execution_options(run, node):
    """Resolve per-node host execution settings with system defaults."""
    settings = get_engine_settings()
    config = node.config or {}
    runtime = resolve_workflow_inputs(run)
    strategy = str(
        config.get("hostStrategy")
        or runtime.get("host_strategy")
        or settings["host_strategy"]
    )
    if strategy not in {"parallel", "serial", "rolling"}:
        raise ValueError("主机执行策略必须是 parallel、serial 或 rolling")
    forks = int(
        config.get("forks") or runtime.get("ansible_forks") or settings["forks"]
    )
    serial_batch = int(
        config.get("serialBatch")
        or runtime.get("serial_batch")
        or settings["serial_batch"]
    )
    max_fail_percentage = int(
        config.get("maxFailPercentage")
        if config.get("maxFailPercentage") is not None
        else runtime.get("max_fail_percentage", settings["max_fail_percentage"])
    )
    if forks <= 0 or serial_batch <= 0:
        raise ValueError("Forks 和滚动批次必须大于 0")
    if not 0 <= max_fail_percentage <= 100:
        raise ValueError("最大失败比例必须在 0 到 100 之间")
    return {
        "strategy": strategy,
        "forks": 1 if strategy == "serial" else forks,
        "serial_batch": serial_batch,
        "max_fail_percentage": max_fail_percentage,
    }


def _apply_host_execution_options(playbook, options):
    """Apply host batching rules to every generated or user-authored play."""
    for play in playbook:
        if not isinstance(play, dict):
            continue
        if options["strategy"] == "serial":
            play["serial"] = 1
        elif options["strategy"] == "rolling":
            play["serial"] = options["serial_batch"]
        else:
            play.pop("serial", None)
        if options["max_fail_percentage"]:
            play["max_fail_percentage"] = options["max_fail_percentage"]
        else:
            play.pop("max_fail_percentage", None)
    return playbook


def _validate_version_arguments(command_spec, values):
    schema = getattr(command_spec, "argument_schema", None) or {}
    if not schema:
        return
    properties = (
        schema.get("properties")
        if isinstance(schema.get("properties"), dict)
        else schema
    )
    required = (
        set(schema.get("required") or [])
        if isinstance(schema.get("required"), list)
        else set()
    )
    for name, definition in properties.items():
        if name in {"properties", "required"} or not isinstance(definition, dict):
            continue
        if definition.get("required"):
            required.add(name)
    missing = [name for name in required if values.get(name) in (None, "")]
    if missing:
        raise ValueError(f"缺少资源版本必填参数：{', '.join(sorted(missing))}")

    expected_types = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for name, definition in properties.items():
        if not isinstance(definition, dict) or name not in values:
            continue
        expected = expected_types.get(str(definition.get("type") or ""))
        value = values[name]
        if expected and value is not None and not isinstance(value, expected):
            raise ValueError(f"资源版本参数 {name} 的类型必须为 {definition['type']}")


def _extract_version_outputs(text, command_spec):
    outputs = {}
    for extractor in getattr(command_spec, "output_extractors", None) or []:
        match = re.search(str(extractor.get("pattern") or ""), text or "", re.MULTILINE)
        if not match:
            continue
        group = int(extractor.get("group", 1))
        try:
            value = match.group(group)
        except IndexError:
            continue
        value_type = extractor.get("type", "string")
        try:
            if value_type == "json":
                value = json.loads(value)
            elif value_type == "integer":
                value = int(value)
            elif value_type == "number":
                value = float(value)
            elif value_type == "boolean":
                value = str(value).strip().lower() in {"1", "true", "yes", "on"}
        except (TypeError, ValueError):
            continue
        outputs[str(extractor["name"])] = value
    return outputs
