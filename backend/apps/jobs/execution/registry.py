from uuid import uuid4
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
import logging
from apps.jobs.security import check_execution_payload
import shutil
from apps.automation.models import CommandVersion, WorkflowNode
from apps.cmdb.targets import authorize_frozen_targets
from apps.ops.contracts import AnsibleRunnerUnavailable, ExecutionPlan
from apps.ops.executor import AnsibleExecutor
from apps.ops.workflow.playbooks import build_playbook
from apps.jobs.events import append_run_event
from apps.jobs.input_secrets import resolve_workflow_inputs
from apps.jobs.models import HostRunResult, JobEventLog, NodeRun, WorkflowRun
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.application.authorization import authorize_execution
from apps.jobs.execution.fencing import commit_node_result, owned_node_queryset
from apps.jobs.application.cancel import (
    _is_workflow_run_canceled,
    settle_canceled_work,
    should_stop_workflow_run,
)
from apps.jobs.execution.plan_builder import (
    INTERNAL_INPUT_VAR_KEYS,
    InvalidGateway,
    InvalidSourcePlaybook,
    _ansible_execution_options,
    _apply_host_execution_options,
    _effective_ansible_timeout,
    _extract_version_outputs,
    _merge_node_vars,
    _node_command_spec,
    _node_playbook,
    _quick_command_adhoc_spec,
    _validate_version_arguments,
    build_gateway_inventory,
    build_source_playbook,
    wrap_command_lines_with_markers,
)


logger = logging.getLogger(__name__)


def _build_host_output_vars(host_outputs, command_spec):
    from apps.jobs.node_executors import extract_output_vars

    hosts = {}
    for hostname, host_output in host_outputs.items():
        stdout = host_output.get("stdout") or ""
        extracted = {
            **extract_output_vars(stdout),
            **_extract_version_outputs(stdout, command_spec),
        }
        hosts[hostname] = {**host_output, "outputs": extracted}

    # Scalar references are unambiguous only when the step has one target.
    single_host_outputs = (
        next(iter(hosts.values()))["outputs"] if len(hosts) == 1 else {}
    )
    return {
        "hosts": hosts,
        **{key: value for key, value in single_host_outputs.items() if key != "hosts"},
    }


def _materialize_failed_target_results(node_run, targets, error, rc, attempt_id=None):
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
                "ip": target.get("address") or "0.0.0.0",
                "status": HostRunResult.Status.FAILED,
                "stderr": error,
                "raw_event_data": {
                    "event": "runner_failure",
                    "event_data": {"host": hostname},
                },
                "rc": rc,
                "finished_at": finished_at,
                "attempt_id": attempt_id,
            },
        )


def execute_ansible_node(node_run_id, *, expected_attempt=None, expected_task_id=None):
    node_run = NodeRun.objects.select_related(
        "workflow_run",
        "workflow_run__worker_pool",
        "workflow_node",
        "command_version",
    ).get(id=node_run_id)
    if expected_attempt is not None and (
        node_run.attempt_count != expected_attempt
        or node_run.celery_task_id != expected_task_id
        or node_run.status != NodeRun.Status.RUNNING
    ):
        return node_run
    run = node_run.workflow_run

    from .snapshots import execution_node

    node = execution_node(node_run)
    actor = authorize_execution(
        actor=run.triggered_by,
        graph_snapshot=run.graph_snapshot,
        input_vars=resolve_workflow_inputs(run),
    )
    authorize_frozen_targets(actor=actor, targets=run.target_snapshot or [])
    if not node:
        raise ValueError("Workflow node is required")

    node_started_at = node_run.started_at or timezone.now()
    runner_attempt_id = (
        node_run.attempts.filter(attempt=node_run.attempt_count)
        .values_list("id", flat=True)
        .first()
    )
    with transaction.atomic():
        initial = (
            NodeRun.objects.select_for_update()
            .filter(
                pk=node_run.pk,
                attempt_count=node_run.attempt_count,
                celery_task_id=node_run.celery_task_id,
                status=node_run.status,
            )
            .first()
        )
        if initial is None or initial.status not in {
            NodeRun.Status.PENDING,
            NodeRun.Status.QUEUED,
            NodeRun.Status.RUNNING,
        }:
            node_run.refresh_from_db()
            return node_run
        initial.status = NodeRun.Status.RUNNING
        initial.started_at = node_started_at
        initial.heartbeat_at = node_started_at
        initial.failure_reason = ""
        initial.save(
            update_fields=[
                "status",
                "started_at",
                "heartbeat_at",
                "failure_reason",
                "updated_at",
            ]
        )
        node_run.status = NodeRun.Status.RUNNING
        append_run_event(
            run_id=run.id,
            node_run_id=node_run.id,
            attempt_id=runner_attempt_id,
            event_key=uuid4().hex,
            event={
                "event_type": "node_started",
                "message": f"Node {node.node_key} started.",
                "payload": {"node_key": node.node_key, "runner_mode": "ansible"},
            },
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
    if adhoc_spec is not None:
        playbook = [
            {
                "hosts": "all",
                "gather_facts": False,
                "tasks": [{"name": "Execute command", adhoc_spec[0]: adhoc_spec[1]}],
            }
        ]
    else:
        playbook = _node_playbook(run, node, command_spec, extra_vars)
    if getattr(command_spec, "become_enabled", False):
        for play in playbook:
            play["become"] = True
    playbook = _apply_host_execution_options(playbook, execution_options)
    # All Ansible entries (including retries and scheduled workflows) pass here.
    # Inputs are inspected in memory but are not persisted in the intercept record.
    check_execution_payload(
        {"playbook": playbook, "parameters": extra_vars},
        operator=run.triggered_by,
        target_desc=f"run={run.id}, node={node.node_key}",
    )
    inventory, gateway_private_dir = build_gateway_inventory(
        run.target_snapshot or [],
        resolve_workflow_inputs(run),
    )
    plan = ExecutionPlan(
        run_id=run.id,
        node_run_id=node_run.id,
        attempt_id=max(node_run.attempt_count, 1),
        command_type=command_spec.command_type,
        target_hosts=run.target_snapshot or [],
        inventory=inventory,
        playbook=playbook,
        extra_vars=extra_vars,
        env_vars={},
        private_data_dir=gateway_private_dir,
        timeout_seconds=_effective_ansible_timeout(run, node, command_spec),
        forks=execution_options["forks"],
        check_mode=execution_options["check_mode"],
    )
    callbacks_received = False

    def handle_event(event):
        nonlocal callbacks_received
        if not owned_node_queryset(node_run).update(heartbeat_at=timezone.now()):
            return False
        callbacks_received = True
        ExecutionLease.touch(run.id)
        if _is_workflow_run_canceled(run):
            return False
        append_run_event(
            run_id=(run).id,
            node_run_id=(node_run).id,
            attempt_id=runner_attempt_id,
            event_key=str((event.raw_event).get("uuid") or uuid4().hex),
            event=event.raw_event,
        )
        return True

    def cancel_callback():
        return not owned_node_queryset(node_run).exists() or _is_workflow_run_canceled(
            run
        )

    def stream_console_output(text: str) -> None:
        """执行期间增量落库原生控制台输出（executor 线程每 2s 回调一次），
        让前端运行中即可实时查看原生输出；线程侧使用独立 DB 连接，用后即关。"""
        try:
            owned_node_queryset(node_run).update(console_output=text)
        except Exception:
            logger.exception(
                "Failed to persist streaming console output for node %s", node_run.id
            )
        finally:
            connection.close()

    materialize_failed_results = False
    runner_result = None
    try:
        runner_result = AnsibleExecutor().execute(
            plan, handle_event, cancel_callback, on_console_output=stream_console_output
        )
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

    finally:
        shutil.rmtree(gateway_private_dir, ignore_errors=True)

    if not callbacks_received and status not in {"canceled", "timeout"}:
        status, rc = "failed", rc or 1
        error = error or "Ansible runner completed without callback events."
        materialize_failed_results = True
    finished_at = timezone.now()
    success = rc == 0 and status in {"successful", "success", "ok"}
    with transaction.atomic():
        if not owned_node_queryset(node_run).select_for_update().exists():
            node_run.refresh_from_db()
            return node_run
        if materialize_failed_results:
            _materialize_failed_target_results(
                node_run, run.target_snapshot or [], error, rc, runner_attempt_id
            )
        host_results = (
            node_run.host_results.filter(attempt_id=runner_attempt_id)
            if runner_attempt_id
            else node_run.host_results.all()
        )
        host_outputs = {
            result.hostname: {
                "status": result.status,
                "rc": result.rc,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            for result in host_results
        }
        commit_node_result(
            node_run,
            {
                "status": {
                    "canceled": NodeRun.Status.CANCELED,
                    "timeout": NodeRun.Status.TIMEOUT,
                }.get(
                    status, NodeRun.Status.SUCCESS if success else NodeRun.Status.FAILED
                ),
                "exit_code": rc,
                "finished_at": finished_at,
                "duration_ms": int(
                    (finished_at - node_started_at).total_seconds() * 1000
                ),
                "failure_reason": "" if success else error or "Node execution failed",
                "output_vars": _build_host_output_vars(host_outputs, command_spec),
                "console_output": getattr(runner_result, "console_output", "")
                or node_run.console_output,
            },
        )
        append_run_event(
            run_id=run.id,
            node_run_id=node_run.id,
            attempt_id=runner_attempt_id,
            event_key=uuid4().hex,
            event={
                "event_type": "node_succeeded"
                if success
                else "node_canceled"
                if node_run.status == NodeRun.Status.CANCELED
                else "node_failed",
                "message": f"Node {node.node_key} {('succeeded' if success else 'stopped')}.",
                "payload": {
                    "node_key": node.node_key,
                    "runner_status": status,
                    "runner_rc": rc,
                },
            },
        )
    if node_run.status == NodeRun.Status.CANCELED:
        settle_canceled_work(run)
    return node_run
