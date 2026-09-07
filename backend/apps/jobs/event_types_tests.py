from unittest import TestCase

from apps.jobs.event_types import JobEvent
from apps.jobs.projections import redact_event_payload


class JobEventContractTests(TestCase):
    def test_job_event_keeps_sequence_and_payload(self):
        event = JobEvent(
            run_id=10,
            event_type="host_ok",
            sequence=42,
            host_id=7,
            message="ok",
            payload={"rc": 0},
        )

        self.assertEqual(event.run_id, 10)
        self.assertEqual(event.sequence, 42)
        self.assertEqual(event.payload, {"rc": 0})

    def test_redact_event_payload_removes_credentials(self):
        payload = redact_event_payload(
            {
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "res": {"stdout": "password=hunter2"},
                },
            }
        )

        serialized = str(payload)
        self.assertNotIn("hunter2", serialized)
        self.assertIn("[REDACTED]", serialized)
