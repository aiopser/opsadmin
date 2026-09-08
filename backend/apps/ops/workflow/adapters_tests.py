from unittest import TestCase

from apps.ops.workflow.events import normalize_runner_event


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

    def test_preserves_unknown_runner_events(self):
        self.assertEqual(normalize_runner_event({"event": "unknown_event"}).event_type, "runner_event")
