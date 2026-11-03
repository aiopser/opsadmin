from copy import deepcopy
import hmac
from types import SimpleNamespace

from common.workflow.schema import validate_graph
from apps.automation.models import WorkflowVersion
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from datetime import timedelta
from apps.automation.models import CommandAtom, CommandVersion, WorkflowNode
from apps.cmdb.targets import (
    authorize_frozen_targets,
    normalize_target_selector,
    resolve_targets,
    snapshot_targets,
    target_snapshot_fingerprint,
)
from apps.jobs.worker_pools import region_for_targets, resolve_worker_pool
from apps.jobs.input_secrets import protect_workflow_inputs, resolve_workflow_inputs
from apps.jobs.application.authorization import authorize_execution
from apps.jobs.models import WorkflowRun
from apps.jobs.confirmation import confirmation_fingerprint
from apps.jobs.settings_service import get_engine_settings
from apps.jobs.execution.settings_snapshot import (
    ensure_execution_settings,
    freeze_execution_settings,
)
from common.workflow.node_types import ANSIBLE_NODE_TYPES, NodeType

from .dispatch import enqueue_workflow_run, register_dispatch


class InvalidQuickCommand(ValueError):
    pass


TRIAL_NODE_TIMEOUT_SECONDS = 600


def get_execution_timeout_seconds():
    """Return the global execution-engine timeout used by new workflow runs."""
    try:
        return max(int(get_engine_settings().get("timeout") or 0), 1)
    except (TypeError, ValueError):
        return 300


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
    name="",
    target_selector=None,
    failure_alert=None,
    execution_graph=None,
):
    workflow_version = WorkflowVersion.objects.select_for_update().get(
        pk=workflow_version.pk
    )
    if workflow_version.status != WorkflowVersion.Status.PUBLISHED:
        raise ValueError("Only published workflow versions can run")
    graph = (
        execution_graph
        if execution_graph is not None
        else workflow_version.graph_snapshot
    )
    errors = validate_graph(graph)
    if errors:
        raise ValueError("Published workflow snapshot is invalid: " + "; ".join(errors))
    safe_input_vars, encrypted = protect_workflow_inputs(workflow_version, input_vars)
    authorize_execution(
        actor=triggered_by,
        graph_snapshot=graph,
        input_vars=input_vars,
    )
    return _persist_run(
        workflow_version=workflow_version,
        target_hosts=target_hosts,
        safe_input_vars=safe_input_vars,
        encrypted=encrypted,
        graph_snapshot=graph,
        worker_pool=worker_pool,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        run_domain=run_domain,
        execution_kind=execution_kind,
        timeout_seconds=timeout_seconds,
        queue_timeout_seconds=queue_timeout_seconds,
        name=name,
        target_selector=target_selector,
        failure_alert=failure_alert,
    )


@transaction.atomic
def clone_workflow_run(run, actor):

    authorize_execution(
        actor=actor,
        graph_snapshot=run.graph_snapshot,
        input_vars=resolve_workflow_inputs(run),
    )
    execution_settings = ensure_execution_settings(run)
    return _persist_run(
        workflow_version=run.workflow_version,
        target_hosts=run.target_snapshot,
        safe_input_vars=deepcopy(run.input_vars),
        encrypted=run.secret_input_vars_encrypted,
        graph_snapshot=run.graph_snapshot,
        worker_pool=run.worker_pool,
        triggered_by=actor,
        trigger_type=WorkflowRun.TriggerType.MANUAL,
        run_domain=run.run_domain,
        execution_kind=run.execution_kind,
        execution_settings=deepcopy(execution_settings),
        frozen_target_snapshot=run.target_snapshot,
        target_selector=run.target_selector,
        timeout_seconds=run.timeout_seconds,
        queue_timeout_seconds=run.queue_timeout_seconds,
        failure_alert=deepcopy(run.failure_alert),
    )


def _persist_run(
    *,
    workflow_version,
    target_hosts,
    safe_input_vars,
    encrypted,
    graph_snapshot,
    worker_pool,
    triggered_by,
    trigger_type,
    run_domain,
    execution_kind,
    timeout_seconds,
    queue_timeout_seconds,
    name="",
    execution_settings=None,
    frozen_target_snapshot=None,
    target_selector=None,
    failure_alert=None,
):
    errors = validate_graph(graph_snapshot)
    if errors:
        raise ValueError("Invalid execution graph: " + "; ".join(errors))
    triggered_by = authorize_execution(
        actor=triggered_by, graph_snapshot=graph_snapshot, input_vars=safe_input_vars
    )
    # Host-less runs (resource trials) have no target snapshot.
    if frozen_target_snapshot is not None:
        target_snapshot = authorize_frozen_targets(
            actor=triggered_by, targets=frozen_target_snapshot
        )
    else:
        target_snapshot = (
            snapshot_targets(actor=triggered_by, targets=target_hosts)
            if target_hosts
            else []
        )
    if not target_snapshot and any(
        node.get("type") in ANSIBLE_NODE_TYPES
        for node in graph_snapshot.get("nodes", [])
    ):
        raise ValidationError({"hostIds": "流程包含主机执行步骤，请选择目标主机"})
    worker_pool = resolve_worker_pool(
        actor=triggered_by,
        pool_id=getattr(worker_pool, "pk", None),
        execution_kind=execution_kind,
        target_region=region_for_targets(target_snapshot),
    )
    if execution_settings is None:
        execution_settings = freeze_execution_settings(
            get_engine_settings(), safe_input_vars, graph_snapshot, timeout_seconds
        )
    if not execution_settings:
        raise ValueError("运行缺少冻结的执行参数，请从任务单重新运行")
    timeout_seconds = execution_settings["values"]["timeoutSeconds"]
    queue_timeout_seconds = max(
        int(
            queue_timeout_seconds
            if queue_timeout_seconds is not None
            else min(timeout_seconds, 300)
        ),
        1,
    )
    now = timezone.now()
    if failure_alert is None:
        failure_alert = (
            workflow_version.workflow.failure_alert
            if workflow_version is not None
            else {}
        )
    from apps.automation.failure_alerts import freeze_failure_alert

    failure_alert = freeze_failure_alert(failure_alert)
    run = WorkflowRun.objects.create(
        workflow_version=workflow_version,
        run_domain=run_domain,
        execution_kind=execution_kind,
        name=str(name or "").strip()[:128],
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        input_vars=safe_input_vars,
        secret_input_vars_encrypted=encrypted,
        target_snapshot=target_snapshot,
        target_selector=deepcopy(target_selector)
        if target_selector is not None
        else normalize_target_selector(
            host_ids=[target["host_id"] for target in target_snapshot]
        ),
        context_vars={"inputs": safe_input_vars},
        graph_snapshot=deepcopy(graph_snapshot),
        failure_alert=deepcopy(failure_alert),
        execution_settings=deepcopy(execution_settings),
        worker_pool=worker_pool,
        celery_task_id="",
        worker_name="",
        timeout_seconds=timeout_seconds,
        queue_timeout_seconds=queue_timeout_seconds,
        queue_deadline_at=now + timedelta(seconds=queue_timeout_seconds),
    )
    # Durable dispatch intent, created in the same transaction as the run row.
    register_dispatch(workflow_run_id=run.id)
    return run


@transaction.atomic
def create_workflow_run_from_selector(
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
    name="",
    group_ids=(),
    tag_ids=(),
    expected_target_ids=None,
    expected_target_fingerprint=None,
    expected_confirmation_fingerprint=None,
    confirmation_config=None,
    failure_alert=None,
    execution_graph=None,
):
    selector = normalize_target_selector(
        host_ids=host_ids, group_ids=group_ids, tag_ids=tag_ids
    )
    hosts = (
        resolve_targets(
            actor=triggered_by,
            host_ids=selector["hostIds"],
            group_ids=selector["groupIds"],
            tag_ids=selector["tagIds"],
        )
        if any(selector.values())
        else []
    )
    if expected_target_ids is not None:
        if sorted(set(expected_target_ids)) != [host["host_id"] for host in hosts]:
            raise ValidationError({"expectedTargetIds": "目标主机发生变化，请重新预览后确认"})
    if (
        expected_target_fingerprint is not None
        and expected_target_fingerprint != target_snapshot_fingerprint(hosts)
    ):
        raise ValidationError({"expectedTargetFingerprint": "目标连接信息发生变化，请重新预览后确认"})
    if expected_confirmation_fingerprint is not None:
        current_version = WorkflowVersion.objects.select_for_update().get(
            pk=workflow_version.pk
        )
        current_pool = (
            type(worker_pool).objects.select_for_update().get(pk=worker_pool.pk)
            if worker_pool
            else None
        )
        current_fingerprint = confirmation_fingerprint(
            current_version, current_pool, confirmation_config
        )
        if not hmac.compare_digest(
            expected_confirmation_fingerprint, current_fingerprint
        ):
            raise ValidationError(
                {"expectedConfirmationFingerprint": "执行配置发生变化，请重新预览后确认"}
            )
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
        name=name,
        target_selector=selector,
        failure_alert=failure_alert,
        execution_graph=execution_graph,
    )


def scheduled_job_run_options(schedule):
    """Build the run-level execution options persisted by a scheduled job."""
    return {
        "input_vars": {
            **resolve_workflow_inputs(schedule),
            "host_strategy": schedule.host_strategy,
            "ansible_forks": schedule.forks,
            "serial_batch": schedule.serial_batch,
            "max_fail_percentage": schedule.max_fail_percentage,
            **({"gateway_id": schedule.gateway_id} if schedule.gateway_id else {}),
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
    resource_version=None,
    extra_vars=None,
    can_execute_high_risk=False,
    extra_input_vars=None,
    timeout_seconds=None,
    name="",
    expected_target_ids=None,
    expected_target_fingerprint=None,
    expected_confirmation_fingerprint=None,
    confirmation_config=None,
):
    from apps.jobs.quick_commands import (
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
                    command__status=CommandAtom.Status.PUBLISHED,
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
    if resource_version is not None:
        resource_version = (
            CommandVersion.objects.select_for_update()
            .select_related("command")
            .filter(
                pk=resource_version.pk,
                status=CommandVersion.Status.PUBLISHED,
                command__status=CommandAtom.Status.PUBLISHED,
            )
            .first()
        )
        if resource_version is None:
            raise ValidationError({"resourceVersion": "所选资源版本已不可用，请重新预览"})
    source_command_version = resource_version or source_command_version
    risk_level = quick_command_risk_level(source_command_version)
    input_vars = {
        "command_content": command_content,
        "execution_source": "quick_command",
        "source_command_version_id": getattr(source_command_version, "id", None),
        "risk_level": risk_level,
    }
    if extra_input_vars:
        input_vars.update(extra_input_vars)
    # The source binding is server-owned; extra inputs cannot replace it.
    input_vars["source_command_version_id"] = getattr(
        source_command_version, "id", None
    )
    input_vars["risk_level"] = risk_level
    input_vars["extra_vars"] = deepcopy(extra_vars or {})
    execution_source = str(input_vars.get("execution_source") or "quick_command")
    execution_kind = {
        "playbook": WorkflowRun.ExecutionKind.PLAYBOOK,
        "module": WorkflowRun.ExecutionKind.MODULE,
    }.get(execution_source, WorkflowRun.ExecutionKind.QUICK_COMMAND)
    # 运行名称：用户未填时按执行类型前缀 + 时间戳自动生成，避免历史记录全部显示系统模板名
    # 注意：项目 USE_TZ=False，timezone.now() 即本地时间；localtime() 对 naive 时间会抛 ValueError
    label = {
        WorkflowRun.ExecutionKind.PLAYBOOK: "剧本执行",
        WorkflowRun.ExecutionKind.MODULE: "模块执行",
    }.get(execution_kind, "脚本执行")
    run_name = str(name or "").strip() or timezone.now().strftime(
        f"{label}-%Y%m%d-%H%M%S"
    )
    graph = deepcopy(version.graph_snapshot)
    for node in graph.get("nodes", []):
        if node.get("commandVersion"):
            node["timeoutSeconds"] = None
            if source_command_version is None:
                node["commandVersion"]["timeout_seconds"] = None
            if (
                execution_source in {"playbook", "module"}
                and source_command_version is None
            ):
                node["commandVersion"]["check_mode_supported"] = True
            if execution_source == "playbook":
                node["config"] = {**(node.get("config") or {}), "hostPolicy": "native"}
    if source_command_version is not None:
        for node in graph.get("nodes", []):
            command = node.get("commandVersion")
            if not command:
                continue
            for field in (
                "module_name",
                "parameter_docs",
                "default_vars",
                "output_extractors",
                "become_enabled",
                "check_mode_supported",
            ):
                command[field] = deepcopy(getattr(source_command_version, field))
            if (
                source_command_version.command_type
                != CommandVersion.CommandType.ANSIBLE_MODULE
            ):
                command["argument_schema"] = deepcopy(
                    source_command_version.argument_schema
                )
            command["sourceVersionId"] = source_command_version.id
            command["timeout_seconds"] = source_command_version.timeout_seconds
    run = create_workflow_run_from_selector(
        workflow_version=version,
        execution_graph=graph,
        host_ids=host_ids,
        input_vars=input_vars,
        worker_pool=worker_pool,
        triggered_by=triggered_by,
        trigger_type=WorkflowRun.TriggerType.MANUAL,
        run_domain=WorkflowRun.RunDomain.OPS,
        execution_kind=execution_kind,
        timeout_seconds=timeout_seconds,
        name=run_name,
        expected_target_ids=expected_target_ids,
        expected_target_fingerprint=expected_target_fingerprint,
        expected_confirmation_fingerprint=expected_confirmation_fingerprint,
        confirmation_config=confirmation_config,
    )
    return run


@transaction.atomic
def create_trial_run(
    *,
    node_type,
    resource_id,
    node_name,
    config=None,
    input_vars=None,
    triggered_by,
    timeout_seconds=None,
    run_domain=WorkflowRun.RunDomain.TASK,
):
    """Run a resource trial (Jenkins trigger / notification test) under unified run governance.

    Builds a synthetic single-node graph so state, cancel, timeout and audit
    follow the same WorkflowRun lifecycle as normal workflow executions.
    """
    from apps.automation.resource_snapshots import resource_snapshot

    snapshot = resource_snapshot(
        SimpleNamespace(node_type=node_type, resource_id=resource_id)
    )
    if not snapshot:
        raise ValueError("Resource does not support trial execution")
    node_timeout = max(int(timeout_seconds or TRIAL_NODE_TIMEOUT_SECONDS), 1)
    graph = {
        "inputSchema": {},
        "nodes": [
            {"id": "start", "name": "开始", "type": NodeType.START},
            {
                "id": "trial",
                "name": node_name,
                "type": node_type,
                "resourceType": node_type,
                "resourceId": str(resource_id),
                "resourceSnapshot": snapshot,
                "commandVersionId": None,
                "commandVersion": None,
                "config": dict(config or {}),
                "inputMapping": {},
                "inputSchema": [],
                "outputSchema": [],
                "retryPolicy": {},
                "failurePolicy": WorkflowNode.FailurePolicy.STOP,
                "continueOnError": False,
                "timeoutSeconds": node_timeout,
                "position": {},
            },
            {"id": "end", "name": "结束", "type": NodeType.END},
        ],
        "edges": [
            {"id": "start-trial", "source": "start", "target": "trial"},
            {"id": "trial-end", "source": "trial", "target": "end"},
        ],
    }
    errors = validate_graph(graph)
    if errors:
        raise ValueError("Invalid trial graph: " + "; ".join(errors))
    run = _persist_run(
        workflow_version=None,
        target_hosts=[],
        safe_input_vars=dict(input_vars or {}),
        encrypted="",
        graph_snapshot=graph,
        worker_pool=None,
        triggered_by=triggered_by,
        trigger_type=WorkflowRun.TriggerType.MANUAL,
        run_domain=run_domain,
        execution_kind=WorkflowRun.ExecutionKind.WORKFLOW,
        timeout_seconds=node_timeout,
        queue_timeout_seconds=None,
    )
    transaction.on_commit(lambda run_id=run.id: enqueue_workflow_run(run_id))
    return run
