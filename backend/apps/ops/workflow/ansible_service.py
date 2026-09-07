import tempfile
import shutil
import sys
from pathlib import Path

import yaml

from apps.ops.ansible.callback import DefaultCallback
from apps.ops.adapters import AnsibleExecutionInput
from apps.ops.services import JumpServerAnsibleService


class AnsibleRunnerUnavailable(RuntimeError):
    pass


class _WorkflowCallback(DefaultCallback):
    def __init__(self, event_handler=None, status_handler=None):
        super().__init__()
        self.external_event_handler = event_handler
        self.external_status_handler = status_handler

    def event_handler(self, data, **kwargs):
        super().event_handler(data, **kwargs)
        self.write_command_output(data)
        if self.external_event_handler:
            return self.external_event_handler(data)
        return True

    @staticmethod
    def write_command_output(data):
        if data.get("event") != "runner_on_ok":
            return
        event_data = data.get("event_data") or {}
        result = event_data.get("res") or {}
        if event_data.get("no_log") or result.get("_ansible_no_log"):
            return
        stdout = str(result.get("stdout") or "").rstrip("\r\n")
        if stdout:
            print(stdout, flush=True)

    def status_handler(self, data, **kwargs):
        super().status_handler(data, **kwargs)
        if self.external_status_handler:
            return self.external_status_handler(data)
        return None


class AnsibleRunnerService:
    """Workflow compatibility facade backed by the JumpServer runner."""

    def run(
        self,
        plan,
        event_handler=None,
        cancel_callback=None,
        status_handler=None,
        finished_callback=None,
    ):
        private_data_dir = Path(
            plan.private_data_dir or tempfile.mkdtemp(prefix="devops-ansible-")
        )
        inventory_path = private_data_dir / "inventory" / "hosts"
        playbook_path = private_data_dir / "project" / "playbook.yml"
        inventory_path.parent.mkdir(parents=True, exist_ok=True)
        inventory_path.write_text(plan.inventory, encoding="utf-8")
        inventory_path.chmod(0o600)
        # 临时排查日志：打印生成的 inventory（凭据密码脱敏），定位 ansible_connection 来源。
        for line in plan.inventory.splitlines():
            for marker in ("ansible_ssh_pass=", "ansible_password=", "ansible_become_password="):
                if marker in line:
                    line = line.split(marker)[0] + marker + "******"
            print(f"[ansible-debug] inventory: {line}", file=sys.stderr, flush=True)
        module = str(getattr(plan, "module", "") or "").strip()
        if not module:
            playbook_path.parent.mkdir(parents=True, exist_ok=True)
            playbook_path.write_text(
                yaml.safe_dump(plan.playbook, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            playbook_path.chmod(0o600)

        callback = _WorkflowCallback(event_handler, status_handler)
        try:
            cmdline = ["--forks", str(max(int(plan.forks), 1))]
            if plan.check_mode:
                cmdline.append("--check")
            JumpServerAnsibleService().run(
                AnsibleExecutionInput(
                    inventory=inventory_path,
                    playbook=None if module else playbook_path,
                    private_data_dir=private_data_dir,
                    extra_vars=plan.extra_vars or {},
                    env_vars=plan.env_vars or {},
                    timeout=plan.timeout_seconds,
                    host_pattern="all",
                    module=module or None,
                    module_args=str(getattr(plan, "module_args", "") or ""),
                ),
                callback=callback,
                cancel_callback=cancel_callback,
                cmdline=" ".join(cmdline),
            )
        except ImportError as exc:
            raise AnsibleRunnerUnavailable(
                "JumpServer Ansible dependencies are not installed."
            ) from exc
        finally:
            shutil.rmtree(private_data_dir, ignore_errors=True)

        result = {
            "status": callback.status,
            "rc": 0 if callback.status in {"success", "successful"} else 1,
            "stats": callback.summary,
        }
        if finished_callback:
            finished_callback(result)
        return result
