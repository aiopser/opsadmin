from copy import deepcopy
from types import SimpleNamespace

from common.workflow.schema import validate_graph
from apps.automation.models import WorkflowVersion
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.automation.models import CommandAtom, CommandVersion, WorkflowNode
from apps.cmdb.targets import snapshot_targets
from apps.jobs.worker_pools import region_for_targets, resolve_worker_pool
from apps.jobs.input_secrets import protect_workflow_inputs
from apps.jobs.models import WorkflowRun
from apps.jobs.settings_service import get_engine_settings
from common.workflow.node_types import NodeType

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
):
    workflow_version = WorkflowVersion.objects.select_for_update().get(
        pk=workflow_version.pk
    )
    if workflow_version.status != WorkflowVersion.Status.PUBLISHED:
        raise ValueError("Only published workflow versions can run")
    errors = validate_graph(workflow_version.graph_snapshot)
    if errors:
        raise ValueError("Published workflow snapshot is invalid: " + "; ".join(errors))
    safe_input_vars, encrypted = protect_workflow_inputs(workflow_version, input_vars)
    return _persist_run(
        workflow_version=workflow_version,
        target_hosts=target_hosts,
        safe_input_vars=safe_input_vars,
        encrypted=encrypted,
        graph_snapshot=workflow_version.graph_snapshot,
        worker_pool=worker_pool,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        run_domain=run_domain,
        execution_kind=execution_kind,
        timeout_seconds=timeout_seconds,
        queue_timeout_seconds=queue_timeout_seconds,
    )


@transaction.atomic
def clone_workflow_run(run, actor):
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
        timeout_seconds=run.timeout_seconds,
        queue_timeout_seconds=run.queue_timeout_seconds,
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
):
    errors = validate_graph(graph_snapshot)
    if errors:
        raise ValueError("Invalid execution graph: " + "; ".join(errors))
    # Host-less runs (resource trials) have no target snapshot.
    target_snapshot = (
        snapshot_targets(actor=triggered_by, targets=target_hosts)
        if target_hosts
        else []
    )
    worker_pool = resolve_worker_pool(
        actor=triggered_by,
        pool_id=getattr(worker_pool, "pk", None),
        execution_kind=execution_kind,
        target_region=region_for_targets(target_snapshot),
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
    run = WorkflowRun.objects.create(
        workflow_version=workflow_version,
        run_domain=run_domain,
        execution_kind=execution_kind,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        input_vars=safe_input_vars,
        secret_input_vars_encrypted=encrypted,
        target_snapshot=target_snapshot,
        context_vars={"inputs": safe_input_vars},
        graph_snapshot=deepcopy(graph_snapshot),
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
    hosts = [{"host_id": host_id} for host_id in host_ids]
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
    timeout_seconds=None,
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
        timeout_seconds=timeout_seconds,
    )


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
        "globalVars": {},
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
