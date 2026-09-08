from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.ops.contracts import ExecutionPlan
from apps.ops.executor import AnsibleExecutor


def plan(**changes):
    values = dict(run_id=1, node_run_id=2, command_type="linux_shell", target_hosts=[],
                  inventory="[all]\nlocalhost", playbook=[], extra_vars={}, env_vars={},
                  private_data_dir="", timeout_seconds=30)
    return ExecutionPlan(**(values | changes))


def test_no_callbacks_cannot_report_success():
    result = AnsibleExecutor(lambda **kw: SimpleNamespace(status="successful", rc=0)).execute(
        plan(), lambda event: None, lambda: False)
    assert result.status == "failed"
    assert "without host callback" in result.error


@pytest.mark.parametrize("status,rc,event,expected", [
    ("successful", 0, "runner_on_ok", "success"),
    ("failed", 2, "runner_on_failed", "failed"),
    ("failed", 4, "runner_on_unreachable", "failed"),
    ("timeout", 254, "runner_on_ok", "timeout"),
    ("canceled", 254, "runner_on_ok", "canceled"),
])
def test_runner_outcomes(status, rc, event, expected):
    received = []
    def runner(**options):
        options["event_handler"]({"event": event, "event_data": {"host": "localhost", "res": {"rc": rc}}})
        return SimpleNamespace(status=status, rc=rc)
    result = AnsibleExecutor(runner).execute(plan(), received.append, lambda: False)
    assert result.status == expected
    assert received[0].host == "localhost"


def test_cancellation_prevents_start():
    def runner(**options):
        pytest.fail("Canceled execution must not start Runner")
    assert AnsibleExecutor(runner).execute(plan(), lambda e: None, lambda: True).status == "canceled"


def test_no_log_and_unknown_events_are_safe():
    received = []
    def runner(**options):
        options["event_handler"]({"event": "new_runner_event", "event_data": {"password": "secret"}})
        options["event_handler"]({"event": "runner_on_ok", "stdout": "secret", "event_data": {
            "host": "localhost", "res": {"_ansible_no_log": True, "stdout": "secret"}}})
        return SimpleNamespace(status="successful", rc=0)
    assert AnsibleExecutor(runner).execute(plan(), received.append, lambda: False).status == "success"
    assert received[0].event_type == "runner_event"
    assert "secret" not in repr(received)


@pytest.mark.parametrize("raises", [False, True])
def test_only_owned_directory_is_cleaned_and_adhoc_options_are_forwarded(tmp_path, raises):
    sentinel = tmp_path / "keep"
    sentinel.write_text("keep")
    directories = []
    def runner(**options):
        directory = Path(options["private_data_dir"])
        directories.append(directory)
        assert directory.is_dir()
        assert Path(options["inventory"]).read_text() == "[all]\nlocalhost"
        assert options["module"] == "raw"
        assert options["module_args"] == "echo hello"
        assert "playbook" not in options
        assert options["cmdline"] == "--forks 3 --check"
        if raises:
            raise RuntimeError("password=secret")
        options["event_handler"]({"event": "runner_on_ok"})
        return SimpleNamespace(status="successful", rc=0)
    result = AnsibleExecutor(runner).execute(plan(private_data_dir=str(tmp_path), module="raw",
        module_args="echo hello", forks=3, check_mode=True), lambda e: None, lambda: False)
    assert result.status == ("failed" if raises else "success")
    assert "secret" not in (result.error or "")
    assert sentinel.read_text() == "keep"
    assert not directories[0].exists()


def test_failed_host_callback_cannot_be_overridden_by_successful_exit():
    def runner(**options):
        options["event_handler"]({"event": "runner_on_failed", "event_data": {"res": {"rc": 1}}})
        return SimpleNamespace(status="successful", rc=0)
    assert AnsibleExecutor(runner).execute(plan(), lambda event: None, lambda: False).status == "failed"


def test_deadline_cancels_runner(monkeypatch):
    ticks = iter([0, 31, 32])
    monkeypatch.setattr("apps.ops.executor.monotonic", lambda: next(ticks))
    def runner(**options):
        assert options["cancel_callback"]()
        return SimpleNamespace(status="canceled", rc=1)
    assert AnsibleExecutor(runner).execute(plan(), lambda event: None, lambda: False).status == "timeout"
