"""Synchronous Runner lifecycle with no jobs ORM or workflow state decisions."""

from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import yaml

from common.redaction import redact_text
from .contracts import AnsibleRunnerUnavailable, ExecutionPlan, RunnerResult
from .workflow.events import normalize_runner_event


class AnsibleExecutor:
    def __init__(self, runner=None):
        self.runner = runner

    def execute(self, plan: ExecutionPlan, on_event, should_cancel) -> RunnerResult:
        if plan.timeout_seconds <= 0 or plan.forks <= 0:
            raise ValueError("Execution timeout and concurrency must be positive")
        if should_cancel():
            return RunnerResult("canceled", 1)
        runner = self.runner
        if runner is None:
            try:
                from ansible_runner import run
            except ImportError as exc:
                raise AnsibleRunnerUnavailable("Ansible Runner is unavailable") from exc
            runner = run
        deadline = monotonic() + plan.timeout_seconds
        received_result = False
        host_failed = False
        timed_out = False
        canceled = False

        def cancel():
            nonlocal timed_out, canceled
            timed_out = monotonic() >= deadline
            canceled = canceled or bool(should_cancel())
            return timed_out or canceled

        def emit(raw):
            nonlocal received_result, host_failed
            event = normalize_runner_event(raw)
            if event is None:
                return False
            received_result = received_result or event.event_type in {"host_ok", "host_changed", "host_failed", "host_unreachable", "task_skipped"}
            host_failed = host_failed or event.event_type in {"host_failed", "host_unreachable"}
            on_event(event)
            # Structured persistence/archives own output, not Runner artifact JSON.
            return False

        # Always own the directory we clean. Supplied gateway dirs are caller-owned.
        with TemporaryDirectory(prefix=f"devops-run-{plan.run_id}-{plan.node_run_id}-{plan.attempt_id}-") as directory:
            root = Path(directory)
            inventory = root / "inventory"
            inventory.write_text(plan.inventory, encoding="utf-8")
            inventory.chmod(0o600)
            project = root / "project"
            project.mkdir()
            options = {
                "private_data_dir": directory,
                "inventory": str(inventory),
                "project_dir": str(project),
                "extravars": dict(plan.extra_vars),
                "envvars": dict(plan.env_vars),
                "settings": {"job_timeout": plan.timeout_seconds},
                "cmdline": f"--forks {plan.forks}" + (" --check" if plan.check_mode else ""),
                "event_handler": emit,
                "cancel_callback": cancel,
                "quiet": True,
                "suppress_ansible_output": True,
                "suppress_output_file": True,
            }
            if plan.module:
                options.update(module=plan.module, module_args=plan.module_args, host_pattern="all")
            else:
                playbook = project / "playbook.yml"
                playbook.write_text(yaml.safe_dump(plan.playbook, allow_unicode=True, sort_keys=False), encoding="utf-8")
                playbook.chmod(0o600)
                options["playbook"] = "playbook.yml"
            if plan.container_image:
                options.update(process_isolation=True, process_isolation_executable="docker", container_image=plan.container_image)
            try:
                result = runner(**options)
            except Exception as exc:
                return RunnerResult("failed", 1, error=redact_text(str(exc)))
            cancel()
            status = getattr(result, "status", "failed")
            rc = getattr(result, "rc", None)
            if timed_out or status == "timeout":
                return RunnerResult("timeout", rc or 1, error="Execution timed out")
            if canceled or status in {"canceled", "cancelled"}:
                return RunnerResult("canceled", rc or 1)
            if not received_result:
                return RunnerResult("failed", rc or 1, error="Runner completed without host callback events")
            success = status == "successful" and rc == 0 and not host_failed
            return RunnerResult("success" if success else "failed", rc, getattr(result, "stats", {}) or {})
