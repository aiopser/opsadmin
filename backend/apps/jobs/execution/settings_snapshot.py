"""Resolve execution policy once, before dispatch; workers never read live defaults."""

from copy import deepcopy

from django.db import transaction
from django.utils import timezone
from common.workflow.node_types import CONTROL_NODE_TYPES


FIELDS = {
    "hostStrategy": ("host_strategy", "host_strategy"),
    "forks": ("ansible_forks", "forks"),
    "serialBatch": ("serial_batch", "serial_batch"),
    "maxFailPercentage": ("max_fail_percentage", "max_fail_percentage"),
    "checkMode": ("check_mode", None),
}


def freeze_execution_settings(defaults, inputs, graph, timeout=None):
    values, sources = {}, {}
    for field, (input_key, default_key) in FIELDS.items():
        explicit = inputs.get(input_key)
        values[field] = (
            explicit if explicit is not None else defaults.get(default_key, False)
        )
        sources[field] = "run" if explicit is not None else "global"
    values["timeoutSeconds"] = timeout if timeout is not None else defaults["timeout"]
    sources["timeoutSeconds"] = "run" if timeout is not None else "global"
    _validate(values)
    nodes = {}
    for node in graph.get("nodes", []):
        if node.get("type") in CONTROL_NODE_TYPES:
            continue
        effective, origins = deepcopy(values), dict(sources)
        config = node.get("config") or {}
        host_policy = (
            config.get("hostPolicy", "native")
            if node.get("type") == "playbook"
            or (
                node.get("type") == "command"
                and inputs.get("execution_source") == "playbook"
            )
            else "platform"
        )
        if host_policy not in {"native", "platform"}:
            raise ValueError("Invalid playbook host policy")
        effective["hostPolicy"] = host_policy
        origins["hostPolicy"] = "step" if "hostPolicy" in config else "default"
        for field in FIELDS:
            if config.get(field) is not None and (
                host_policy == "platform" or field == "checkMode"
            ):
                effective[field], origins[field] = config[field], "step"
        limits = [(values["timeoutSeconds"], sources["timeoutSeconds"])]
        resource_timeout = (node.get("commandVersion") or {}).get("timeout_seconds")
        if resource_timeout is None:
            resource_timeout = (
                (node.get("resourceSnapshot") or {}).get("definition") or {}
            ).get("timeout_seconds")
        step_timeout = node.get("timeoutSeconds")
        selected_timeout = (
            step_timeout if step_timeout is not None else resource_timeout
        )
        if selected_timeout is not None:
            if type(selected_timeout) is not int or selected_timeout <= 0:
                raise ValueError("Node timeout must be positive or null")
            limits.append(
                (selected_timeout, "step" if step_timeout is not None else "resource")
            )
        effective["timeoutSeconds"], origins["timeoutSeconds"] = min(
            limits, key=lambda item: int(item[0])
        )
        _validate(effective)
        if (
            effective["checkMode"]
            and node.get("type") in {"command", "script", "playbook", "module"}
            and not (node.get("commandVersion") or {}).get(
                "check_mode_supported", False
            )
        ):
            raise ValueError("Resource version does not support Check Mode")
        if host_policy == "platform" and effective["hostStrategy"] == "serial":
            effective["forks"], origins["forks"] = 1, "serial"
        nodes[node["id"]] = {"values": effective, "sources": origins}
    return {"values": values, "sources": sources, "nodes": nodes}


def _validate(values):
    if values["hostStrategy"] not in {"parallel", "serial", "rolling"}:
        raise ValueError("Invalid host execution strategy")
    for field in ("forks", "serialBatch", "timeoutSeconds"):
        if isinstance(values[field], bool) or int(values[field]) <= 0:
            raise ValueError(f"{field} must be positive")
        values[field] = int(values[field])
    if not 0 <= int(values["maxFailPercentage"]) <= 100:
        raise ValueError("Maximum failure percentage must be between 0 and 100")
    values["maxFailPercentage"] = int(values["maxFailPercentage"])
    if not isinstance(values["checkMode"], bool):
        raise ValueError("Check mode must be a boolean")


def ensure_execution_settings(run, node_key=None):
    """Freeze settings for pre-snapshot runs before their next execution/retry.

    New runs already carry this snapshot. The locked fallback only upgrades
    rows created before the field existed, preserving their stored timeout and
    explicit input/step overrides while recording the defaults used now.
    """
    snapshot = run.execution_settings or {}
    if snapshot and (node_key is None or node_key in snapshot.get("nodes", {})):
        return snapshot

    from apps.jobs.models import WorkflowRun
    from apps.jobs.settings_service import get_engine_settings

    with transaction.atomic():
        locked_run = WorkflowRun.objects.select_for_update().get(pk=run.pk)
        snapshot = locked_run.execution_settings or {}
        if not snapshot or (
            node_key is not None and node_key not in snapshot.get("nodes", {})
        ):
            snapshot = freeze_execution_settings(
                get_engine_settings(),
                locked_run.input_vars or {},
                locked_run.graph_snapshot or {},
                locked_run.timeout_seconds,
            )
            locked_run.execution_settings = snapshot
            locked_run.save(update_fields=["execution_settings", "updated_at"])
        run.execution_settings = snapshot
    return snapshot


def node_execution_settings(run, node_key):
    snapshot = ensure_execution_settings(run, node_key)
    node = snapshot.get("nodes", {}).get(node_key)
    if node is None:
        raise ValueError("运行缺少冻结的执行参数，请重新创建运行")
    return node["values"]


def effective_node_timeout(run, node_key):
    timeout = node_execution_settings(run, node_key)["timeoutSeconds"]
    deadline = getattr(run, "workflow_deadline_at", None)
    if deadline is not None:
        remaining = (deadline - timezone.now()).total_seconds()
        if remaining <= 0:
            from billiard.exceptions import SoftTimeLimitExceeded

            raise SoftTimeLimitExceeded()
        timeout = min(timeout, max(int(remaining), 1))
    return max(min(int(timeout), int(run.timeout_seconds)), 1)
