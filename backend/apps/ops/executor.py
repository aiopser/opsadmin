"""Synchronous Runner lifecycle with no jobs ORM or workflow state decisions."""

import json
import threading
import time as time_module
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

import yaml

from common.redaction import redact_text
from .contracts import AnsibleRunnerUnavailable, ExecutionPlan, RunnerResult
from .workflow.events import normalize_runner_event

CONSOLE_OUTPUT_MAX_CHARS = 512 * 1024
CONSOLE_OUTPUT_STREAM_INTERVAL_SECONDS = 2


class AnsibleExecutor:
    def __init__(self, runner=None):
        self.runner = runner

    def execute(self, plan: ExecutionPlan, on_event, should_cancel, on_console_output=None) -> RunnerResult:
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
        failure_msgs: list[str] = []

        def cancel():
            nonlocal timed_out, canceled
            timed_out = monotonic() >= deadline
            canceled = canceled or bool(should_cancel())
            return timed_out or canceled

        def summarize_failure(event) -> str:
            msg = event.result.get("msg") or event.result.get("reason") or ""
            if isinstance(msg, (dict, list)):
                msg = json.dumps(msg, ensure_ascii=False)
            text = str(msg).strip() or event.event_type
            return f"{event.host}: {text}" if event.host else text

        def _redacted_console(runner_result) -> str:
            """读取 runner 原生控制台 stdout，截断后脱敏；失败时返回空串不阻塞执行。"""
            try:
                stream = getattr(runner_result, "stdout", None)
                if stream is None:
                    return ""
                text = stream.read()
                if isinstance(text, bytes):
                    text = text.decode("utf-8", errors="replace")
                return _sanitize_console_text(str(text))
            except Exception:
                return ""

        def _sanitize_console_text(text: str) -> str:
            if len(text) > CONSOLE_OUTPUT_MAX_CHARS:
                text = text[:CONSOLE_OUTPUT_MAX_CHARS] + "\n...[output truncated]"
            return redact_text(text)

        stream_stop = threading.Event()

        def stream_console_output() -> None:
            """执行期间周期性读取 runner artifacts 的 stdout 文件并回调，
            让前端运行中即可看到原生控制台输出（与结束后读取的是同一数据源）。"""
            last_text = ""
            while not stream_stop.wait(CONSOLE_OUTPUT_STREAM_INTERVAL_SECONDS):
                try:
                    files = list(root.glob("artifacts/*/stdout"))
                    if not files:
                        continue
                    text = _sanitize_console_text(files[0].read_text(encoding="utf-8", errors="replace"))
                    if text and text != last_text and on_console_output is not None:
                        last_text = text
                        try:
                            on_console_output(text)
                        except Exception:
                            pass
                except Exception:
                    continue

        def emit(raw):
            nonlocal received_result, host_failed
            event = normalize_runner_event(raw)
            if event is None:
                return False
            received_result = received_result or event.event_type in {"host_ok", "host_changed", "host_failed", "host_unreachable", "task_skipped"}
            host_failed = host_failed or event.event_type in {"host_failed", "host_unreachable"}
            if event.event_type in {"host_failed", "host_unreachable", "execution_error"} and len(failure_msgs) < 3:
                failure_msgs.append(summarize_failure(event)[:200])
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
            # stdout 重定向到非 tty 文件时 ansible 默认禁用颜色，而前端控制台
            # 输出渲染依赖 ANSI 颜色码，故强制带色（用户显式配置优先）
            env_vars = dict(plan.env_vars)
            env_vars.setdefault("ANSIBLE_FORCE_COLOR", "1")
            options = {
                "private_data_dir": directory,
                "inventory": str(inventory),
                "project_dir": str(project),
                "extravars": dict(plan.extra_vars),
                "envvars": env_vars,
                "settings": {"job_timeout": plan.timeout_seconds},
                "cmdline": f"--forks {plan.forks}" + (" --check" if plan.check_mode else ""),
                "event_handler": emit,
                "cancel_callback": cancel,
                "quiet": True,
                "suppress_ansible_output": True,
                # stdout 仍写入 artifacts 供事后读取原生控制台输出，只是不打印到进程终端
                "suppress_output_file": False,
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
            if on_console_output is not None:
                threading.Thread(target=stream_console_output, daemon=True).start()
            try:
                result = runner(**options)
            except Exception as exc:
                return RunnerResult("failed", 1, error=redact_text(str(exc)))
            finally:
                stream_stop.set()
            console_output = _redacted_console(result)
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
            if success:
                return RunnerResult("success", rc, getattr(result, "stats", {}) or {}, console_output=console_output)
            # Surface per-host failure messages so callers (e.g. probes) show
            # the real cause instead of a generic "probe failed".
            return RunnerResult(
                "failed",
                rc,
                getattr(result, "stats", {}) or {},
                error=redact_text(" | ".join(failure_msgs)) or None,
                console_output=console_output,
            )
