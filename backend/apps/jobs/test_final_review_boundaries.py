"""Execution ownership and explicit retry boundaries found in final review."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

from apps.cmdb.models import AssetHost, CredentialRef
from apps.jobs.application.retry import retry_failed_node
from apps.jobs.application.runs import create_workflow_run
from apps.jobs.execution.snapshots import ensure_node_runs
from apps.jobs.models import NodeRun, NodeRunAttempt
from apps.jobs.test_execution_entrypoints import (
    actor,
    host,
    pool,
    published_workflow_version,
)

pytestmark = pytest.mark.django_db


def test_frozen_credential_revocation_blocks_ansible_transport(
    actor, host, pool
) -> None:
    from apps.jobs.execution.registry import execute_ansible_node

    original = CredentialRef.objects.create(
        name="revoked-original", type="password", scope="global", username="original"
    )
    replacement = CredentialRef.objects.create(
        name="current-binding", type="password", scope="global", username="current"
    )
    host.credential_ref = original
    host.save()
    run = create_workflow_run(
        workflow_version=published_workflow_version(),
        target_hosts=[host],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(
        status="running", attempt_count=1, celery_task_id="final-worker"
    )
    NodeRunAttempt.objects.create(
        node_run=node, attempt=1, status="running", celery_task_id="final-worker"
    )
    AssetHost.objects.filter(pk=host.pk).update(credential_ref=replacement)
    get_user_model().objects.filter(pk=actor.pk).update(is_superuser=False)

    def allowed(user, path, method):
        return path != f"/api/v1/cmdb/credential-refs/{original.pk}", ""

    with patch("apps.cmdb.targets.verify_permission", side_effect=allowed), patch(
        "apps.jobs.execution.registry.AnsibleExecutor"
    ) as transport:
        transport.return_value.execute.return_value = SimpleNamespace(
            status="success", return_code=0, error="", console_output=""
        )
        with pytest.raises(PermissionDenied):
            execute_ansible_node(
                node.pk, expected_attempt=1, expected_task_id="final-worker"
            )
        transport.return_value.execute.assert_not_called()


def test_explicit_retry_resumes_never_started_nodes_after_worker_loss(
    actor, host, pool
) -> None:
    from apps.jobs.recovery import StaleFinalizeKind, finalize_stale_run
    from apps.jobs.workflow_engine import plan_dispatch

    run = create_workflow_run(
        workflow_version=published_workflow_version(),
        target_hosts=[host],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    work_id = plan_dispatch(run.pk)[0]
    NodeRun.objects.filter(pk=work_id).update(status="running")
    NodeRunAttempt.objects.filter(node_run_id=work_id, attempt=1).update(
        status="running"
    )
    run.refresh_from_db()
    finalize_stale_run(run, StaleFinalizeKind.WORKER_LOST)
    end = run.node_runs.get(node_key="end")
    assert end.status == "canceled"
    with patch("apps.jobs.application.retry.enqueue_node_run"):
        retry_failed_node(work_id, actor=actor)
    NodeRun.objects.filter(pk=work_id).update(status="success")
    plan_dispatch(run.pk)
    end.refresh_from_db()
    run.refresh_from_db()
    assert (end.status, run.status) == ("success", "success")
