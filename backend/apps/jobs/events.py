import ipaddress
import json
import logging
import re

from common.redaction import REDACTED_VALUE, SENSITIVE_KEY_PATTERN, redact_text

from django.db import transaction
from django.utils import timezone

from apps.ops.workflow.events import normalize_runner_event
from apps.ops.workflow.inventory import inventory_hostname

from .models import HostRunResult, JobEventLog


logger = logging.getLogger(__name__)

SAFE_EVENT_METADATA_FIELDS = ("task", "task_action", "play", "playbook", "uuid")
SAFE_RESULT_TEXT_FIELDS = ("stdout", "stderr", "msg")
SAFE_RESULT_VALUE_FIELDS = ("changed", "rc", "skipped", "unreachable")
UNSAFE_NATIVE_KEYS = {"extra_vars", "invocation", "module_args", "_raw_params"}
HOST_EVENT_STATUSES = {
    "runner_on_start": HostRunResult.Status.RUNNING,
    "runner_on_ok": HostRunResult.Status.OK,
    "runner_on_failed": HostRunResult.Status.FAILED,
    "runner_on_unreachable": HostRunResult.Status.UNREACHABLE,
    "runner_on_skipped": HostRunResult.Status.SKIPPED,
    "runner_on_canceled": HostRunResult.Status.CANCELED,
    "runner_on_cancelled": HostRunResult.Status.CANCELED,
}
TERMINAL_HOST_STATUSES = {
    HostRunResult.Status.OK,
    HostRunResult.Status.CHANGED,
    HostRunResult.Status.FAILED,
    HostRunResult.Status.UNREACHABLE,
    HostRunResult.Status.SKIPPED,
    HostRunResult.Status.CANCELED,
}


def _safe_metadata(event_data, hostname, host_id, ip):
    metadata = {"host": hostname}
    if host_id is not None:
        metadata["host_id"] = host_id
    if ip:
        metadata["ip"] = ip
    for field in SAFE_EVENT_METADATA_FIELDS:
        value = event_data.get(field)
        if isinstance(value, (str, int, float, bool)):
            metadata[field] = redact_text(value) if isinstance(value, str) else value
    return metadata


def _safe_result(result):
    safe_result = {}
    for field in SAFE_RESULT_TEXT_FIELDS:
        if field in result:
            safe_result[field] = redact_text(result[field])
    for field in SAFE_RESULT_VALUE_FIELDS:
        if field in result and isinstance(result[field], (bool, int)):
            safe_result[field] = result[field]
    return safe_result


def _redact_native_value(value, key=""):
    """Preserve Runner's event shape while removing credentials recursively."""
    if key and re.search(SENSITIVE_KEY_PATTERN, str(key), re.IGNORECASE):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {
            str(item_key): _redact_native_value(item_value, str(item_key))
            for item_key, item_value in value.items()
            if str(item_key) not in UNSAFE_NATIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_redact_native_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(value)


def _event_host_id(event_data):
    host_id = event_data.get("host_id")
    if host_id is None:
        return None
    try:
        return int(host_id)
    except (TypeError, ValueError):
        return None


def _event_hostname(event_data):
    hostname = event_data.get("host") or event_data.get("remote_addr")
    return str(hostname) if hostname else ""


def _event_ip(event_data):
    for value in (event_data.get("ip"), event_data.get("remote_addr")):
        if not value:
            continue
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            continue
    return ""


def sanitize_runner_event(event):
    event = event or {}
    event_data = event.get("event_data") or {}
    if not isinstance(event_data, dict):
        event_data = {}
    result = event_data.get("res") or {}
    if not isinstance(result, dict):
        result = {}

    event_type = str(event.get("event") or "runner_event")
    no_log = bool(event_data.get("no_log") or result.get("_ansible_no_log"))
    hostname = _event_hostname(event_data)
    host_id = _event_host_id(event_data)
    ip = _event_ip(event_data)
    if no_log:
        metadata = {"host": hostname, "redacted": True}
        payload = {"event": event_type, "event_data": metadata}
        message = f"{event_type} output redacted because no_log is enabled."
        safe_result = {}
    else:
        metadata = _safe_metadata(event_data, hostname, host_id, ip)
        safe_result = _safe_result(result)
        if safe_result:
            metadata["res"] = safe_result
        payload = {
            "event": event_type,
            "event_data": metadata,
            "runner_event": _redact_native_value(event),
        }
        message = str(
            safe_result.get("msg")
            or safe_result.get("stderr")
            or safe_result.get("stdout")
            or event_data.get("stderr")
            or event_data.get("stdout")
            or event_data.get("msg")
            or event_type
        )

    return {
        "event": event_type,
        "event_data": payload.get("event_data") or {},
        "host_id": host_id,
        "hostname": hostname,
        "ip": ip,
        "message": message,
        "no_log": no_log,
        "payload": payload,
        "result": safe_result,
    }


def _target_snapshot_for_event(workflow_run, event):
    for target in workflow_run.target_snapshot or []:
        if event["host_id"] is not None and target.get("host_id") == event["host_id"]:
            return target
        if event["hostname"] and event["hostname"] in {
            target.get("hostname"),
            target.get("inventory_hostname") or inventory_hostname(target),
        }:
            return target
    return {}


def _resolve_event_host(workflow_run, event):
    target = _target_snapshot_for_event(workflow_run, event)
    host_id = event["host_id"]
    if host_id is None:
        host_id = target.get("host_id")
    hostname = target.get("hostname") or event["hostname"]
    ip = event["ip"] or target.get("ip", "")
    return host_id, hostname, ip


def _host_result_defaults(event, host_id, hostname, host_key, ip, status):
    result = event["result"]
    defaults = {
        "host_id": host_id,
        "hostname": hostname,
        "host_key": host_key,
        "ip": ip or "0.0.0.0",
        "status": status,
        "raw_event_data": event["payload"],
        "changed": status == HostRunResult.Status.CHANGED,
    }
    if "stdout" in result:
        defaults["stdout"] = str(result["stdout"] or "")
    if "stderr" in result:
        defaults["stderr"] = str(result["stderr"] or "")
    elif status in {HostRunResult.Status.FAILED, HostRunResult.Status.UNREACHABLE}:
        defaults["stderr"] = str(result.get("msg") or "")
    if result.get("rc") is not None:
        defaults["rc"] = result["rc"]
    if status == HostRunResult.Status.RUNNING:
        defaults["started_at"] = timezone.now()
    if status in TERMINAL_HOST_STATUSES:
        defaults["finished_at"] = timezone.now()
    return defaults


def update_host_result_from_event(*, node_run, event):
    status = HOST_EVENT_STATUSES.get(event["event"])
    if not status:
        return None
    if status == HostRunResult.Status.OK and event["result"].get("changed"):
        status = HostRunResult.Status.CHANGED

    host_id, hostname, ip = _resolve_event_host(node_run.workflow_run, event)
    if not hostname:
        return None
    host_key = HostRunResult.host_key_for(host_id, hostname)
    lookup = {"node_run": node_run, "host_key": host_key}
    defaults = _host_result_defaults(
        event,
        host_id,
        hostname,
        host_key,
        ip,
        status,
    )
    host_result, created = HostRunResult.objects.select_for_update().get_or_create(
        defaults=defaults,
        **lookup,
    )
    if created or (
        host_result.status in TERMINAL_HOST_STATUSES
        and status not in TERMINAL_HOST_STATUSES
    ):
        return host_result

    for field, value in defaults.items():
        setattr(host_result, field, value)
    host_result.save()
    return host_result


@transaction.atomic
def persist_runner_event(*, workflow_run, node_run, event):
    if node_run.workflow_run_id != workflow_run.id:
        raise ValueError("node_run does not belong to workflow_run")
    safe_event = sanitize_runner_event(event)
    host_id, _, _ = _resolve_event_host(workflow_run, safe_event)
    safe_event["host_id"] = host_id
    log = JobEventLog.objects.create(
        workflow_run=workflow_run,
        node_run=node_run,
        host_id=safe_event["host_id"],
        event_type=safe_event["event"],
        message=safe_event["message"],
        payload=safe_event["payload"],
    )
    from .event_types import JobEvent
    from .projections import JobEventProjector

    JobEventProjector(workflow_run=workflow_run, node_run=node_run,).apply(
        JobEvent.from_sanitized(
            run_id=workflow_run.id,
            sequence=log.id,
            event=safe_event,
        )
    )
    return log
