from dataclasses import dataclass


EVENT_TYPE_MAP = {
    "runner_on_start": "runner_start",
    "playbook_on_start": "playbook_start",
    "playbook_on_task_start": "task_start",
    "runner_on_ok": "host_ok",
    "runner_on_changed": "host_changed",
    "runner_on_failed": "host_failed",
    "runner_on_unreachable": "host_unreachable",
    "runner_on_skipped": "task_skipped",
    "runner_on_canceled": "execution_canceled",
    "runner_on_cancelled": "execution_canceled",
    "runner_on_error": "execution_error",
    "runner_on_finish": "runner_finish",
}


@dataclass(frozen=True)
class NormalizedRunnerEvent:
    event_type: str
    host: str | None
    result: dict
    event_data: dict
    raw_event: dict


def normalize_runner_event(raw_event):
    if not isinstance(raw_event, dict):
        return None
    event_name = raw_event.get("event")
    event_type = EVENT_TYPE_MAP.get(event_name)
    if not event_type:
        return None
    event_data = raw_event.get("event_data") or {}
    result = event_data.get("res") or event_data.get("result") or {}
    if not isinstance(result, dict):
        result = {"value": result}
    return NormalizedRunnerEvent(
        event_type=event_type,
        host=event_data.get("host"),
        result=result,
        event_data=event_data,
        raw_event=raw_event,
    )
