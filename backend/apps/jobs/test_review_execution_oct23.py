"""Execution boundary regressions; all external execution is intercepted."""

from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.automation.models import CommandAtom, JenkinsBuild
from apps.jobs.application.retry import retry_failed_node
from apps.jobs.application.runs import clone_workflow_run, create_workflow_run
from apps.jobs.execution.snapshots import ensure_node_runs
from apps.jobs.models import NodeRun, NodeRunAttempt, WorkflowRun
from apps.jobs.node_executors import execute_jenkins, record_generic_result
from apps.jobs.test_execution_entrypoints import (
    actor,
    api_run,
    host,
    pool,
    jenkins_run,
    published_workflow_version,
)
from apps.jobs.workflow_engine import plan_dispatch

pytestmark = pytest.mark.django_db


def make_run(actor, host, pool):
    return create_workflow_run(
        workflow_version=published_workflow_version(),
        target_hosts=[host],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )


@pytest.mark.parametrize("entry", ["manual", "scheduled", "clone"])
def test_application_rejects_high_risk_without_current_permission(
    actor, host, pool, entry, monkeypatch
):
    run = make_run(actor, host, pool)
    CommandAtom.objects.filter(code="entry").update(risk_level="high")
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    # Isolate the command authorization boundary from asset/pool permissions.
    monkeypatch.setattr(
        "apps.jobs.application.runs.snapshot_targets", lambda **kw: run.target_snapshot
    )
    monkeypatch.setattr(
        "apps.jobs.application.runs.authorize_frozen_targets",
        lambda **kw: run.target_snapshot,
    )
    monkeypatch.setattr(
        "apps.jobs.application.runs.resolve_worker_pool", lambda **kw: pool
    )
    with pytest.raises(PermissionDenied, match="高危"):
        if entry == "clone":
            clone_workflow_run(run, actor)
        else:
            create_workflow_run(
                workflow_version=run.workflow_version,
                target_hosts=[host],
                input_vars={},
                worker_pool=pool,
                triggered_by=actor,
                trigger_type=entry,
            )
    assert WorkflowRun.objects.count() == 1


def test_old_generic_result_cannot_overwrite_new_attempt(actor, host, pool):
    run = make_run(actor, host, pool)
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(
        status="running", attempt_count=1, celery_task_id="old"
    )
    node.refresh_from_db()
    NodeRun.objects.filter(pk=node.pk).update(
        attempt_count=2, celery_task_id="new", output_vars={"new": True}
    )
    record_generic_result(node, True, {"late": True})
    node.refresh_from_db()
    assert (node.status, node.output_vars) == ("running", {"new": True})
    assert not run.event_logs.filter(event_type="node_succeeded").exists()


def test_execute_node_does_not_publish_late_result_as_next_attempt(
    actor, host, pool, monkeypatch
):
    from apps.jobs.tasks import execute_node

    run = make_run(actor, host, pool)
    run.status = "running"
    run.save(update_fields=["status"])
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(
        node_type="api", status="queued", attempt_count=1
    )
    first = NodeRunAttempt.objects.create(node_run=node, attempt=1)
    queued = []

    def late_result(*args, **kwargs):
        NodeRunAttempt.objects.filter(pk=first.pk).update(status="timeout")
        NodeRun.objects.filter(pk=node.pk).update(
            status="running",
            attempt_count=2,
            celery_task_id="new",
            output_vars={"new": True},
        )
        NodeRunAttempt.objects.create(node_run=node, attempt=2, status="running")
        return {"late": True}

    monkeypatch.setattr("apps.jobs.tasks.execute_generic_node", late_result)
    monkeypatch.setattr(
        "apps.jobs.tasks.enqueue_workflow_run",
        lambda *args, **kwargs: queued.append(args),
    )
    execute_node(node.id, 1)
    node.refresh_from_db()
    first.refresh_from_db()
    assert (node.status, node.output_vars, first.status) == (
        "running",
        {"new": True},
        "timeout",
    )
    assert queued == []


def test_ansible_late_callbacks_console_and_completion_are_fenced(
    actor, host, pool, monkeypatch, tmp_path
):
    from apps.jobs.execution.registry import execute_ansible_node

    run = make_run(actor, host, pool)
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(
        status="running", attempt_count=1, celery_task_id="old"
    )
    NodeRunAttempt.objects.create(node_run=node, attempt=1, status="running")
    private_dir = tmp_path / "runner"
    private_dir.mkdir()
    monkeypatch.setattr(
        "apps.jobs.execution.registry.build_gateway_inventory",
        lambda *args: ({}, str(private_dir)),
    )

    def late_execute(self, plan, on_event, is_canceled, on_console_output):
        NodeRun.objects.filter(pk=node.pk).update(
            status="running",
            attempt_count=2,
            celery_task_id="new",
            console_output="new console",
            output_vars={"new": True},
        )
        NodeRunAttempt.objects.create(node_run=node, attempt=2, status="running")
        on_console_output("late console")
        on_event(
            SimpleNamespace(
                raw_event={
                    "event": "runner_on_ok",
                    "uuid": "old-event",
                    "event_data": {"host": host.hostname, "res": {"stdout": "late"}},
                }
            )
        )
        return SimpleNamespace(
            status="successful", return_code=0, error="", console_output="late console"
        )

    monkeypatch.setattr(
        "apps.jobs.execution.registry.AnsibleExecutor.execute", late_execute
    )
    execute_ansible_node(node.pk)
    node.refresh_from_db()
    assert (node.status, node.output_vars, node.console_output) == (
        "running",
        {"new": True},
        "new console",
    )
    assert not node.host_results.exists()


def test_retry_reopens_only_failure_blocked_nodes(actor, host, pool, monkeypatch):
    run = make_run(actor, host, pool)
    graph = deepcopy(run.graph_snapshot)
    graph["nodes"].insert(2, {**deepcopy(graph["nodes"][1]), "id": "later"})
    graph["nodes"].insert(3, {**deepcopy(graph["nodes"][1]), "id": "not_selected"})
    graph["nodes"].insert(
        1, {"id": "split", "type": "parallel_gateway", "timeoutSeconds": 60}
    )
    graph["edges"] = [
        {"id": "a", "source": "start", "target": "split"},
        {"id": "f", "source": "split", "target": "work"},
        {"id": "b", "source": "work", "target": "later"},
        {"id": "c", "source": "later", "target": "end"},
        {
            "id": "d",
            "source": "split",
            "target": "not_selected",
            "condition": "false",
        },
        {"id": "e", "source": "not_selected", "target": "end"},
    ]
    run.graph_snapshot = graph
    run.save(update_fields=["graph_snapshot"])
    work_id = plan_dispatch(run.pk)[0]
    NodeRun.objects.filter(pk=work_id).update(status="failed", failure_reason="failed")
    assert plan_dispatch(run.pk) == []
    monkeypatch.setattr(
        "apps.jobs.application.retry.enqueue_node_run", lambda *args: None
    )
    retry_failed_node(work_id, actor=actor)
    node = NodeRun.objects.get(pk=work_id)
    node.status = "running"
    node.save(update_fields=["status"])
    record_generic_result(node, True)
    queued = plan_dispatch(run.pk)
    later = run.node_runs.get(node_key="later")
    assert queued == [later.pk]
    assert later.status == "queued"
    assert run.node_runs.get(node_key="not_selected").status == "skipped"


def test_jenkins_cancellation_stops_queue_polling_without_claiming_remote_abort(
    jenkins_run, monkeypatch
):
    server, job, run, node = jenkins_run
    calls = []
    monkeypatch.setattr(
        "apps.jobs.node_executors.trigger_jenkins_job",
        lambda *args, **kwargs: "https://ci.example.test/queue/1/",
    )

    def request(method, url, *args):
        calls.append((method, url))
        WorkflowRun.objects.filter(pk=run.pk).update(status="cancel_requested")
        return 200, {}, "{}"

    monkeypatch.setattr("apps.jobs.node_executors._request", request)
    monkeypatch.setattr("apps.jobs.node_executors.time.sleep", lambda *args: None)
    with pytest.raises(Exception, match="停止等待"):
        execute_jenkins(node, {})
    assert len(calls) == 1
    record = JenkinsBuild.objects.get(node_run=node)
    assert record.result == "WAIT_CANCELED"
    assert record.status != JenkinsBuild.Status.ABORTED


def test_worker_rechecks_revoked_high_risk_permission_before_transport(
    actor, host, pool, monkeypatch
):
    from apps.jobs.tasks import execute_node

    run = make_run(actor, host, pool)
    CommandAtom.objects.filter(code="entry").update(risk_level="high")
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(status="queued", attempt_count=1)
    NodeRunAttempt.objects.create(node_run=node, attempt=1)
    calls = []
    monkeypatch.setattr(
        "apps.jobs.tasks.execute_ansible_node",
        lambda *args, **kwargs: calls.append(args),
    )
    monkeypatch.setattr(
        "apps.jobs.tasks.enqueue_workflow_run", lambda *args, **kwargs: None
    )
    execute_node(node.pk, 1)
    node.refresh_from_db()
    assert node.status == "failed"
    assert "高危" in node.failure_reason
    assert calls == []


def test_quick_wrapper_cannot_use_caller_high_risk_flag_as_authorization(
    actor, host, pool, monkeypatch
):
    from apps.jobs.application.runs import create_quick_command_run

    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    monkeypatch.setattr(
        "apps.jobs.application.runs.resolve_targets", lambda **kwargs: []
    )
    with pytest.raises(PermissionDenied, match="高危"):
        create_quick_command_run(
            command_type="linux_shell",
            command_content="echo arbitrary",
            host_ids=[host.pk],
            worker_pool=pool,
            triggered_by=actor,
            can_execute_high_risk=True,
        )
    assert not WorkflowRun.objects.exists()


def test_node_retry_rejects_actor_without_high_risk_permission(actor, host, pool):
    run = make_run(actor, host, pool)
    CommandAtom.objects.filter(code="entry").update(risk_level="high")
    node = ensure_node_runs(run)["work"]
    NodeRun.objects.filter(pk=node.pk).update(status="failed", attempt_count=1)
    viewer = get_user_model().objects.create_user(username="retry-viewer")
    with pytest.raises(PermissionDenied, match="高危"):
        retry_failed_node(node.pk, actor=viewer)
    node.refresh_from_db()
    assert (node.status, node.attempt_count) == ("failed", 1)


def test_inactive_role_does_not_grant_high_risk_permission(actor, host, pool):
    from apps.jobs.application.authorization import authorize_execution
    from apps.permission.models import Permission, Role

    run = make_run(actor, host, pool)
    CommandAtom.objects.filter(code="entry").update(risk_level="high")
    role = Role.objects.create(name="disabled-high-risk", is_active=False)
    role.permission.add(
        Permission.objects.create(
            name="high", code="automation.command:execute_high_risk", type="api"
        )
    )
    actor.role.add(role)
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    with pytest.raises(PermissionDenied, match="高危"):
        authorize_execution(actor=actor, graph_snapshot=run.graph_snapshot)
    role.is_active = True
    role.save(update_fields=["is_active"])
    authorize_execution(actor=actor, graph_snapshot=run.graph_snapshot)


def test_late_runner_event_stays_with_original_attempt_without_projecting(
    actor, host, pool
):
    from apps.jobs.events import append_run_event

    run = make_run(actor, host, pool)
    node = ensure_node_runs(run)["work"]
    old = NodeRunAttempt.objects.create(
        node_run=node, attempt=1, status="timeout", celery_task_id="old"
    )
    NodeRun.objects.filter(pk=node.pk).update(
        status="running", attempt_count=2, celery_task_id="new"
    )
    log = append_run_event(
        run_id=run.pk,
        node_run_id=node.pk,
        attempt_id=old.pk,
        event_key="late",
        event={
            "event": "runner_on_ok",
            "event_data": {"host": host.hostname, "res": {"stdout": "old"}},
        },
    )
    assert log.attempt_id == old.pk
    assert not node.host_results.exists()


@pytest.mark.parametrize("scope", ["department", "all"])
def test_node_and_host_details_share_workflow_data_scope(actor, host, pool, scope):
    from apps.jobs.models import HostRunResult
    from apps.jobs.views import HostRunResultViewSet, NodeRunViewSet
    from apps.permission.models import Role
    from apps.user.models import Department

    dept = Department.objects.create(name="execution-scope")
    actor.department = dept
    actor.save(update_fields=["department"])
    viewer = get_user_model().objects.create_user(
        username="scope-viewer", department=dept
    )
    viewer.role.add(Role.objects.create(name="execution-scope", job_data_scope=scope))
    run = make_run(actor, host, pool)
    node = ensure_node_runs(run)["work"]
    result = HostRunResult.objects.create(
        node_run=node, hostname="test", ip="192.0.2.1"
    )
    for view_class, pk in [
        (NodeRunViewSet, node.pk),
        (HostRunResultViewSet, result.pk),
    ]:
        view = view_class()
        view.request = SimpleNamespace(user=viewer)
        assert view.get_queryset().filter(pk=pk).exists()


def test_canceled_jenkins_build_stops_before_querying_build_status(
    jenkins_run, monkeypatch
):
    server, job, run, node = jenkins_run
    calls = []
    monkeypatch.setattr(
        "apps.jobs.node_executors.trigger_jenkins_job",
        lambda *args, **kwargs: "https://ci.example.test/queue/1/",
    )

    def request(method, url, *args):
        calls.append((method, url))
        if "queue" in url:
            return (
                200,
                {},
                '{"executable": {"url": "https://ci.example.test/job/test/1/", "number": 1}}',
            )
        WorkflowRun.objects.filter(pk=run.pk).update(status="cancel_requested")
        return 200, {}, "partial console"

    monkeypatch.setattr("apps.jobs.node_executors._request", request)
    with pytest.raises(Exception, match="停止等待"):
        execute_jenkins(node, {})
    assert len(calls) == 2
    assert JenkinsBuild.objects.get(node_run=node).result == "WAIT_CANCELED"


def test_orphaned_schedule_is_not_automatically_promoted_to_superuser(
    actor, host, pool
):
    from apps.jobs.models import ScheduledJob
    from apps.jobs.tasks import _transfer_orphan_schedule_ownerships

    owner = get_user_model().objects.create_user(
        username="revoked-owner", is_active=False
    )
    schedule = ScheduledJob.objects.create(
        name="revoked",
        cron_expression="* * * * *",
        workflow_version=published_workflow_version(),
        worker_pool=pool,
        created_by=owner,
    )
    assert _transfer_orphan_schedule_ownerships() == 0
    schedule.refresh_from_db()
    assert schedule.created_by_id == owner.pk


def test_revoked_one_off_schedule_records_rejection_instead_of_invalid_cron(
    actor, host, pool, monkeypatch
):
    from apps.jobs.models import ScheduledJob, ScheduledJobOutcome
    from apps.jobs.tasks import _dispatch_scheduled_run

    version = published_workflow_version()
    CommandAtom.objects.filter(code="entry").update(risk_level="high")
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    now = timezone.now()
    schedule = ScheduledJob.objects.create(
        name="once-revoked",
        schedule_type="once",
        run_at=now - timedelta(seconds=1),
        cron_expression="",
        workflow_version=version,
        worker_pool=pool,
        created_by=actor,
    )
    monkeypatch.setattr(
        "apps.jobs.application.runs.resolve_targets", lambda **kwargs: []
    )
    assert _dispatch_scheduled_run(schedule, schedule.run_at, now) is None
    outcome = ScheduledJobOutcome.objects.get(scheduled_job=schedule)
    assert outcome.outcome == "invalid"
    assert "高危" in outcome.reason
    assert not WorkflowRun.objects.exists()


def test_missing_command_risk_metadata_cannot_silently_downgrade_frozen_graph(
    actor, host, pool
):
    from apps.automation.models import CommandVersion
    from apps.jobs.application.authorization import authorize_execution

    run = make_run(actor, host, pool)
    CommandVersion.objects.filter(command__code="entry").delete()
    actor.is_superuser = False
    actor.save(update_fields=["is_superuser"])
    with pytest.raises(PermissionDenied, match="高危"):
        authorize_execution(actor=actor, graph_snapshot=run.graph_snapshot)


def test_generic_transport_cannot_start_after_attempt_is_replaced(api_run, monkeypatch):
    from apps.jobs.tasks import execute_node

    _, run, node = api_run
    NodeRun.objects.filter(pk=node.pk).update(
        status="queued", node_type="api", attempt_count=1
    )
    NodeRunAttempt.objects.create(node_run=node, attempt=1)
    calls = []

    def replace_attempt(*args):
        NodeRun.objects.filter(pk=node.pk).update(
            status="running", attempt_count=2, celery_task_id="new"
        )
        return {}

    monkeypatch.setattr("apps.jobs.tasks.runtime_context", replace_attempt)
    monkeypatch.setattr(
        "apps.jobs.tasks.enqueue_workflow_run", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "apps.jobs.node_executors._request",
        lambda *args, **kwargs: calls.append(args) or (200, {}, "{}"),
    )
    execute_node(node.pk, 1)
    node.refresh_from_db()
    assert node.status == "running"
    assert calls == []
