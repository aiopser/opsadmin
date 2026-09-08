"""Explicitly opt-in, localhost-only Runner validation on a disposable Linux worker."""

import os
import sys
from time import monotonic

import pytest

from apps.ops.contracts import ExecutionPlan
from apps.ops.executor import AnsibleExecutor


@pytest.fixture
def local_plan():
    if os.environ.get("DEVOPS_ISOLATED_RUNNER_TEST") != "yes":
        pytest.skip("Requires explicit disposable-worker opt-in; no real execution by default")
    if sys.platform != "linux":
        pytest.skip("Ansible control node integration requires Linux")
    return ExecutionPlan(
        run_id=0, node_run_id=0, command_type="module", target_hosts=[],
        inventory="[all]\nlocalhost ansible_connection=local\n", playbook=[],
        extra_vars={}, env_vars={}, private_data_dir="", timeout_seconds=45,
        module="ansible.builtin.command",
    )


def test_real_local_success(local_plan):
    from dataclasses import replace
    events = []
    result = AnsibleExecutor().execute(replace(local_plan, module_args="/bin/true"), events.append, lambda: False)
    assert result.status == "success"
    assert any(event.event_type == "host_ok" for event in events)


def test_real_local_failure(local_plan):
    from dataclasses import replace
    events = []
    result = AnsibleExecutor().execute(replace(local_plan, module_args="/bin/false"), events.append, lambda: False)
    assert result.status == "failed"
    assert any(event.event_type == "host_failed" for event in events)


def test_real_local_cancel(local_plan):
    from dataclasses import replace
    start = monotonic()
    result = AnsibleExecutor().execute(replace(local_plan, module_args="/bin/sleep 30"), lambda event: None,
        lambda: monotonic() - start >= 5)
    assert result.status == "canceled"
    assert monotonic() - start < 25
