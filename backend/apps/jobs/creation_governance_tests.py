from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.jobs.services import create_workflow_run


class WorkflowRunCreationGovernanceTests(TestCase):
    @patch("apps.jobs.services.WorkflowRun.objects.create")
    @patch("apps.jobs.services.build_host_snapshot", return_value={"host_id": 1})
    @patch("apps.jobs.services.get_engine_settings", return_value={"timeout": 300})
    def test_creation_explicitly_initializes_worker_governance_fields(
        self, _settings, _snapshot, create
    ):
        create_workflow_run.__wrapped__(
            workflow_version=SimpleNamespace(),
            target_hosts=[SimpleNamespace()],
            input_vars={},
            worker_pool=SimpleNamespace(),
            triggered_by=SimpleNamespace(),
        )

        fields = create.call_args.kwargs
        self.assertEqual(fields["celery_task_id"], "")
        self.assertEqual(fields["worker_name"], "")
        self.assertEqual(fields["runner_workspace"], "")
        self.assertEqual(fields["timeout_seconds"], 300)
