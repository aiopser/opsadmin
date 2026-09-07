from dataclasses import dataclass


@dataclass
class ExecutionPlan:
    run_id: int
    node_run_id: int
    command_type: str
    target_hosts: list[dict]
    inventory: str
    playbook: list[dict]
    extra_vars: dict
    env_vars: dict
    private_data_dir: str
    timeout_seconds: int
    forks: int = 10
    check_mode: bool = False
    module: str | None = None
    module_args: str = ""
