import pytest
from apps.automation.models import WorkflowTemplate, WorkflowVersion
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool
from apps.jobs.application.runs import create_workflow_run


@pytest.mark.django_db
def test_creation_initializes_governance_and_persists_snapshot(user):
    user.is_superuser = True
    user.save()
    host = AssetHost.objects.create(
        hostname="governance",
        internal_ip="192.0.2.30",
        os_family="linux",
        connection_type="ssh",
    )
    pool = WorkerPool.objects.create(code="governance", name="Test", queue_name="test")
    template = WorkflowTemplate.objects.create(code="governance", name="Test")
    version = WorkflowVersion.objects.create(
        workflow=template,
        version=1,

    )
    from apps.automation.workflow_graph import replace_graph
    replace_graph(version, {
        "nodes": [{"id": "start", "type": "start"}, {"id": "end", "type": "end"}],
        "edges": [{"id": "done", "source": "start", "target": "end"}],
    })
    version.publish(user)
    run = create_workflow_run(
        workflow_version=version,
        target_hosts=[host],
        input_vars={},
        worker_pool=pool,
        triggered_by=user,
        timeout_seconds=300,
    )
    run.refresh_from_db()
    assert run.celery_task_id == ""
    assert run.worker_name == ""
    assert run.timeout_seconds == 300
    assert run.target_snapshot[0]["address"] == "192.0.2.30"
