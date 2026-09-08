from uuid import uuid4
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
import logging
import shutil
from apps.automation.models import CommandVersion, WorkflowNode
from apps.cmdb.targets import snapshot_targets
from apps.ops.contracts import AnsibleRunnerUnavailable, ExecutionPlan
from apps.ops.executor import AnsibleExecutor
from apps.ops.workflow.playbooks import build_playbook
from apps.jobs.events import append_run_event
from apps.jobs.input_secrets import resolve_workflow_inputs
from apps.jobs.models import HostRunResult, JobEventLog, NodeRun, WorkflowRun
from apps.jobs.state_machine import ExecutionLease
from apps.jobs.application.cancel import (
    _is_workflow_run_canceled,
    _mark_workflow_work_canceled,
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
                "ip": target.get("address") or "0.0.0.0",
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


def execute_ansible_node(node_run_id):
    node_run = NodeRun.objects.select_related(
        "workflow_run",
        "workflow_run__worker_pool",
        "workflow_node",
        "command_version",
    ).get(id=node_run_id)
    run = node_run.workflow_run
    from .snapshots import execution_node

    node = execution_node(node_run)
    snapshot_targets(actor=run.triggered_by, targets=run.target_snapshot or [])
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
    append_run_event(
        run_id=(run).id,
        node_run_id=(node_run).id,
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
        check_mode=bool((node.config or {}).get("checkMode")),
        module=adhoc_spec[0] if adhoc_spec else None,
        module_args=adhoc_spec[1] if adhoc_spec else "",
    )
    callbacks_received = False
    runner_attempt_id = (
        node_run.attempts.filter(attempt=node_run.attempt_count)
        .values_list("id", flat=True)
        .first()
    )

    def handle_event(event):
        nonlocal callbacks_received
        callbacks_received = True
        NodeRun.objects.filter(id=node_run.id).update(heartbeat_at=timezone.now())
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
        return _is_workflow_run_canceled(run)

    materialize_failed_results = False
    try:
        runner_result = AnsibleExecutor().execute(plan, handle_event, cancel_callback)
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
    from apps.jobs.node_executors import extract_output_vars

    extracted_outputs = {}
    for host_output in host_outputs.values():
        stdout = host_output.get("stdout") or ""
        extracted_outputs.update(extract_output_vars(stdout))
        extracted_outputs.update(_extract_version_outputs(stdout, command_spec))
    node_run.status = {
        "canceled": NodeRun.Status.CANCELED,
        "timeout": NodeRun.Status.TIMEOUT,
    }.get(status, NodeRun.Status.SUCCESS if success else NodeRun.Status.FAILED)
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
    append_run_event(
        run_id=(run).id,
        node_run_id=(node_run).id,
        event_key=uuid4().hex,
        event={
            "event_type": "node_succeeded" if success else "node_failed",
            "message": f"Node {node.node_key} {('succeeded' if success else 'failed')}.",
            "payload": {
                "node_key": node.node_key,
                "runner_status": status,
                "runner_rc": rc,
            },
        },
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
    append_run_event(
        run_id=(run).id,
        node_run_id=None,
        event_key=uuid4().hex,
        event={
            "event_type": "workflow_failed",
            "message": failure_reason,
            "payload": {"workflow_run_id": run.id},
        },
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
    append_run_event(
        run_id=(run).id,
        node_run_id=None,
        event_key=uuid4().hex,
        event={
            "event_type": "workflow_started",
            "message": "Workflow run started by ansible-runner.",
            "payload": {"workflow_run_id": run.id, "runner_mode": "ansible"},
        },
    )

    try:
        snapshot_targets(actor=run.triggered_by, targets=run.target_snapshot or [])
        source_playbook = build_source_playbook(run)
    except (InvalidSourcePlaybook, PermissionDenied, ValidationError) as exc:
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
    executor = AnsibleExecutor()
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
        append_run_event(
            run_id=(run).id,
            node_run_id=(node_run).id,
            event_key=uuid4().hex,
            event={
                "event_type": "node_started",
                "message": f"Node {node.node_key} started.",
                "payload": {"node_key": node.node_key, "runner_mode": "ansible"},
            },
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
            attempt_id=max(node_run.attempt_count, 1),
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
        runner_attempt_id = (
            node_run.attempts.filter(attempt=node_run.attempt_count)
            .values_list("id", flat=True)
            .first()
        )

        def handle_event(event):
            nonlocal callbacks_received
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
            if not _is_workflow_run_canceled(run):
                return False
            return True

        materialize_failed_results = False
        try:
            runner_result = executor.execute(plan, handle_event, cancel_callback)
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

        finally:
            shutil.rmtree(gateway_private_dir, ignore_errors=True)

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
        append_run_event(
            run_id=(run).id,
            node_run_id=(node_run).id,
            event_key=uuid4().hex,
            event={
                "event_type": "node_succeeded" if node_success else "node_failed",
                "message": f"Node {node.node_key} succeeded."
                if node_success
                else f"Node {node.node_key} failed.",
                "payload": {
                    "node_key": node.node_key,
                    "runner_status": status,
                    "runner_rc": rc,
                },
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
    append_run_event(
        run_id=(run).id,
        node_run_id=None,
        event_key=uuid4().hex,
        event={
            "event_type": "workflow_succeeded",
            "message": "Workflow run succeeded.",
            "payload": {"workflow_run_id": run.id, "runner_mode": "ansible"},
        },
    )
    return run
