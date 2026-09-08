import pytest
from apps.automation.models import WorkflowTemplate, WorkflowVersion
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool
from apps.jobs.services import create_workflow_run


@pytest.mark.django_db
def test_creation_initializes_governance_and_persists_snapshot(user):
    user.is_superuser = True
    user.save()
    host = AssetHost.objects.create(hostname="governance", primary_ip="192.0.2.30", os_family="linux", connection_type="ssh")
    pool = WorkerPool.objects.create(code="governance", name="Test", queue_name="test")
    template = WorkflowTemplate.objects.create(code="governance", name="Test")
    version = WorkflowVersion.objects.create(workflow=template, version=1, status="published", graph_snapshot={"nodes": [], "edges": []})
    run = create_workflow_run(workflow_version=version, target_hosts=[host], input_vars={}, worker_pool=pool, triggered_by=user, timeout_seconds=300)
    run.refresh_from_db()
    assert run.celery_task_id == ""
    assert run.worker_name == ""
    assert run.runner_workspace == ""
    assert run.timeout_seconds == 300
    assert run.target_snapshot[0]["address"] == "192.0.2.30"
