from django.db import transaction
from django.utils import timezone

from apps.ops.workflow.adapters import RunnerResult

from .models import WorkflowRun


def redact_event_payload(payload):
    from .events import sanitize_runner_event

    return sanitize_runner_event(payload).get("payload") or {}


class JobEventProjector:
    def __init__(self, *, workflow_run, node_run):
        self.workflow_run = workflow_run
        self.node_run = node_run

    def apply(self, event):
        from .events import update_host_result_from_event

        return update_host_result_from_event(
            node_run=self.node_run,
            event=event.as_runner_event(),
        )

    @staticmethod
    @transaction.atomic
    def finalize(run_id, result):
        result = (
            result
            if isinstance(result, RunnerResult)
            else RunnerResult.from_mapping(result)
        )
        if result.status in {"canceled", "cancelled"}:
            target_status = WorkflowRun.Status.CANCELED
        elif result.status == "timeout":
            target_status = WorkflowRun.Status.TIMEOUT
        elif result.return_code == 0 and result.status in {
            "successful",
            "success",
            "ok",
        }:
            target_status = WorkflowRun.Status.SUCCESS
        else:
            target_status = WorkflowRun.Status.FAILED

        run = WorkflowRun.objects.select_for_update().get(id=run_id)
        if run.status in {
            WorkflowRun.Status.PENDING,
            WorkflowRun.Status.QUEUED,
            WorkflowRun.Status.RUNNING,
            WorkflowRun.Status.CANCEL_REQUESTED,
        }:
            finished_at = timezone.now()
            run.status = target_status
            run.finished_at = finished_at
            run.failure_reason = result.error or ""
            run.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "failure_reason",
                    "updated_at",
                ]
            )
        return run
