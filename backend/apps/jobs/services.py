from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import json
import logging
import os
import re
import shlex
import shutil
import tempfile
from types import SimpleNamespace

import yaml

from apps.automation.models import CommandAtom, CommandVersion, WorkflowNode
from apps.automation.workflow_graph import serialize_graph
from apps.cmdb.crypto import decrypt_secret
from apps.cmdb.models import AssetHost
from apps.ops.workflow.ansible_service import (
    AnsibleRunnerService,
    AnsibleRunnerUnavailable,
)
from apps.ops.workflow.adapters import AnsibleRunnerAdapter
from apps.ops.workflow.inventory import build_inventory
from apps.ops.workflow.inventory import inventory_hostname
from apps.ops.workflow.playbooks import build_playbook
from apps.ops.workflow.plans import ExecutionPlan

from .events import persist_runner_event
from .input_secrets import protect_workflow_inputs, resolve_workflow_inputs
from .models import Gateway, HostRunResult, JobEventLog, NodeRun, WorkflowRun
from .quick_commands import is_quick_command_workflow_version
from .settings_service import get_engine_settings
from .state_machine import ExecutionLease


logger = logging.getLogger(__name__)


FREE_FORM_MODULES = frozenset({"shell", "command", "script", "raw"})

# 执行链内部写入 input_vars 的元数据键，不应作为 extra_vars 透传给 Ansible
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
        override_gateway_id or host.get("default_gateway_id")
        for host in snapshots
        if override_gateway_id or host.get("default_gateway_id")
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
        gateway_id = override_gateway_id or host.get("default_gateway_id")
        if not gateway_id:
            prepared_hosts.append(host)
            continue
        if str(host.get("connection_type") or "ssh").lower() != "ssh":
            raise InvalidGateway("Gateway proxy is only supported for SSH hosts")
        variables = dict(host.get("ansible_connection_vars") or {})
        variables.update(proxy_vars[gateway_id])
        host["ansible_connection_vars"] = variables
        prepared_hosts.append(host)
    return prepared_hosts, {}, private_data_dir


def build_gateway_inventory(host_snapshots, input_vars=None):
    prepared_hosts, group_vars, private_data_dir = prepare_host_gateway_execution(
        host_snapshots,
        input_vars,
    )
    try:
        return build_inventory(prepared_hosts, group_vars), private_data_dir
    except Exception:
        if private_data_dir:
            shutil.rmtree(private_data_dir, ignore_errors=True)
        raise


class InvalidTargetHosts(ValueError):
    pass


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


class InvalidQuickCommand(ValueError):
    pass


def get_execution_timeout_seconds():
    """Return the global execution-engine timeout used by new workflow runs."""
    try:
        return max(int(get_engine_settings().get("timeout") or 0), 1)
    except (TypeError, ValueError):
        return 300


def build_host_snapshot(host):
    labels = [
        str(binding.tag)
        for binding in getattr(host, "tag_bindings", []).all()
        if binding.tag
    ]
    return {
        "host_id": host.id,
        "asset_type": host.asset_type,
        "hostname": host.hostname,
        "inventory_hostname": inventory_hostname(
            {"host_id": host.id, "hostname": host.hostname}
        ),
        "ip": host.primary_ip,
        "os_family": host.os_family,
        "connection_type": host.connection_type,
        "connection_port": host.connection_port,
        "ansible_connection_vars": host.ansible_connection_vars,
        "credential_ref_id": host.credential_ref_id,
        "default_gateway_id": host.default_gateway_id,
        "labels": labels,
        "image_name": host.image_name,
        "cpu_cores": host.cpu_cores,
        "memory_mb": host.memory_mb,
        "system_disk_gb": host.system_disk_gb,
        "data_disk_gb": host.data_disk_gb,
        "metadata": host.metadata,
    }


@transaction.atomic
def create_workflow_run(
    workflow_version,
    target_hosts,
    input_vars,
    worker_pool,
    triggered_by,
    trigger_type=WorkflowRun.TriggerType.MANUAL,
    run_domain=WorkflowRun.RunDomain.TASK,
    execution_kind=WorkflowRun.ExecutionKind.WORKFLOW,
    timeout_seconds=None,
    queue_timeout_seconds=None,
):
    target_snapshot = [build_host_snapshot(host) for host in target_hosts]
    safe_input_vars, secret_input_vars_encrypted = protect_workflow_inputs(
        workflow_version,
        input_vars,
    )
    timeout_seconds = max(
        int(timeout_seconds or get_execution_timeout_seconds()),
        1,
    )
    queue_timeout_seconds = max(
        int(
            queue_timeout_seconds
            if queue_timeout_seconds is not None
            else min(timeout_seconds, 300)
        ),
        1,
    )
    now = timezone.now()
    return WorkflowRun.objects.create(
        workflow_version=workflow_version,
        run_domain=run_domain,
        execution_kind=execution_kind,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        input_vars=safe_input_vars,
        secret_input_vars_encrypted=secret_input_vars_encrypted,
        target_snapshot=target_snapshot,
        context_vars={"inputs": safe_input_vars},
        graph_snapshot=workflow_version.graph_snapshot
        or serialize_graph(workflow_version),
        worker_pool=worker_pool,
        celery_task_id="",
        worker_name="",
        runner_workspace="",
        timeout_seconds=timeout_seconds,
        queue_timeout_seconds=queue_timeout_seconds,
        queue_deadline_at=now + timedelta(seconds=queue_timeout_seconds),
    )


@transaction.atomic
def create_workflow_run_from_host_ids(
    workflow_version,
    host_ids,
    input_vars,
    worker_pool,
    triggered_by,
    trigger_type=WorkflowRun.TriggerType.MANUAL,
    run_domain=WorkflowRun.RunDomain.TASK,
    execution_kind=WorkflowRun.ExecutionKind.WORKFLOW,
    timeout_seconds=None,
    queue_timeout_seconds=None,
):
    requested_host_ids = set(host_ids)
    hosts = list(
        AssetHost.objects.filter(
            id__in=requested_host_ids,
            status=AssetHost.HostStatus.ACTIVE,
        )
        .select_for_update()
        .select_related("credential_ref", "default_gateway")
        .prefetch_related(
            "tag_bindings__tag",
        )
    )
    if {host.id for host in hosts} != requested_host_ids:
        raise InvalidTargetHosts("One or more target hosts are missing or inactive")
    return create_workflow_run(
        workflow_version=workflow_version,
        target_hosts=hosts,
        input_vars=input_vars,
        worker_pool=worker_pool,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        run_domain=run_domain,
        execution_kind=execution_kind,
        timeout_seconds=timeout_seconds,
        queue_timeout_seconds=queue_timeout_seconds,
    )


def scheduled_job_run_options(schedule):
    """Build the run-level execution options persisted by a scheduled job."""
    return {
        "input_vars": {
            **(schedule.input_vars or {}),
            "host_strategy": schedule.host_strategy,
            "ansible_forks": schedule.forks,
            "serial_batch": schedule.serial_batch,
            "max_fail_percentage": schedule.max_fail_percentage,
            "bypass_host_gateway": schedule.bypass_host_gateway,
        },
        "timeout_seconds": schedule.timeout_seconds,
        "queue_timeout_seconds": schedule.queue_timeout_seconds,
    }


@transaction.atomic
def create_quick_command_run(
    *,
    command_type,
    command_content,
    host_ids,
    worker_pool,
    triggered_by,
    source_command_version_id=None,
    can_execute_high_risk=False,
    extra_input_vars=None,
):
    from .quick_commands import (
        ensure_quick_command_workflows,
        quick_command_risk_level,
    )

    version = ensure_quick_command_workflows()[command_type]
    source_command_version = None
    if source_command_version_id is not None:
        try:
            source_command_version = (
                CommandVersion.objects.select_for_update()
                .select_related("command")
                .get(
                    id=source_command_version_id,
                    status=CommandVersion.Status.PUBLISHED,
                )
            )
        except CommandVersion.DoesNotExist as exc:
            raise InvalidQuickCommand(
                "Source command version is missing or unpublished"
            ) from exc
        if (
            source_command_version.command_type != command_type
            or source_command_version.content != command_content
        ):
            raise InvalidQuickCommand(
                "Command content does not match its source version"
            )
    risk_level = quick_command_risk_level(source_command_version)
    if risk_level == CommandAtom.RiskLevel.HIGH and not can_execute_high_risk:
        raise InvalidQuickCommand("High-risk command execution permission is required")
    input_vars = {
        "command_content": command_content,
        "execution_source": "quick_command",
        "source_command_version_id": getattr(source_command_version, "id", None),
        "risk_level": risk_level,
    }
    if extra_input_vars:
        input_vars.update(extra_input_vars)
    execution_source = str(input_vars.get("execution_source") or "quick_command")
    execution_kind = {
        "playbook": WorkflowRun.ExecutionKind.PLAYBOOK,
        "module": WorkflowRun.ExecutionKind.MODULE,
    }.get(execution_source, WorkflowRun.ExecutionKind.QUICK_COMMAND)
    return create_workflow_run_from_host_ids(
        workflow_version=version,
        host_ids=host_ids,
        input_vars=input_vars,
        worker_pool=worker_pool,
        triggered_by=triggered_by,
        trigger_type=WorkflowRun.TriggerType.MANUAL,
        run_domain=WorkflowRun.RunDomain.OPS,
        execution_kind=execution_kind,
    )


def should_stop_workflow_run(run):
    return run.status in {
        WorkflowRun.Status.CANCEL_REQUESTED,
        WorkflowRun.Status.CANCELED,
        WorkflowRun.Status.TIMEOUT,
    }


def _claim_workflow_run(run):
    started_at = timezone.now()
    claimed = WorkflowRun.objects.filter(
        id=run.id,
        status__in=[WorkflowRun.Status.PENDING, WorkflowRun.Status.QUEUED],
    ).update(
        status=WorkflowRun.Status.RUNNING,
        started_at=started_at,
        updated_at=started_at,
    )
    if not claimed:
        run.refresh_from_db(fields=["status", "started_at", "finished_at"])
        return None
    run.status = WorkflowRun.Status.RUNNING
    run.started_at = started_at
    return started_at


def _is_workflow_run_canceled(run):
    run.refresh_from_db(fields=["status"])
    return should_stop_workflow_run(run)


def _mark_node_run_canceled(node_run):
    if node_run.status not in {NodeRun.Status.PENDING, NodeRun.Status.RUNNING}:
        return False

    finished_at = timezone.now()
    node_run.status = NodeRun.Status.CANCELED
    node_run.finished_at = finished_at
    node_run.duration_ms = int(
        (finished_at - (node_run.started_at or finished_at)).total_seconds() * 1000
    )
    node_run.failure_reason = "Canceled by user"
    node_run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "failure_reason",
            "updated_at",
        ]
    )
    JobEventLog.objects.create(
        workflow_run=node_run.workflow_run,
        node_run=node_run,
        event_type="node_canceled",
        message="Node execution canceled by user.",
        payload={"node_run_id": node_run.id},
    )
    return True


def _mark_workflow_work_canceled(run):
    finished_at = timezone.now()
    node_runs_by_workflow_node_id = {
        node_run.workflow_node_id: node_run
        for node_run in NodeRun.objects.filter(workflow_run=run)
    }
    workflow_nodes = (
        WorkflowNode.objects.filter(workflow_version=run.workflow_version)
        .select_related("command_version")
        .order_by("order_index", "id")
    )
    terminal_statuses = {
        NodeRun.Status.SUCCESS,
        NodeRun.Status.FAILED,
        NodeRun.Status.SKIPPED,
        NodeRun.Status.CANCELED,
    }

    for workflow_node in workflow_nodes:
        node_run = node_runs_by_workflow_node_id.get(workflow_node.id)
        if node_run is None:
            node_run = NodeRun.objects.create(
                workflow_run=run,
                workflow_node=workflow_node,
                command_version=workflow_node.command_version,
                status=NodeRun.Status.PENDING,
                input_vars=workflow_node.input_mapping,
            )
        if node_run.status in terminal_statuses:
            continue

        HostRunResult.objects.filter(
            node_run=node_run,
            status__in=[HostRunResult.Status.PENDING, HostRunResult.Status.RUNNING],
        ).update(
            status=HostRunResult.Status.CANCELED,
            finished_at=finished_at,
            updated_at=finished_at,
        )
        for target in run.target_snapshot or []:
            host_id = target.get("host_id")
            hostname = str(target.get("hostname") or "")
            if not hostname:
                continue
            host_key = HostRunResult.host_key_for(host_id, hostname)
            HostRunResult.objects.get_or_create(
                node_run=node_run,
                host_key=host_key,
                defaults={
                    "host_id": host_id,
                    "hostname": hostname,
                    "ip": target.get("ip") or "0.0.0.0",
                    "status": HostRunResult.Status.CANCELED,
                    "raw_event_data": {
                        "event": "workflow_canceled",
                        "event_data": {"host": hostname},
                    },
                    "finished_at": finished_at,
                },
            )
        _mark_node_run_canceled(node_run)


def _materialize_failed_target_results(node_run, targets, error, rc):
    finished_at = timezone.now()
    for target in targets:
        host_id = target.get("host_id")
        hostname = str(target.get("hostname") or "")
        if not hostname:
            continue
        host_key = HostRunResult.host_key_for(host_id, hostname)
        HostRunResult.objects.update_or_create(
            node_run=node_run,
            host_key=host_key,
            defaults={
                "host_id": host_id,
                "hostname": hostname,
                "ip": target.get("ip") or "0.0.0.0",
                "status": HostRunResult.Status.FAILED,
                "stderr": error,
                "raw_event_data": {
                    "event": "runner_failure",
                    "event_data": {"host": hostname},
                },
                "rc": rc,
                "finished_at": finished_at,
            },
        )


def _merge_node_vars(run, node):
    extra_vars = {}
    command_version = node.command_version
    if command_version and isinstance(command_version.default_vars, dict):
        extra_vars.update(command_version.default_vars)
    resolved_inputs = resolve_workflow_inputs(run)
    if isinstance(resolved_inputs, dict):
        extra_vars.update(resolved_inputs)
    if isinstance(node.input_mapping, dict):
        from .node_executors import render_value
        from .workflow_engine import runtime_context

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


def execute_ansible_node(node_run_id):
    node_run = NodeRun.objects.select_related(
        "workflow_run",
        "workflow_run__worker_pool",
        "workflow_node",
        "command_version",
    ).get(id=node_run_id)
    run = node_run.workflow_run
    node = node_run.workflow_node
    if not node:
        raise ValueError("Workflow node is required")

    node_started_at = timezone.now()
    node_run.status = NodeRun.Status.RUNNING
    node_run.started_at = node_started_at
    node_run.heartbeat_at = node_started_at
    node_run.failure_reason = ""
    node_run.save(
        update_fields=[
            "status",
            "started_at",
            "heartbeat_at",
            "failure_reason",
            "updated_at",
        ]
    )
    JobEventLog.objects.create(
        workflow_run=run,
        node_run=node_run,
        event_type="node_started",
        message=f"Node {node.node_key} started.",
        payload={"node_key": node.node_key, "runner_mode": "ansible"},
    )

    command_spec = _node_command_spec(node)
    extra_vars = _merge_node_vars(run, node)
    _validate_version_arguments(command_spec, extra_vars)
    if (
        command_spec.command_type
        in {
            CommandVersion.CommandType.LINUX_SHELL,
            CommandVersion.CommandType.WINDOWS_POWERSHELL,
        }
        and resolve_workflow_inputs(run).get("execution_source") == "quick_command"
    ):
        extra_vars["command_content"] = wrap_command_lines_with_markers(
            extra_vars.get("command_content"), command_spec.command_type
        )
    execution_options = _ansible_execution_options(run, node)
    adhoc_spec = _quick_command_adhoc_spec(run, command_spec, extra_vars)
    playbook = []
    if adhoc_spec is None:
        playbook = _apply_host_execution_options(
            _node_playbook(run, node, command_spec, extra_vars),
            execution_options,
        )
    inventory, gateway_private_dir = build_gateway_inventory(
        run.target_snapshot or [],
        resolve_workflow_inputs(run),
    )
    plan = ExecutionPlan(
        run_id=run.id,
        node_run_id=node_run.id,
        command_type=command_spec.command_type,
        target_hosts=run.target_snapshot or [],
        inventory=inventory,
        playbook=playbook,
        extra_vars=extra_vars,
        env_vars={},
        private_data_dir=gateway_private_dir,
        timeout_seconds=_effective_ansible_timeout(run, node, command_spec),
        forks=execution_options["forks"],
        check_mode=bool((node.config or {}).get("checkMode")),
        module=adhoc_spec[0] if adhoc_spec else None,
        module_args=adhoc_spec[1] if adhoc_spec else "",
    )
    callbacks_received = False

    def handle_event(event):
        nonlocal callbacks_received
        callbacks_received = True
        NodeRun.objects.filter(id=node_run.id).update(heartbeat_at=timezone.now())
        ExecutionLease.touch(run.id)
        if _is_workflow_run_canceled(run):
            return False
        persist_runner_event(workflow_run=run, node_run=node_run, event=event)
        return True

    def cancel_callback():
        return _is_workflow_run_canceled(run)

    materialize_failed_results = False
    try:
        runner_result = AnsibleRunnerAdapter(
            plan,
            service=AnsibleRunnerService(),
            cancel_check=cancel_callback,
        ).start(handle_event, lambda *_args: None)
        status = runner_result.status
        rc = int(runner_result.return_code or 0)
        error = runner_result.error or ""
    except AnsibleRunnerUnavailable as exc:
        status, rc, error = "failed", 127, str(exc)
        materialize_failed_results = True
    except Exception as exc:
        logger.exception("Ansible node %s failed", node_run.id)
        status, rc, error = "failed", 1, str(exc) or "Ansible runner execution failed."
        materialize_failed_results = True

    if not callbacks_received:
        status, rc = "failed", rc or 1
        error = error or "Ansible runner completed without callback events."
        materialize_failed_results = True
    if materialize_failed_results:
        _materialize_failed_target_results(
            node_run, run.target_snapshot or [], error, rc
        )

    finished_at = timezone.now()
    success = rc == 0 and status in {"successful", "success", "ok"}
    host_outputs = {
        result.hostname: {
            "status": result.status,
            "rc": result.rc,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
        for result in node_run.host_results.all()
    }
    from .node_executors import extract_output_vars

    extracted_outputs = {}
    for host_output in host_outputs.values():
        stdout = host_output.get("stdout") or ""
        extracted_outputs.update(extract_output_vars(stdout))
        extracted_outputs.update(_extract_version_outputs(stdout, command_spec))
    node_run.status = NodeRun.Status.SUCCESS if success else NodeRun.Status.FAILED
    node_run.exit_code = rc
    node_run.finished_at = finished_at
    node_run.duration_ms = int((finished_at - node_started_at).total_seconds() * 1000)
    node_run.failure_reason = "" if success else error or "Node execution failed"
    node_run.output_vars = {"hosts": host_outputs, **extracted_outputs}
    node_run.save(
        update_fields=[
            "status",
            "exit_code",
            "finished_at",
            "duration_ms",
            "failure_reason",
            "output_vars",
            "updated_at",
        ]
    )
    JobEventLog.objects.create(
        workflow_run=run,
        node_run=node_run,
        event_type="node_succeeded" if success else "node_failed",
        message=f"Node {node.node_key} {'succeeded' if success else 'failed'}.",
        payload={"node_key": node.node_key, "runner_status": status, "runner_rc": rc},
    )
    return node_run


@transaction.atomic
def _mark_workflow_failed(run, started_at, failure_reason):
    finished_at = timezone.now()
    run.status = WorkflowRun.Status.FAILED
    run.failure_reason = failure_reason
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    run.save(
        update_fields=[
            "status",
            "failure_reason",
            "finished_at",
            "duration_ms",
            "updated_at",
        ]
    )
    JobEventLog.objects.create(
        workflow_run=run,
        event_type="workflow_failed",
        message=failure_reason,
        payload={"workflow_run_id": run.id},
    )
    return run


def run_workflow_ansible(workflow_run_id):
    run = WorkflowRun.objects.select_related(
        "workflow_version",
        "worker_pool",
    ).get(id=workflow_run_id)
    started_at = _claim_workflow_run(run)
    if started_at is None:
        if should_stop_workflow_run(run):
            _mark_workflow_work_canceled(run)
        return run
    if not run.workflow_version:
        return _mark_workflow_failed(
            run,
            started_at,
            "Workflow version is required.",
        )
    JobEventLog.objects.create(
        workflow_run=run,
        event_type="workflow_started",
        message="Workflow run started by ansible-runner.",
        payload={"workflow_run_id": run.id, "runner_mode": "ansible"},
    )

    try:
        source_playbook = build_source_playbook(run)
    except InvalidSourcePlaybook as exc:
        return _mark_workflow_failed(run, started_at, str(exc))

    nodes = (
        WorkflowNode.objects.filter(
            workflow_version=run.workflow_version,
        )
        .select_related("command_version", "command_version__command")
        .order_by(
            "order_index",
            "id",
        )
    )
    runner_service = AnsibleRunnerService()
    workflow_failed = False
    failure_reason = ""

    for node in nodes:
        if _is_workflow_run_canceled(run):
            _mark_workflow_work_canceled(run)
            return run
        node_started_at = timezone.now()
        node_run, _ = NodeRun.objects.update_or_create(
            workflow_run=run,
            workflow_node=node,
            defaults={
                "command_version": node.command_version,
                "status": NodeRun.Status.RUNNING,
                "input_vars": node.input_mapping,
                "started_at": node_started_at,
                "failure_reason": "",
            },
        )
        JobEventLog.objects.create(
            workflow_run=run,
            node_run=node_run,
            event_type="node_started",
            message=f"Node {node.node_key} started.",
            payload={"node_key": node.node_key, "runner_mode": "ansible"},
        )

        extra_vars = _merge_node_vars(run, node)
        if source_playbook is not None:
            extra_vars = {
                key: value
                for key, value in extra_vars.items()
                if key not in INTERNAL_INPUT_VAR_KEYS
            }
        elif (
            resolve_workflow_inputs(run).get("execution_source", "quick_command")
            == "quick_command"
        ):
            # 多行快速命令注入分段标记，便于前端区分每条命令的输出
            extra_vars["command_content"] = wrap_command_lines_with_markers(
                extra_vars.get("command_content"),
                node.command_version.command_type,
            )
        playbook = source_playbook or build_playbook(node.command_version, extra_vars)
        try:
            inventory, gateway_private_dir = build_gateway_inventory(
                run.target_snapshot or [],
                resolve_workflow_inputs(run),
            )
        except InvalidGateway as exc:
            return _mark_workflow_failed(run, started_at, str(exc))
        plan = ExecutionPlan(
            run_id=run.id,
            node_run_id=node_run.id,
            command_type=node.command_version.command_type,
            target_hosts=run.target_snapshot or [],
            inventory=inventory,
            playbook=playbook,
            extra_vars=extra_vars,
            env_vars={},
            private_data_dir=gateway_private_dir,
            # The execution-engine setting is the effective timeout for all
            # direct Ansible executions. Node timeout is a legacy workflow
            # field and must not silently override the global setting.
            timeout_seconds=run.timeout_seconds,
        )

        callbacks_received = False

        def handle_event(event):
            nonlocal callbacks_received
            callbacks_received = True
            ExecutionLease.touch(run.id)
            if _is_workflow_run_canceled(run):
                _mark_workflow_work_canceled(run)
                return False
            persist_runner_event(
                workflow_run=run,
                node_run=node_run,
                event=event,
            )
            return True

        def cancel_callback():
            if not _is_workflow_run_canceled(run):
                return False
            _mark_workflow_work_canceled(run)
            return True

        materialize_failed_results = False
        try:
            runner = AnsibleRunnerAdapter(
                plan,
                service=runner_service,
                cancel_check=cancel_callback,
            )
            runner_result = runner.start(handle_event, lambda *_args: None)
            result = {
                "status": runner_result.status,
                "rc": runner_result.return_code,
                "stats": runner_result.stats,
                "error": runner_result.error,
            }
        except AnsibleRunnerUnavailable as exc:
            result = {"status": "failed", "rc": 127, "stats": {}, "error": str(exc)}
            materialize_failed_results = True
        except Exception:
            logger.exception(
                "Ansible runner failed for workflow run %s node run %s.",
                run.id,
                node_run.id,
            )
            result = {
                "status": "failed",
                "rc": 1,
                "stats": {},
                "error": "Ansible runner execution failed.",
            }
            materialize_failed_results = True

        if not callbacks_received:
            result = dict(result) if isinstance(result, dict) else {}
            result["status"] = "failed"
            result["rc"] = int(result.get("rc") or 1)
            result["error"] = (
                result.get("error")
                or "Ansible runner completed without callback events."
            )
            materialize_failed_results = True

        node_finished_at = timezone.now()
        if _is_workflow_run_canceled(run):
            _mark_workflow_work_canceled(run)
            return run
        rc = int(result.get("rc") or 0)
        status = result.get("status")
        error = result.get("error", "")
        if materialize_failed_results:
            _materialize_failed_target_results(
                node_run,
                run.target_snapshot or [],
                error or "Node execution failed",
                rc,
            )
        node_success = rc == 0 and status in {"successful", "success", "ok"}
        node_run.status = (
            NodeRun.Status.SUCCESS if node_success else NodeRun.Status.FAILED
        )
        node_run.exit_code = rc
        node_run.finished_at = node_finished_at
        node_run.duration_ms = int(
            (node_finished_at - node_started_at).total_seconds() * 1000
        )
        node_run.failure_reason = (
            "" if node_success else (error or "Node execution failed")
        )
        node_run.save(
            update_fields=[
                "status",
                "exit_code",
                "finished_at",
                "duration_ms",
                "failure_reason",
                "updated_at",
            ]
        )
        JobEventLog.objects.create(
            workflow_run=run,
            node_run=node_run,
            event_type="node_succeeded" if node_success else "node_failed",
            message=(
                f"Node {node.node_key} succeeded."
                if node_success
                else f"Node {node.node_key} failed."
            ),
            payload={
                "node_key": node.node_key,
                "runner_status": status,
                "runner_rc": rc,
            },
        )

        if not node_success and not node.continue_on_error:
            workflow_failed = True
            failure_reason = node_run.failure_reason
            break

    if workflow_failed:
        _mark_workflow_failed(run, started_at, failure_reason)
        return run

    finished_at = timezone.now()
    if _is_workflow_run_canceled(run):
        _mark_workflow_work_canceled(run)
        return run
    run.status = WorkflowRun.Status.SUCCESS
    run.finished_at = finished_at
    run.duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    run.failure_reason = ""
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "duration_ms",
            "failure_reason",
            "updated_at",
        ]
    )
    JobEventLog.objects.create(
        workflow_run=run,
        event_type="workflow_succeeded",
        message="Workflow run succeeded.",
        payload={"workflow_run_id": run.id, "runner_mode": "ansible"},
    )
    return run
