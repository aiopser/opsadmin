"""T13 execution entrypoint contracts.

快捷命令、工作流、克隆（重试/重跑）必须进入同一运行创建服务并产生同一种
可查询运行记录；取消统一走 settle_canceled_work；API/Jenkins/通知执行器
的外呼全部 mock，覆盖超时、出站目标校验和凭据脱敏，不调用真实服务。
"""

from copy import deepcopy
import json

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
    execute_api,
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
        internal_ip="10.0.0.99",
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
    template.status = WorkflowTemplate.Status.PUBLISHED
    template.save(update_fields=["status"])
    return version


class TestUnifiedEntrypoints:
    def test_clone_preserves_targets_after_cmdb_connection_changes(
        self, actor, host, pool
    ):
        version = published_workflow_version()
        original = create_workflow_run(
            workflow_version=version,
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        expected = deepcopy(original.target_snapshot)
        host.internal_ip = "192.0.2.200"
        host.connection_port = 2222
        host.region = "changed-region"
        host.save()
        cloned = clone_workflow_run(original, actor)
        assert cloned.target_snapshot == expected
        original.refresh_from_db()
        assert original.target_snapshot == expected
        assert cloned.execution_settings == original.execution_settings

    def test_clone_rejects_original_credential_disabled_after_host_rebinding(
        self, actor, host, pool
    ):
        from apps.cmdb.models import CredentialRef
        from rest_framework.exceptions import ValidationError

        credential = CredentialRef.objects.create(
            name="original", type="password", scope="global"
        )
        host.credential_ref = credential
        host.save()
        original = create_workflow_run(
            workflow_version=published_workflow_version(),
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        host.credential_ref = None
        host.save()
        credential.is_active = False
        credential.save()
        with pytest.raises(ValidationError, match="Credential"):
            clone_workflow_run(original, actor)
        assert WorkflowRun.objects.count() == 1

    def test_clone_reauthorizes_current_asset_status(self, actor, host, pool):
        from rest_framework.exceptions import ValidationError

        original = create_workflow_run(
            workflow_version=published_workflow_version(),
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        host.status = AssetHost.HostStatus.INACTIVE
        host.save()
        with pytest.raises(ValidationError, match="Inactive target"):
            clone_workflow_run(original, actor)
        assert WorkflowRun.objects.count() == 1

    def test_clone_reauthorizes_current_actor(self, actor, host, pool, user):
        from rest_framework.exceptions import PermissionDenied

        original = create_workflow_run(
            workflow_version=published_workflow_version(),
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        with pytest.raises(PermissionDenied):
            clone_workflow_run(original, user)
        assert WorkflowRun.objects.count() == 1

    def test_new_execution_resolves_current_assets(self, actor, host, pool):
        version = published_workflow_version()
        original = create_workflow_run(
            workflow_version=version,
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        host.internal_ip = "192.0.2.201"
        host.save()
        current = create_workflow_run(
            workflow_version=version,
            target_hosts=[host],
            input_vars={},
            worker_pool=pool,
            triggered_by=actor,
        )
        assert current.target_snapshot[0]["address"] == host.internal_ip
        assert original.target_snapshot[0]["address"] != host.internal_ip

    def test_invalid_schedule_does_not_block_the_next_due_schedule(
        self, actor, host, pool, monkeypatch
    ):
        from datetime import timedelta
        from django.utils import timezone
        from apps.jobs.models import ScheduledJob
        from apps.jobs.tasks import execute_scheduled_job

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
        from apps.jobs.test_schedule_policy import fire

        for schedule in (invalid, valid):
            from apps.jobs.schedule_sync import upsert_periodic_task

            upsert_periodic_task(schedule)
            fire(schedule)
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

    def test_execute_api_persists_redacted_console_output(self, monkeypatch, api_run):
        _, _, node_run = api_run
        node_run.status = NodeRun.Status.RUNNING
        node_run.attempt_count = 1
        node_run.celery_task_id = "task-api-console"
        node_run.save(
            update_fields=["status", "attempt_count", "celery_task_id", "updated_at"]
        )

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            return (200, {}, '{"status": "ok", "password": "topsecret"}')

        monkeypatch.setattr(node_executors, "_request", fake_request)
        execute_api(node_run, {})
        node_run.refresh_from_db()
        assert node_run.console_output.startswith(
            "$ GET https://api.example.test/status"
        )
        assert "HTTP 200" in node_run.console_output
        assert "topsecret" not in node_run.console_output
        assert "[REDACTED]" in node_run.console_output

    def test_execute_api_failure_persists_console_output(self, monkeypatch, api_run):
        _, _, node_run = api_run
        node_run.status = NodeRun.Status.RUNNING
        node_run.attempt_count = 1
        node_run.celery_task_id = "task-api-failed"
        node_run.save(
            update_fields=["status", "attempt_count", "celery_task_id", "updated_at"]
        )

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            return (500, {}, "boom")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="Unexpected HTTP status: 500"):
            execute_api(node_run, {})
        node_run.refresh_from_db()
        assert "$ GET https://api.example.test/status" in node_run.console_output
        assert "HTTP 500" in node_run.console_output
        assert "boom" in node_run.console_output
        assert "ERROR: Unexpected HTTP status: 500" in node_run.console_output

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
        NodeRun.objects.filter(pk=node_run.pk).update(status=NodeRun.Status.RUNNING)
        node_run.refresh_from_db()
        calls = []

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            calls.append((method, url))
            if "parameterDefinitions" in url:
                return 200, {}, '{"property": [{"parameterDefinitions": []}]}'
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
        node_run.refresh_from_db()
        assert "HTTP 201" in node_run.console_output
        assert "Queued Jenkins job deploy" in node_run.console_output

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

    def test_input_mapping_supplies_build_parameters(self, monkeypatch, jenkins_run):
        from apps.automation.models import JenkinsBuild

        server, job, run, node_run = jenkins_run
        trigger_urls = []

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return (
                    200,
                    {},
                    '{"property": [{"parameterDefinitions": [{"name": "backend_branch"}, {"name": "game_action"}]}]}',
                )
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if "/buildWithParameters" in url:
                trigger_urls.append(url)
                return 201, {"Location": "https://ci.example.test/queue/item/12/"}, ""
            if "/queue/item/12/" in url:
                return (
                    200,
                    {},
                    '{"executable": {"url": "https://ci.example.test/job/deploy/5/", "number": 5}}',
                )
            if "logText/progressiveText" in url:
                return 200, {"X-Text-Size": "0"}, ""
            if "/job/deploy/5/" in url:
                return (
                    200,
                    {},
                    '{"building": false, "result": "SUCCESS", "number": 5}',
                )
            raise AssertionError(f"unexpected jenkins call: {method} {url}")

        # 流程设计器的参数映射保存于图节点 inputMapping
        workflow_run = node_run.workflow_run
        workflow_run.graph_snapshot["nodes"][1]["inputMapping"] = {
            "backend_branch": "dev",
            "game_action": "stop",
        }
        workflow_run.save(update_fields=["graph_snapshot"])
        NodeRun.objects.filter(pk=node_run.pk).update(status=NodeRun.Status.RUNNING)
        node_run.refresh_from_db()

        monkeypatch.setattr(node_executors, "_request", fake_request)
        execute_jenkins(node_run, {})
        record = JenkinsBuild.objects.get(node_run=node_run)
        assert record.status == JenkinsBuild.Status.SUCCESS
        assert record.parameters == {"backend_branch": "dev", "game_action": "stop"}
        assert len(trigger_urls) == 1
        assert "backend_branch=dev" in trigger_urls[0]
        assert "game_action=stop" in trigger_urls[0]
        node_run.refresh_from_db()
        assert "backend_branch=dev" in node_run.console_output

    def test_build_failure_writes_jenkins_log_to_console(
        self, monkeypatch, jenkins_run
    ):
        from apps.automation.models import JenkinsBuild

        server, job, run, node_run = jenkins_run
        NodeRun.objects.filter(pk=node_run.pk).update(status=NodeRun.Status.RUNNING)
        node_run.refresh_from_db()

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return 200, {}, '{"property": [{"parameterDefinitions": []}]}'
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if url.endswith("build"):
                return 201, {"Location": "https://ci.example.test/queue/item/13/"}, ""
            if "/queue/item/13/" in url:
                return (
                    200,
                    {},
                    '{"executable": {"url": "https://ci.example.test/job/deploy/6/", "number": 6}}',
                )
            if "logText/progressiveText" in url:
                return (
                    200,
                    {"X-Text-Size": "0"},
                    "ERROR: step deploy failed\r\nFinished: FAILURE",
                )
            if "/job/deploy/6/" in url:
                return (
                    200,
                    {},
                    '{"building": false, "result": "FAILURE", "number": 6}',
                )
            raise AssertionError(f"unexpected jenkins call: {method} {url}")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="finished with FAILURE"):
            execute_jenkins(node_run, {})
        node_run.refresh_from_db()
        assert "ERROR: step deploy failed" in node_run.console_output
        assert "Finished: FAILURE" in node_run.console_output
        assert "ERROR: Jenkins build finished with FAILURE" in node_run.console_output

    def test_parameterless_trigger_sends_form_content_type(
        self, monkeypatch, jenkins_run
    ):
        server, job, run, node_run = jenkins_run
        seen = {}

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return 200, {}, '{"property": [{"parameterDefinitions": []}]}'
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if url.endswith("/build"):
                seen["headers"] = headers
                return 201, {"Location": "https://ci.example.test/queue/item/9/"}, ""
            raise AssertionError(f"unexpected jenkins call: {method} {url}")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        queue_url = node_executors.trigger_jenkins_job(server, "deploy")
        assert queue_url.endswith("/queue/item/9/")
        assert seen["headers"]["Content-Type"] == "application/x-www-form-urlencoded"

    def test_trigger_tolerates_parameter_probe_failure(self, monkeypatch, jenkins_run):
        server, job, run, node_run = jenkins_run
        seen = {}

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return 403, {}, ""
            if url.endswith("crumbIssuer/api/json"):
                return 404, {}, ""
            if url.endswith("/build"):
                seen["headers"] = headers
                return 201, {"Location": "https://ci.example.test/queue/item/10/"}, ""
            raise AssertionError(f"unexpected jenkins call: {method} {url}")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        queue_url = node_executors.trigger_jenkins_job(server, "deploy")
        assert queue_url.endswith("/queue/item/10/")
        assert seen["headers"]["Content-Type"] == "application/x-www-form-urlencoded"

    def test_job_name_is_url_encoded_for_non_ascii(self, monkeypatch, jenkins_run):
        server, job, run, node_run = jenkins_run
        seen = []

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            seen.append(url)
            return 200, {}, '{"property": [{"parameterDefinitions": []}]}'

        monkeypatch.setattr(node_executors, "_request", fake_request)
        definitions = node_executors.fetch_jenkins_job_parameter_definitions(
            server, "游戏后台管理"
        )
        assert definitions == []
        assert len(seen) == 1
        # 中文 job 名必须被 percent-encode，否则 http 客户端无法发送请求行
        assert (
            "/job/%E6%B8%B8%E6%88%8F%E5%90%8E%E5%8F%B0%E7%AE%A1%E7%90%86/api/json"
            in seen[0]
        )

    def test_nested_job_endpoint_keeps_folder_segments(self):
        endpoint = node_executors._jenkins_job_endpoint("team/游戏构建")
        assert endpoint == "job/team/job/%E6%B8%B8%E6%88%8F%E6%9E%84%E5%BB%BA"

    def test_trigger_reports_required_parameters_before_triggering(
        self, monkeypatch, jenkins_run
    ):
        server, job, run, node_run = jenkins_run

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return (
                    200,
                    {},
                    '{"property": [{"parameterDefinitions": [{"name": "ENV"}, {"name": "VERSION"}]}]}',
                )
            raise AssertionError("should not trigger a build")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="ENV"):
            node_executors.trigger_jenkins_job(server, "deploy")

    def test_trigger_rejects_parameters_for_parameterless_job(
        self, monkeypatch, jenkins_run
    ):
        server, job, run, node_run = jenkins_run

        def fake_request(method, url, headers, body, timeout, verify_ssl):
            if "parameterDefinitions" in url:
                return 200, {}, '{"property": [{"parameterDefinitions": []}]}'
            raise AssertionError("should not trigger a build")

        monkeypatch.setattr(node_executors, "_request", fake_request)
        with pytest.raises(NodeExecutionError, match="未定义构建参数"):
            node_executors.trigger_jenkins_job(server, "deploy", {"ENV": "prod"})


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
    def test_template_render_failure_is_visible_in_send_records(self, notify_run):
        from apps.automation.models import NotificationRecord

        _, template, _, node_run = notify_run
        template.subject_template = "{{ missing_title }}"
        template.save(update_fields=["subject_template"])

        with pytest.raises(Exception, match="missing_title"):
            node_executors.send_notification(
                template, {"inputs": {"name": "test"}}, node_run=node_run
            )

        record = NotificationRecord.objects.get(node_run=node_run)
        assert record.status == NotificationRecord.Status.FAILED
        assert "missing_title" in record.failure_reason

    def test_trial_send_renders_failure_alert_template_variables(
        self, monkeypatch, notify_run, actor, pool
    ):
        from apps.automation.models import NotificationRecord
        from apps.jobs.application.runs import create_trial_run
        from apps.jobs.workflow_engine import runtime_context
        from common.workflow.node_types import NodeType

        channel, template, _, _ = notify_run
        channel.channel_type = NotificationChannel.ChannelType.DINGTALK
        channel.save(update_fields=["channel_type"])
        pool.is_default = True
        pool.save(update_fields=["is_default"])
        template.subject_template = "{{ title }}"
        template.body_template = "{{ run.name }}：{{ run.failureReason }}"
        template.save(update_fields=["subject_template", "body_template"])
        trial = create_trial_run(
            node_type=NodeType.NOTIFY,
            resource_id=template.pk,
            node_name=f"Notification test: {template.name}",
            triggered_by=actor,
        )
        node_run = NodeRun.objects.create(workflow_run=trial, node_key="trial")
        sent = {}

        def fake_request(method, url, headers, body, timeout):
            sent["payload"] = json.loads(body)
            return 200, {}, '{"errcode": 0}'

        monkeypatch.setattr(node_executors, "_request", fake_request)
        node_executors.execute_notification(node_run, runtime_context(trial, {}))
        assert "通知模板测试" in sent["payload"]["text"]["content"]
        assert NotificationRecord.objects.get(node_run=node_run).subject == "通知模板测试"

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

    def test_webhook_custom_payload_renders_message(self, monkeypatch, notify_run):
        channel, template, run, node_run = notify_run
        channel.config = {
            "payload": {"text": "{{ message }}", "title": "{{ subject }}"}
        }
        channel.save(update_fields=["config"])
        sent = {}

        def fake_request(method, url, headers, body, timeout):
            sent["payload"] = json.loads(body)
            return 204, {}, ""

        monkeypatch.setattr(node_executors, "_request", fake_request)
        node_executors.send_notification(
            template, {"inputs": {"name": "deploy"}}, node_run=node_run
        )
        assert sent["payload"] == {
            "text": "Job deploy finished",
            "title": "Job finished",
        }

    @pytest.mark.parametrize(
        ("channel_type", "response", "expected_payload"),
        [
            (
                "wecom",
                '{"errcode": 0}',
                {"msgtype": "text", "text": {"content": "Job deploy finished"}},
            ),
            (
                "dingtalk",
                '{"errcode": 0}',
                {"msgtype": "text", "text": {"content": "Job deploy finished"}},
            ),
            (
                "feishu",
                '{"code": 0}',
                {"msg_type": "text", "content": {"text": "Job deploy finished"}},
            ),
        ],
    )
    def test_provider_payload_and_acknowledgement(
        self, monkeypatch, notify_run, channel_type, response, expected_payload
    ):
        channel, template, run, node_run = notify_run
        channel.channel_type = channel_type
        channel.save(update_fields=["channel_type"])
        sent = {}

        def fake_request(method, url, headers, body, timeout):
            sent["payload"] = json.loads(body)
            return 200, {}, response

        monkeypatch.setattr(node_executors, "_request", fake_request)
        node_executors.send_notification(
            template, {"inputs": {"name": "deploy"}}, node_run=node_run
        )
        assert sent["payload"] == expected_payload

    def test_provider_rejection_is_not_marked_success(self, monkeypatch, notify_run):
        from apps.automation.models import NotificationRecord

        channel, template, run, node_run = notify_run
        channel.channel_type = NotificationChannel.ChannelType.DINGTALK
        channel.save(update_fields=["channel_type"])
        monkeypatch.setattr(
            node_executors, "_request", lambda *args: (200, {}, '{"errcode": 310000}')
        )

        with pytest.raises(NodeExecutionError, match="code 310000"):
            node_executors.send_notification(
                template, {"inputs": {"name": "deploy"}}, node_run=node_run
            )
        assert (
            NotificationRecord.objects.get(node_run=node_run).status
            == NotificationRecord.Status.FAILED
        )
