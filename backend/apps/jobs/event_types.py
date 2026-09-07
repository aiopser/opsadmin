from dataclasses import dataclass, field

from apps.ops.workflow.events import normalize_runner_event


@dataclass(frozen=True)
class JobEvent:
    run_id: int
    event_type: str
    sequence: int
    node_id: int | None = None
    host_id: int | None = None
    message: str = ""
    payload: dict = field(default_factory=dict)
    source_event_type: str = ""
    hostname: str = ""
    ip: str = ""
    result: dict = field(default_factory=dict)

    @classmethod
    def from_sanitized(cls, *, run_id, sequence, event):
        normalized = normalize_runner_event(
            {"event": event.get("event"), "event_data": event.get("event_data")}
        )
        return cls(
            run_id=run_id,
            event_type=normalized.event_type if normalized else event["event"],
            sequence=sequence,
            host_id=event.get("host_id"),
            message=event.get("message", ""),
            payload=event.get("payload") or {},
            source_event_type=event.get("event", ""),
            hostname=event.get("hostname", ""),
            ip=event.get("ip", ""),
            result=event.get("result") or {},
        )

    def as_runner_event(self):
        return {
            "event": self.source_event_type or self.event_type,
            "host_id": self.host_id,
            "hostname": self.hostname,
            "ip": self.ip,
            "message": self.message,
            "payload": self.payload,
            "result": self.result,
        }
