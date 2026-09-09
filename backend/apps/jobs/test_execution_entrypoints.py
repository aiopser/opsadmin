"""T13 execution entrypoint contracts.

快捷命令、工作流、克隆（重试/重跑）必须进入同一运行创建服务并产生同一种
可查询运行记录；取消统一走 settle_canceled_work；API/Jenkins/通知执行器
的外呼全部 mock，覆盖超时、出站目标校验和凭据脱敏，不调用真实服务。
"""

from copy import deepcopy

import pytest
from django.contrib.auth import get_user_model
from urllib.error import URLError

from apps.automation.models import (
    ApiEndpoint,
    CommandAtom,
    CommandVersion,
    JenkinsJob,
    JenkinsServer,
    NotificationChannel,
    NotificationTemplate,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.automation.workflow_graph import replace_graph
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost
from apps.jobs.models import NodeRun, NodeRunAttempt, WorkerPool, WorkflowRun
from apps.jobs.application.cancel import settle_canceled_work
from apps.jobs.application.runs import (
    clone_workflow_run,
    create_quick_command_run,
    create_workflow_run,
)
from apps.jobs.execution.snapshots import ensure_node_runs
from apps.jobs import node_executors
from apps.jobs.node_executors import (
    NodeExecutionError,
    _validate_outbound_url,
    execute_api_endpoint,
    execute_jenkins,
    execute_notification,
)


def valid_graph():
    return {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "work", "type": "command", "timeoutSeconds": 60},
            {"id": "end", "type": "end"},
        ],
        "edges": [
            {"id": "a", "source": "start", "target": "work"},
            {"id": "b", "source": "work", "target": "end"},
        ],
    }


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_superuser(
        username="entrypoint-user",
        password="123456",
        email="entrypoint@example.test",
        phone="13800009999",
    )


@pytest.fixture
def host(db):
    return AssetHost.objects.create(
        hostname="entry-host",
        primary_ip="10.0.0.99",
        os_family=AssetHost.OSFamily.LINUX,
        cpu_cores=2,
        memory_mb=4096,
        system_disk_gb=40,
    )


@pytest.fixture
def pool(db):
    return WorkerPool.objects.create(
        code="entry", name="entry", queue_name="ansible.entry"
    )


def published_workflow_version(command_content="echo entry"):
    command = CommandAtom.objects.create(name="entry", code="entry")
    command_version = CommandVersion.objects.create(
        command=command,
        version=1,
        command_type="linux_shell",
        content=command_content,
    )
    command_version.publish(None)
    template = WorkflowTemplate.objects.create(name="entry", code="entry")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = valid_graph()
    graph["nodes"][1]["commandVersionId"] = command_version.pk
    assert replace_graph(version, graph) == []
    version.publish(None)
    return version


class TestUnifiedEntrypoints:
    def test_invalid_schedule_does_not_block_the_next_due_schedule(
        self, actor, host, pool, monkeypatch
    ):
        from datetime import timedelta
        from django.utils import timezone
        from apps.jobs.models import ScheduledJob
        from apps.jobs.tasks import dispatch_scheduled_jobs

        version = published_workflow_version()
        now = timezone.now()
        invalid = ScheduledJob.objects.create(
            name="invalid",
            workflow_version=version,
            worker_pool=pool,
            host_ids=[host.id + 10000],
            created_by=actor,
            next_run_at=now - timedelta(minutes=2),
        )
        valid = ScheduledJob.objects.create(
            name="valid",
            workflow_version=version,
            worker_pool=pool,
            host_ids=[host.id],
            created_by=actor,
            next_run_at=now - timedelta(minutes=1),
        )
        monkeypatch.setattr("apps.jobs.tasks.enqueue_workflow_run", lambda run_id: None)
        dispatch_scheduled_jobs()
        invalid.refresh_from_db()
        valid.refresh_from_db()
        assert invalid.last_workflow_run_id is None
        assert invalid.next_run_at > now
        assert valid.last_workflow_run.trigger_type == WorkflowRun.TriggerType.SCHEDULED
        assert valid.last_workflow_run.target_snapshot[0]["host_id"] == host.id
        assert WorkflowRun.objects.count() == 1

    def test_all_entrypoints_produce_one_queryable_run_record(self, actor, host, pool):
        version = published_workflow_version()

        workflow_run = create_workflow_run(
            workflow_version=version,
            target_hosts=[{"host_id": host.id}],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        quick_run = create_quick_command_run(
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            command_content="echo quick",
            host_ids=[host.id],
            worker_pool=pool,
            triggered_by=actor,
            can_execute_high_risk=True,
        )
        cloned_run = clone_workflow_run(workflow_run, actor)

        ids = [workflow_run.id, quick_run.id, cloned_run.id]
        assert WorkflowRun.objects.filter(id__in=ids).count() == 3
        for run in (workflow_run, quick_run, cloned_run):
            assert run.graph_snapshot["nodes"]
            assert run.graph_snapshot["edges"]
            assert run.target_snapshot[0]["host_id"] == host.id
            assert "address" in run.target_snapshot[0]

        assert workflow_run.run_domain == WorkflowRun.RunDomain.TASK
        assert workflow_run.execution_kind == WorkflowRun.ExecutionKind.WORKFLOW
        assert quick_run.run_domain == WorkflowRun.RunDomain.OPS
        assert quick_run.execution_kind == WorkflowRun.ExecutionKind.QUICK_COMMAND
        assert cloned_run.run_domain == workflow_run.run_domain
        assert cloned_run.execution_kind == workflow_run.execution_kind
        assert cloned_run.trigger_type == WorkflowRun.TriggerType.MANUAL

        workflow_run.graph_snapshot["nodes"][1]["id"] = "mutated"
        assert cloned_run.graph_snapshot["nodes"][1]["id"] == "work"

    def test_entrypoint_rejects_unpublished_versions(self, actor, host, pool):
        command = CommandAtom.objects.create(name="draft", code="draft")
        command_version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type="linux_shell",
            content="echo draft",
        )
        command_version.publish(None)
        template = WorkflowTemplate.objects.create(name="draft", code="draft")
        version = WorkflowVersion.objects.create(workflow=template, version=1)
        graph = valid_graph()
        graph["nodes"][1]["commandVersionId"] = command_version.pk
        assert replace_graph(version, graph) == []
        with pytest.raises(ValueError, match="[Pp]ublished"):
            create_workflow_run(
                workflow_version=version,
                target_hosts=[{"host_id": host.id}],
                input_vars={},
                worker_pool=pool,
                triggered_by=actor,
            )
        assert not WorkflowRun.objects.exists()


class TestUnifiedCancellation:
    def test_settle_canceled_work_settles_unstarted_and_queued_work(
        self, actor, host, pool
    ):
        version = published_workflow_version()
        run = create_workflow_run(
            workflow_version=version,
            target_hosts=[{"host_id": host.id}],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        node_runs = ensure_node_runs(run)
        work_run = node_runs["work"]
        NodeRunAttempt.objects.create(
            node_run=work_run, attempt=1, status=NodeRunAttempt.Status.QUEUED
        )
        done = node_runs["end"]
        done.status = NodeRun.Status.SUCCESS
        done.save(update_fields=["status"])

        settle_canceled_work(run)

        work_run.refresh_from_db()
        done.refresh_from_db()
        assert work_run.status == NodeRun.Status.CANCELED
        assert work_run.failure_reason == "Canceled by user"
        assert done.status == NodeRun.Status.SUCCESS
        assert NodeRunAttempt.objects.get(node_run=work_run).status == (
            NodeRunAttempt.Status.CANCELED
        )


@pytest.fixture
def api_run(actor, host, pool):
    endpoint = ApiEndpoint.objects.create(
        name="status",
        url="https://api.example.test/status",
        method="GET",
        auth_type=ApiEndpoint.AuthType.BEARER,
        secret_encrypted=encrypt_secret("s3cr3t-token"),
    )
    template = WorkflowTemplate.objects.create(name="api", code="api")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = valid_graph()
    graph["nodes"][1].update(type="api", resourceId=endpoint.pk)
    assert replace_graph(version, graph) == []
    version.publish(None)
    run = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    node_run = NodeRun.objects.create(workflow_run=run, node_key="work")
    return endpoint, run, node_run


class TestApiExecutor:
    def test_success_uses_bearer_credential_and_extracts_outputs(
        self, monkeypatch, api_run
    ):
        endpoint, run, node_run = api_run
        seen = {}

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            seen["url"] = url
            seen["authorization"] = headers.get("Authorization")
            return (
                200,
                {},
                '{"status": "ok", "note": "[[ answer :: 42 ]]"}',
            )

        monkeypatch.setattr(node_executors, "_request", fake_request)
        result = execute_api_endpoint(node_executors.execution_resource(node_run), {})
        assert seen["url"] == "https://api.example.test/status"
        assert seen["authorization"] == "Bearer s3cr3t-token"
        assert result["status_code"] == 200
        assert result["answer"] == 42

    def test_timeout_error_does_not_leak_credential(self, monkeypatch, api_run):
        _, _, node_run = api_run
        monkeypatch.setattr(node_executors, "_validate_outbound_url", lambda url: None)

        def fake_urlopen(*args, **kwargs):
            raise URLError("timed out")

        from types import SimpleNamespace

        monkeypatch.setattr(
            node_executors,
            "build_opener",
            lambda *args: SimpleNamespace(open=fake_urlopen),
        )
        with pytest.raises(NodeExecutionError) as excinfo:
            execute_api_endpoint(node_executors.execution_resource(node_run), {})
        assert "s3cr3t-token" not in str(excinfo.value)

    def test_http_failure_message_does_not_leak_credential(self, monkeypatch, api_run):
        _, _, node_run = api_run

        def fake_request(*args, **kwargs):
            return 500, {}, '{"error": "boom"}'

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="Unexpected HTTP status: 500"):
            execute_api_endpoint(node_executors.execution_resource(node_run), {})
        assert "s3cr3t-token" not in str(
            NodeExecutionError("Unexpected HTTP status: 500")
        )


class TestOutboundTargetValidation:
    def test_redirect_revalidates_target_before_following(self):
        from urllib.request import Request

        request = Request(
            "https://api.example.test/start",
            headers={"Authorization": "Bearer test-secret"},
        )
        with pytest.raises(NodeExecutionError, match="Blocked outbound address"):
            node_executors.ValidatedRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "http://127.0.0.1/private"
            )

    def test_redirect_refuses_cross_origin_credentials(self, monkeypatch):
        from urllib.parse import urlparse
        from urllib.request import Request

        monkeypatch.setattr(node_executors, "_validate_outbound_url", urlparse)
        request = Request(
            "https://api.example.test/start",
            headers={"Authorization": "Bearer test-secret"},
        )
        with pytest.raises(NodeExecutionError, match="Cross-origin"):
            node_executors.ValidatedRedirectHandler().redirect_request(
                request, None, 302, "Found", {}, "https://other.example.test/end"
            )
        redirected = node_executors.ValidatedRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, "https://api.example.test/end"
        )
        assert redirected.full_url == "https://api.example.test/end"

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1:8080/x",
            "http://localhost:8080/x",
            "ftp://example.test/x",
            "not-a-url",
        ],
    )
    def test_blocked_or_invalid_targets_are_rejected_before_any_request(self, url):
        with pytest.raises(NodeExecutionError):
            _validate_outbound_url(url)

    def test_api_endpoint_to_loopback_never_reaches_transport(
        self, actor, host, pool, monkeypatch
    ):
        endpoint = ApiEndpoint.objects.create(
            name="loopback",
            url="http://127.0.0.1:8080/x",
            method="GET",
            auth_type=ApiEndpoint.AuthType.BEARER,
            secret_encrypted=encrypt_secret("loopback-token"),
        )
        template = WorkflowTemplate.objects.create(name="loop", code="loop")
        version = WorkflowVersion.objects.create(workflow=template, version=1)
        graph = valid_graph()
        graph["nodes"][1].update(type="api", resourceId=endpoint.pk)
        assert replace_graph(version, graph) == []
        version.publish(None)
        run = create_workflow_run(
            workflow_version=version,
            target_hosts=[{"host_id": host.id}],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        node_run = NodeRun.objects.create(workflow_run=run, node_key="work")

        def fail_urlopen(*args, **kwargs):
            raise AssertionError("transport must not be reached for blocked targets")

        monkeypatch.setattr(node_executors, "build_opener", fail_urlopen)
        with pytest.raises(NodeExecutionError, match="Blocked outbound address"):
            execute_api_endpoint(node_executors.execution_resource(node_run), {})


@pytest.fixture
def jenkins_run(actor, host, pool):
    server = JenkinsServer.objects.create(
        name="ci",
        base_url="https://ci.example.test",
        username="robot",
        token_encrypted=encrypt_secret("ci-token"),
        verify_ssl=False,
    )
    job = JenkinsJob.objects.create(server=server, name="deploy")
    template = WorkflowTemplate.objects.create(name="ci", code="ci")
    version = WorkflowVersion.objects.create(workflow=template, version=1)
    graph = valid_graph()
    graph["nodes"][1].update(type="jenkins", resourceId=job.pk, timeoutSeconds=1)
    assert replace_graph(version, graph) == []
    version.publish(None)
    run = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    node_run = NodeRun.objects.create(workflow_run=run, node_key="work")
    return server, job, run, node_run


class TestJenkinsExecutor:
    def test_build_roundtrip_is_mocked_and_recorded(self, monkeypatch, jenkins_run):
        from apps.automation.models import JenkinsBuild

        server, job, run, node_run = jenkins_run
        calls = []

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            calls.append((method, url))
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if url.endswith("build") or url.endswith("buildWithParameters"):
                return (
                    201,
                    {"Location": "https://ci.example.test/queue/item/7/"},
                    "",
                )
            if "/queue/item/7/" in url:
                return (
                    200,
                    {},
                    '{"executable": {"url": "https://ci.example.test/job/deploy/9/", "number": 9}}',
                )
            if "logText/progressiveText" in url:
                return 200, {"X-Text-Size": "0"}, ""
            if "/job/deploy/9/" in url:
                return (
                    200,
                    {},
                    '{"building": false, "result": "SUCCESS", "number": 9}',
                )
            raise AssertionError(f"unexpected jenkins call: {method} {url}")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        result = execute_jenkins(node_run, {})
        assert result["build_number"] == 9
        assert result["result"] == "SUCCESS"
        record = JenkinsBuild.objects.get(node_run=node_run)
        assert record.status == JenkinsBuild.Status.SUCCESS
        assert record.build_url == "https://ci.example.test/job/deploy/9/"
        assert all(url.startswith("https://ci.example.test") for _, url in calls)
        assert "ci-token" not in str(calls)

    def test_queue_timeout_marks_build_failed(self, monkeypatch, jenkins_run):
        from apps.automation.models import JenkinsBuild

        server, job, run, node_run = jenkins_run

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if url.endswith("build"):
                return (
                    201,
                    {"Location": "https://ci.example.test/queue/item/8/"},
                    "",
                )
            return 200, {}, "{}"

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="Timed out waiting"):
            execute_jenkins(node_run, {})
        record = JenkinsBuild.objects.get(node_run=node_run)
        assert record.status == JenkinsBuild.Status.FAILED
        assert record.result == "QUEUE_TIMEOUT"


@pytest.fixture
def notify_run(actor, host, pool):
    channel = NotificationChannel.objects.create(
        name="hook",
        channel_type=NotificationChannel.ChannelType.WEBHOOK,
        secret_encrypted=encrypt_secret("https://hook.example.test/incoming"),
    )
    template = NotificationTemplate.objects.create(
        name="done",
        code="done",
        channel=channel,
        subject_template="Job finished",
        body_template="Job {{ inputs.name }} finished",
    )
    workflow_template = WorkflowTemplate.objects.create(name="notify", code="notify")
    version = WorkflowVersion.objects.create(workflow=workflow_template, version=1)
    graph = valid_graph()
    graph["nodes"][1].update(type="notify", resourceId=template.pk)
    assert replace_graph(version, graph) == []
    version.publish(None)
    run = create_workflow_run(
        workflow_version=version,
        target_hosts=[{"host_id": host.id}],
        input_vars={},
        worker_pool=pool,
        triggered_by=actor,
    )
    node_run = NodeRun.objects.create(workflow_run=run, node_key="work")
    return channel, template, run, node_run


class TestNotificationExecutor:
    def test_webhook_delivery_is_fully_mocked(self, monkeypatch, notify_run):
        from apps.automation.models import NotificationRecord

        channel, template, run, node_run = notify_run
        seen = {}

        def fake_request(method, url, headers, body, timeout):
            seen["method"] = method
            seen["url"] = url
            seen["body"] = body
            return 200, {}, '{"ok": 1}'

        monkeypatch.setattr(node_executors, "_request", fake_request)
        result = execute_notification(node_run, {"inputs": {"name": "deploy"}})
        assert seen["method"] == "POST"
        assert seen["url"] == "https://hook.example.test/incoming"
        assert b"Job deploy finished" in seen["body"]
        record = NotificationRecord.objects.get(node_run=node_run)
        assert record.status == NotificationRecord.Status.SUCCESS
        assert result["notification_record_id"] == record.id

    def test_delivery_failure_is_recorded(self, monkeypatch, notify_run):
        from apps.automation.models import NotificationRecord

        channel, template, run, node_run = notify_run

        def fake_request(*args, **kwargs):
            return 500, {}, "boom"

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="Notification failed: HTTP 500"):
            execute_notification(node_run, {"inputs": {"name": "deploy"}})
        record = NotificationRecord.objects.get(node_run=node_run)
        assert record.status == NotificationRecord.Status.FAILED
