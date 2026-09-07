from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.jobs.models import WorkflowRun
from apps.jobs.state_machine import (
    ExecutionLease,
    ExecutionStateMachine,
    InvalidExecutionTransition,
)


class ExecutionStateMachineTests(SimpleTestCase):
    def test_pending_must_be_queued_before_running(self):
        self.assertFalse(
            ExecutionStateMachine.can_transition(
                WorkflowRun.Status.PENDING,
                WorkflowRun.Status.RUNNING,
            )
        )
        self.assertTrue(
            ExecutionStateMachine.can_transition(
                WorkflowRun.Status.PENDING,
                WorkflowRun.Status.QUEUED,
            )
        )
        self.assertTrue(
            ExecutionStateMachine.can_transition(
                WorkflowRun.Status.QUEUED,
                WorkflowRun.Status.RUNNING,
            )
        )

    def test_transition_updates_run_and_is_idempotent_for_same_state(self):
        run = SimpleNamespace(
            status=WorkflowRun.Status.PENDING,
            save=Mock(),
        )

        ExecutionStateMachine.transition(run, WorkflowRun.Status.QUEUED)
        self.assertEqual(run.status, WorkflowRun.Status.QUEUED)
        run.save.assert_called_once()

        run.save.reset_mock()
        ExecutionStateMachine.transition(run, WorkflowRun.Status.QUEUED)
        run.save.assert_not_called()

    def test_transition_rejects_skipping_queue_and_terminal_reactivation(self):
        run = SimpleNamespace(status=WorkflowRun.Status.PENDING, save=Mock())
        with self.assertRaises(InvalidExecutionTransition):
            ExecutionStateMachine.transition(run, WorkflowRun.Status.RUNNING)

        run.status = WorkflowRun.Status.SUCCESS
        with self.assertRaises(InvalidExecutionTransition):
            ExecutionStateMachine.transition(run, WorkflowRun.Status.RUNNING)

    @patch("apps.jobs.state_machine.WorkflowRun")
    def test_touch_records_task_worker_and_heartbeat(self, workflow_run):
        queryset = workflow_run.objects.filter.return_value

        ExecutionLease.touch(7, task_id="task-7", worker="worker-a")

        workflow_run.objects.filter.assert_called_once_with(id=7)
        queryset.update.assert_called_once()
        update_fields = queryset.update.call_args.kwargs
        self.assertEqual(update_fields["celery_task_id"], "task-7")
        self.assertEqual(update_fields["worker_name"], "worker-a")
        self.assertIn("heartbeat_at", update_fields)

    def test_lease_is_expired_only_after_timeout_window(self):
        now = timezone.now()
        run = SimpleNamespace(
            heartbeat_at=now - timedelta(seconds=31),
            timeout_seconds=30,
        )
        self.assertTrue(ExecutionLease.is_expired(run, now=now))

        run.heartbeat_at = now - timedelta(seconds=29)
        self.assertFalse(ExecutionLease.is_expired(run, now=now))
