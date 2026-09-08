from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionPlan:
    run_id: int
    node_run_id: int
    command_type: str
    target_hosts: list[dict]
    inventory: str = field(repr=False)
    playbook: list[dict]
    extra_vars: dict = field(repr=False)
    env_vars: dict = field(repr=False)
    private_data_dir: str
    timeout_seconds: int
    attempt_id: int = 1
    container_image: str | None = None
    forks: int = 10
    check_mode: bool = False
    module: str | None = None
    module_args: str = field(default="", repr=False)


@dataclass(frozen=True)
class RunnerResult:
    status: str
    return_code: int | None
    stats: dict = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def from_mapping(cls, value):
        return cls(status=str(value.get("status") or "failed"), return_code=value.get("rc"), stats=value.get("stats") or {}, error=value.get("error"))


@dataclass(frozen=True)
class RunnerEvent:
    event_type: str
    host: str | None
    result: dict
    event_data: dict
    raw_event: dict


class AnsibleRunnerUnavailable(RuntimeError):
    pass
