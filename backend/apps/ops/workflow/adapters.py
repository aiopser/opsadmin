from dataclasses import dataclass
import inspect

from .ansible_service import AnsibleRunnerService


@dataclass(frozen=True)
class RunnerResult:
    status: str
    return_code: int | None
    stats: dict
    error: str | None = None

    @classmethod
    def from_mapping(cls, value):
        value = value or {}
        return cls(
            status=str(value.get("status") or "failed"),
            return_code=value.get("rc"),
            stats=value.get("stats") or {},
            error=value.get("error"),
        )


class RunnerAdapter:
    def prepare(self):
        return None

    def start(self, on_event, on_status):
        raise NotImplementedError

    def request_cancel(self):
        raise NotImplementedError

    def cleanup(self):
        return None


class AnsibleRunnerAdapter(RunnerAdapter):
    def __init__(self, plan, *, service=None, cancel_check=None):
        self.plan = plan
        self.service = service or AnsibleRunnerService()
        self.cancel_check = cancel_check
        self._cancel_requested = False

    def start(self, on_event, on_status):
        self.prepare()
        kwargs = {
            "event_handler": on_event,
            "cancel_callback": self._cancel_callback,
            "status_handler": lambda status: on_event(
                {"event": "runner_status", "event_data": status or {}}
            ),
        }
        parameters = inspect.signature(self.service.run).parameters
        if not any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        ):
            kwargs = {key: value for key, value in kwargs.items() if key in parameters}
        raw_result = self.service.run(self.plan, **kwargs)
        result = RunnerResult.from_mapping(raw_result)
        on_status(result.status, result.return_code)
        return result

    def request_cancel(self):
        self._cancel_requested = True

    def _cancel_callback(self):
        return self._cancel_requested or bool(self.cancel_check and self.cancel_check())
