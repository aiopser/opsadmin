from unittest import TestCase

from apps.ops.workflow.adapters import AnsibleRunnerAdapter, RunnerResult
from apps.ops.workflow.events import normalize_runner_event
from apps.ops.workflow.plans import ExecutionPlan


class RunnerEventNormalizationTests(TestCase):
    def test_normalizes_host_result_events(self):
        normalized = normalize_runner_event(
            {
                "event": "runner_on_failed",
                "event_data": {
                    "host": "web01",
                    "res": {"rc": 2, "stderr": "failed"},
                },
            }
        )

        self.assertEqual(normalized.event_type, "host_failed")
        self.assertEqual(normalized.host, "web01")
        self.assertEqual(normalized.result["rc"], 2)

    def test_ignores_unknown_runner_events(self):
        self.assertIsNone(normalize_runner_event({"event": "unknown_event"}))


class RunnerAdapterTests(TestCase):
    def test_runner_result_normalizes_runner_mapping(self):
        result = RunnerResult.from_mapping(
            {"status": "successful", "rc": 0, "stats": {"ok": 1}}
        )

        self.assertEqual(result.status, "successful")
        self.assertEqual(result.return_code, 0)
        self.assertEqual(result.stats, {"ok": 1})
        self.assertIsNone(result.error)

    def test_ansible_adapter_forwards_callbacks_and_cancel_request(self):
        class FakeService:
            def __init__(self):
                self.calls = []

            def run(self, plan, event_handler=None, cancel_callback=None):
                self.calls.append((plan, event_handler, cancel_callback))
                self.assert_cancel_callback = cancel_callback
                event_handler({"event": "runner_on_start"})
                return {"status": "successful", "rc": 0, "stats": {}}

        service = FakeService()
        plan = ExecutionPlan(
            run_id=1,
            node_run_id=2,
            command_type="linux_shell",
            target_hosts=[],
            inventory="[linux]\n",
            playbook=[],
            extra_vars={},
            env_vars={},
            private_data_dir="",
            timeout_seconds=30,
        )
        received = []
        adapter = AnsibleRunnerAdapter(plan, service=service)

        result = adapter.start(
            received.append, lambda status, rc: received.append((status, rc))
        )
        self.assertEqual(result.return_code, 0)
        self.assertEqual(received[0]["event"], "runner_on_start")
        self.assertFalse(service.assert_cancel_callback())

        adapter.request_cancel()
        self.assertTrue(service.assert_cancel_callback())
