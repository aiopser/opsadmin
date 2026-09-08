from common.workflow.node_types import NodeType
from uuid import uuid4
import json
from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool
from apps.audit_center.models import DomainAuditEvent
from apps.jobs.models import (
    HostRunResult,
    JobEventLog,
    NodeRun,
    ScheduledJob,
    WorkflowRun,
)
from apps.jobs.serializers import WorkflowRunCreateSerializer
from apps.jobs.events import append_run_event, sanitize_runner_event
from apps.ops.contracts import AnsibleRunnerUnavailable, RunnerResult
from apps.ops.workflow.events import normalize_runner_event
from apps.permission.models import Permission, Role
from apps.permission.services import CasbinEnforcerService, sync_casbin_rules


class VersionedAnsibleResourceTests(SimpleTestCase):
    @patch(
        "apps.jobs.execution.plan_builder.resolve_workflow_inputs",
        return_value={"execution_source": "quick_command"},
    )
    def test_quick_linux_command_uses_adhoc_raw(self, _resolve_inputs):
        from apps.jobs.execution.plan_builder import _quick_command_adhoc_spec

        spec = SimpleNamespace(
            command_type=CommandVersion.CommandType.LINUX_SHELL,
        )

        result = _quick_command_adhoc_spec(
            SimpleNamespace(),
            spec,
            {"command_content": "printf '%s\\n' hello"},
        )

        self.assertEqual(
            result,
            ("raw", "/bin/bash -c 'printf '\"'\"'%s\\n'\"'\"' hello'"),
        )

    @patch(
        "apps.jobs.execution.plan_builder.resolve_workflow_inputs",
        return_value={"execution_source": "workflow"},
    )
    def test_regular_linux_command_keeps_playbook_execution(self, _resolve_inputs):
        from apps.jobs.execution.plan_builder import _quick_command_adhoc_spec

        result = _quick_command_adhoc_spec(
            SimpleNamespace(),
            SimpleNamespace(command_type=CommandVersion.CommandType.LINUX_SHELL),
            {"command_content": "ls"},
        )

        self.assertIsNone(result)

    def test_host_execution_options_apply_serial_and_rolling_batches(self):
        from apps.jobs.execution.plan_builder import _apply_host_execution_options

        serial_playbook = _apply_host_execution_options(
            [{"hosts": "all", "tasks": []}],
            {
                "strategy": "serial",
                "serial_batch": 5,
                "max_fail_percentage": 20,
            },
        )
        rolling_playbook = _apply_host_execution_options(
            [{"hosts": "all", "tasks": []}],
            {
                "strategy": "rolling",
                "serial_batch": 8,
                "max_fail_percentage": 0,
            },
        )

        self.assertEqual(serial_playbook[0]["serial"], 1)
        self.assertEqual(serial_playbook[0]["max_fail_percentage"], 20)
        self.assertEqual(rolling_playbook[0]["serial"], 8)
        self.assertNotIn("max_fail_percentage", rolling_playbook[0])

    def test_playbook_node_uses_published_version_content(self):
        from apps.jobs.execution.plan_builder import _node_playbook

        node = SimpleNamespace(
            node_type=NodeType.PLAYBOOK,
            config={},
        )
        command_spec = SimpleNamespace(
            content="- name: Versioned play\n  hosts: legacy\n  tasks: []",
            default_vars={},
        )

        playbook = _node_playbook(SimpleNamespace(), node, command_spec, {})

        self.assertEqual(playbook[0]["name"], "Versioned play")
        self.assertEqual(playbook[0]["hosts"], "all")

    def test_module_node_uses_version_module_and_default_arguments(self):
        from apps.jobs.execution.plan_builder import _node_playbook

        run = SimpleNamespace(input_vars={}, secret_input_vars_encrypted="")
        node = SimpleNamespace(
            node_type=NodeType.MODULE,
            config={},
        )
        command_spec = SimpleNamespace(
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content="ansible.builtin.service",
            default_vars={"module_args": {"name": "nginx", "state": "restarted"}},
        )
        extra_vars = {}

        _node_playbook(run, node, command_spec, extra_vars)

        self.assertEqual(extra_vars["module_name"], "ansible.builtin.service")
        self.assertEqual(extra_vars["module_args"]["state"], "restarted")

    def test_published_playbook_ignores_stale_inline_node_content(self):
        from apps.jobs.execution.plan_builder import _node_playbook

        node = SimpleNamespace(
            node_type=NodeType.PLAYBOOK,
            command_version=SimpleNamespace(id=1),
            config={"content": "- name: Stale inline play\n  hosts: all\n  tasks: []"},
        )
        command_spec = SimpleNamespace(
            content="- name: Published play\n  hosts: legacy\n  tasks: []",
            default_vars={},
            become_enabled=True,
        )

        playbook = _node_playbook(SimpleNamespace(), node, command_spec, {})

        self.assertEqual(playbook[0]["name"], "Published play")
        self.assertEqual(playbook[0]["hosts"], "all")
        self.assertTrue(playbook[0]["become"])

    @patch("apps.jobs.workflow_engine.resolve_workflow_inputs", return_value={})
    @patch(
        "apps.jobs.execution.plan_builder.resolve_workflow_inputs",
        return_value={"command_content": "runtime override"},
    )
    def test_published_command_body_cannot_be_overridden_by_run_inputs(
        self, _resolve, _resolve_context
    ):
        from apps.jobs.execution.plan_builder import _merge_node_vars

        version = SimpleNamespace(
            content="echo published",
            default_vars={"command_content": "default override"},
        )
        node = SimpleNamespace(command_version=version, input_mapping={})
        run = SimpleNamespace(
            node_runs=SimpleNamespace(all=lambda: []),
            graph_snapshot={},
            execution_kind="workflow",
            workflow_version=None,
            id=1,
            triggered_by_id=None,
            trigger_type="manual",
        )

        values = _merge_node_vars(run, node)

        self.assertEqual(values["command_content"], "echo published")

    @patch("apps.jobs.workflow_engine.resolve_workflow_inputs", return_value={})
    @patch(
        "apps.jobs.execution.plan_builder.resolve_workflow_inputs",
        return_value={"command_content": "echo real"},
    )
    def test_quick_command_workflow_keeps_runtime_command_body(
        self, _resolve, _resolve_context
    ):
        from apps.jobs.execution.plan_builder import _merge_node_vars

        version = SimpleNamespace(content="{{ command_content }}", default_vars={})
        node = SimpleNamespace(command_version=version, input_mapping={})
        run = SimpleNamespace(
            node_runs=SimpleNamespace(all=lambda: []),
            graph_snapshot={},
            execution_kind="quick_command",
            workflow_version=SimpleNamespace(
                workflow=SimpleNamespace(code="__quick_linux_shell"),
                global_vars={},
            ),
            id=1,
            triggered_by_id=None,
            trigger_type="manual",
        )

        values = _merge_node_vars(run, node)

        self.assertEqual(values["command_content"], "echo real")

    def test_version_timeout_participates_in_effective_timeout(self):
        from apps.jobs.execution.plan_builder import _effective_ansible_timeout

        timeout = _effective_ansible_timeout(
            SimpleNamespace(timeout_seconds=300),
            SimpleNamespace(timeout_seconds=120),
            SimpleNamespace(timeout_seconds=45),
        )

        self.assertEqual(timeout, 45)

    def test_version_argument_schema_validates_required_values_and_types(self):
        from apps.jobs.execution.plan_builder import _validate_version_arguments

        spec = SimpleNamespace(
            argument_schema={
                "properties": {
                    "service": {"type": "string"},
                    "replicas": {"type": "integer"},
                },
                "required": ["service"],
            }
        )

        _validate_version_arguments(spec, {"service": "api", "replicas": 2})
        with self.assertRaisesRegex(ValueError, "service"):
            _validate_version_arguments(spec, {"replicas": 2})
        with self.assertRaisesRegex(ValueError, "replicas"):
            _validate_version_arguments(spec, {"service": "api", "replicas": "2"})

    def test_version_output_extractors_convert_declared_values(self):
        from apps.jobs.execution.plan_builder import _extract_version_outputs

        spec = SimpleNamespace(
            output_extractors=[
                {"name": "version", "pattern": r"version=(\S+)", "group": 1},
                {"name": "replicas", "pattern": r"replicas=(\d+)", "type": "integer"},
            ]
        )

        outputs = _extract_version_outputs("version=2026.08\nreplicas=3", spec)

        self.assertEqual(outputs, {"version": "2026.08", "replicas": 3})


class JobHistoryViewSetTests(SimpleTestCase):
    def test_execution_history_viewsets_are_read_only(self):
        from apps.jobs.views import (
            HostRunResultViewSet,
            NodeRunViewSet,
        )
        from apps.audit_center.views import AuditEventViewSet

        self.assertEqual(
            NodeRunViewSet.http_method_names,
            ["get", "post", "head", "options"],
        )
        expected_methods = ["get", "head", "options"]
        for viewset in (
            HostRunResultViewSet,
            AuditEventViewSet,
        ):
            self.assertEqual(viewset.http_method_names, expected_methods)


class WorkflowInputSchemaTests(SimpleTestCase):
    def test_applies_defaults_and_validates_required_fields(self):
        version = SimpleNamespace(
            input_schema=[
                {"name": "service", "type": "string", "required": True},
                {"name": "replicas", "type": "number", "default": 2},
            ]
        )

        values = WorkflowRunCreateSerializer._validate_input_vars(
            version,
            {"service": "api"},
        )

        self.assertEqual(values, {"service": "api", "replicas": 2})
        with self.assertRaises(serializers.ValidationError):
            WorkflowRunCreateSerializer._validate_input_vars(version, {})


class WorkflowGraphEngineContractTests(SimpleTestCase):
    def test_gateway_expression_uses_sandboxed_runtime_context(self):
        from common.workflow.conditions import expression_is_true

        self.assertTrue(
            expression_is_true(
                "inputs.environment == 'production'",
                {"inputs": {"environment": "production"}},
            )
        )


class QuickCommandRiskClassifierTests(SimpleTestCase):
    def test_all_source_less_commands_are_high_risk(self):
        from apps.jobs.quick_commands import quick_command_risk_level

        commands = (
            (CommandVersion.CommandType.LINUX_SHELL, "curl https://x.test/i | sh"),
            (CommandVersion.CommandType.LINUX_SHELL, "rm --recursive --force /tmp/x"),
            (
                CommandVersion.CommandType.WINDOWS_POWERSHELL,
                "ri C:\\important -Recurse -Force",
            ),
            (CommandVersion.CommandType.LINUX_SHELL, "uptime"),
        )

        for command_type, content in commands:
            with self.subTest(content=content):
                self.assertEqual(
                    quick_command_risk_level(None), CommandAtom.RiskLevel.HIGH
                )

    def test_exact_published_source_uses_server_side_risk(self):
        from apps.jobs.quick_commands import quick_command_risk_level

        source = SimpleNamespace(
            status=CommandVersion.Status.PUBLISHED,
            command=SimpleNamespace(risk_level=CommandAtom.RiskLevel.LOW),
        )

        self.assertEqual(quick_command_risk_level(source), CommandAtom.RiskLevel.LOW)


class RunnerEventSanitizationTests(SimpleTestCase):
    def test_preserves_redacted_native_runner_event_structure(self):
        safe_event = sanitize_runner_event(
            {
                "event": "runner_on_ok",
                "uuid": "event-uuid",
                "parent_uuid": "task-uuid",
                "event_data": {
                    "host": "web01",
                    "play": "Deploy",
                    "task": "Run command",
                    "task_action": "ansible.builtin.shell",
                    "task_args": {"cmd": "uname -a", "password": "hunter2"},
                    "res": {"stdout": "Linux web01", "rc": 0},
                },
            }
        )

        native_event = safe_event["payload"]["runner_event"]
        self.assertEqual(native_event["uuid"], "event-uuid")
        self.assertEqual(native_event["parent_uuid"], "task-uuid")
        self.assertEqual(native_event["event_data"]["task"], "Run command")
        self.assertEqual(
            native_event["event_data"]["task_args"]["password"],
            "[REDACTED]",
        )
        self.assertEqual(native_event["event_data"]["res"]["stdout"], "Linux web01")

    def test_textual_credentials_are_redacted_for_key_variants_bearer_and_uris(self):
        cases = {
            "ansible_password=hunter2": "ansible_password=[REDACTED]",
            "ansible-password=hunter2": "ansible-password=[REDACTED]",
            "Authorization: Bearer token": "Authorization: [REDACTED]",
            "password: value": "password: [REDACTED]",
            "ssh://deploy:hunter2@example.test/opt/app": (
                "ssh://[REDACTED]@example.test/opt/app"
            ),
        }

        for value, expected in cases.items():
            with self.subTest(value=value):
                safe_event = sanitize_runner_event(
                    {
                        "event": "runner_on_ok",
                        "event_data": {"host": "web01", "res": {"stdout": value}},
                    }
                )

                self.assertEqual(safe_event["result"]["stdout"], expected)
                self.assertNotIn("hunter2", safe_event["result"]["stdout"])
                self.assertNotIn("token", safe_event["result"]["stdout"])
                self.assertNotIn("value", safe_event["result"]["stdout"])

    def test_json_quoted_credential_values_are_redacted_and_remain_quoted(self):
        safe_event = sanitize_runner_event(
            {
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "res": {
                        "stdout": (
                            '{"password": "hunter2", '
                            '"nested_token": "token-value", "safe": "visible"}'
                        )
                    },
                },
            }
        )

        self.assertEqual(
            safe_event["result"]["stdout"],
            (
                '{"password": "[REDACTED]", '
                '"nested_token": "[REDACTED]", "safe": "visible"}'
            ),
        )

    def test_authorization_headers_redact_basic_credentials_and_all_schemes(self):
        safe_event = sanitize_runner_event(
            {
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "res": {
                        "stdout": (
                            "Authorization: Basic dXNlcjpodW50ZXIy\n"
                            "Authorization: CustomScheme opaque-token"
                        )
                    },
                },
            }
        )

        self.assertEqual(
            safe_event["result"]["stdout"],
            "Authorization: [REDACTED]\nAuthorization: [REDACTED]",
        )
        self.assertNotIn("Basic", safe_event["result"]["stdout"])
        self.assertNotIn("dXNlcjpodW50ZXIy", safe_event["result"]["stdout"])
        self.assertNotIn("CustomScheme", safe_event["result"]["stdout"])
        self.assertNotIn("opaque-token", safe_event["result"]["stdout"])

    def test_no_log_payload_contains_only_event_host_and_redacted_marker(self):
        safe_event = sanitize_runner_event(
            {
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "host_id": 42,
                    "ip": "10.0.0.11",
                    "task": "secret task",
                    "no_log": True,
                    "res": {"stdout": "hunter2"},
                },
            }
        )

        self.assertEqual(
            safe_event["payload"],
            {
                "event": "runner_on_ok",
                "event_data": {"host": "web01", "redacted": True},
            },
        )

    def test_workflow_run_viewset_allows_only_reads_and_commands(self):
        from apps.jobs.views import WorkflowRunViewSet

        self.assertEqual(
            WorkflowRunViewSet.http_method_names,
            ["get", "post", "head", "options"],
        )

    def test_execution_history_permissions_exclude_write_operations(self):
        from apps.permission.seed_data import SYSTEM_PERMISSIONS

        permission_codes = {definition["code"] for definition in SYSTEM_PERMISSIONS}
        for resource in ("jobs.workflow_run",):
            self.assertNotIn(f"{resource}.update", permission_codes)
            self.assertNotIn(f"{resource}.delete", permission_codes)

        for resource in (
            "jobs.node_run",
            "jobs.host_result",
            "jobs.event",
            "audit.event",
        ):
            self.assertNotIn(f"{resource}.create", permission_codes)
            self.assertNotIn(f"{resource}.update", permission_codes)
            self.assertNotIn(f"{resource}.delete", permission_codes)


class HostRunResultModelTests(SimpleTestCase):
    def test_host_key_uses_id_or_hostname(self):
        self.assertEqual(HostRunResult.host_key_for(42, "web01"), "id:42")
        self.assertEqual(HostRunResult.host_key_for(None, "web01"), "name:web01")
        self.assertNotEqual(
            HostRunResult.host_key_for(None, "web01"),
            HostRunResult.host_key_for(None, "web02"),
        )

    def test_host_result_uniqueness_is_portable(self):
        constraints = {
            constraint.name: constraint
            for constraint in HostRunResult._meta.constraints
        }

        self.assertEqual(set(constraints), {"jobs_unique_node_host_key"})
        constraint = constraints["jobs_unique_node_host_key"]
        self.assertEqual(tuple(constraint.fields), ("node_run", "host_key"))
        self.assertIsNone(constraint.condition)


class WorkflowCancellationTests(SimpleTestCase):
    def test_canceled_workflow_run_must_not_continue(self):
        from apps.jobs.application.cancel import should_stop_workflow_run

        run = WorkflowRun(status=WorkflowRun.Status.CANCELED)

        self.assertTrue(should_stop_workflow_run(run))


class RunnerFailureFallbackTests(SimpleTestCase):
    def test_failed_result_fallback_updates_callback_host_without_duplicate(self):
        from apps.jobs.execution.registry import _materialize_failed_target_results

        results = {
            "id:1": SimpleNamespace(
                host_key="id:1",
                hostname="web01",
                status=HostRunResult.Status.OK,
            )
        }

        class FakeManager:
            def update_or_create(self, *, node_run, host_key, defaults):
                result = results.get(host_key)
                created = result is None
                if created:
                    result = SimpleNamespace(host_key=host_key)
                    results[host_key] = result
                for field, value in defaults.items():
                    setattr(result, field, value)
                return result, created

        class FakeHostRunResult:
            class Status:
                FAILED = HostRunResult.Status.FAILED

            objects = FakeManager()

            @staticmethod
            def host_key_for(host_id, hostname):
                return f"id:{host_id}" if host_id is not None else f"name:{hostname}"

        with patch("apps.jobs.execution.registry.HostRunResult", FakeHostRunResult):
            _materialize_failed_target_results(
                SimpleNamespace(),
                [
                    {"host_id": 1, "hostname": "web01", "ip": "10.0.0.11"},
                    {"host_id": 2, "hostname": "web02", "ip": "10.0.0.12"},
                ],
                "runner crashed",
                1,
            )

        self.assertEqual(set(results), {"id:1", "id:2"})
        self.assertEqual(results["id:1"].status, HostRunResult.Status.FAILED)
        self.assertEqual(results["id:1"].stderr, "runner crashed")
        self.assertEqual(results["id:2"].status, HostRunResult.Status.FAILED)


from apps.jobs.application.runs import create_workflow_run
def execute_graph_fixture(run_id):
    """Drive real graph/claim tasks synchronously with broker transport isolated."""
    from apps.jobs.tasks import run_workflow, execute_node
    from apps.jobs.workflow_engine import TERMINAL_NODE_STATUSES
    with patch("apps.jobs.tasks.enqueue_node_run"), patch("apps.jobs.tasks.enqueue_workflow_run"):
        for _ in range(20):
            result = run_workflow(run_id)
            for node_id in result["queuedNodes"]:
                node = NodeRun.objects.get(pk=node_id)
                execute_node(node_id, node.attempt_count)
            run = WorkflowRun.objects.get(pk=run_id)
            if run.status in {"success", "failed", "canceled", "timeout"}:
                return run
        raise AssertionError("Graph did not terminate")


def publish_linear_fixture(version):
    """Build an explicit graph for test command nodes before publication."""
    from apps.automation.models import WorkflowEdge
    commands = list(version.nodes.order_by("order_index", "id"))
    start = WorkflowNode.objects.create(workflow_version=version, node_key="start", name="Start", node_type="start")
    end = WorkflowNode.objects.create(workflow_version=version, node_key="end", name="End", node_type="end")
    path = [start, *commands, end]
    for index, (source, target) in enumerate(zip(path, path[1:])):
        WorkflowEdge.objects.create(workflow_version=version, edge_key=f"edge-{index}", source_node=source, target_node=target)
    version.publish(None)

from apps.jobs.views import WorkflowRunViewSet


class WorkflowRunServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="job-user",
            password="123456",
            email="job-user@example.com",
            phone="13800000002",
        )
        self.worker_pool = WorkerPool.objects.create(
            code="default",
            name="Default Worker Pool",
            queue_name="ansible.default",
            is_default=True,
        )
        self.host = AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            cpu_cores=2,
            memory_mb=4096,
            system_disk_gb=40,
            data_disk_gb=200,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        self.command = CommandAtom.objects.create(
            name="Check disk",
            code="check_disk",
            category="system",
            risk_level=CommandAtom.RiskLevel.LOW,
            created_by=self.user,
            updated_by=self.user,
        )
        self.command_version = CommandVersion.objects.create(
            command=self.command,
            version=1,
            status=CommandVersion.Status.PUBLISHED,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="df -h",
            created_by=self.user,
            published_by=self.user,
        )
        self.workflow = WorkflowTemplate.objects.create(
            name="Check service",
            code="check_service",
            created_by=self.user,
            updated_by=self.user,
        )
        self.workflow_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            version=1,
            status=WorkflowVersion.Status.DRAFT,
            created_by=self.user,
            published_by=self.user,
        )
        self.node = WorkflowNode.objects.create(
            workflow_version=self.workflow_version,
            node_key="check_disk",
            name="Check disk",
            command_version=self.command_version,
            order_index=1,
        )
        publish_linear_fixture(self.workflow_version)
        self.api_role = Role.objects.create(name="job_runner")
        self.user.role.add(self.api_role)
        self.api_role.permission.add(
            Permission.objects.create(
                name="Use test pool",
                code="test.jobs.pool.detail",
                type="api",
                path="/api/v1/jobs/worker-pools/:id",
                method="GET",
            ),
            Permission.objects.create(
                name="Use test asset",
                code="test.cmdb.host.detail",
                type="api",
                path="/api/v1/cmdb/hosts/:id",
                method="GET",
            ),
            Permission.objects.create(
                name="创建工作流执行",
                code="test.jobs.workflow_run.create",
                type=Permission.PermissionType.API,
                path="/api/v1/tasks/runs",
                method="POST",
            ),
            Permission.objects.create(
                name="校验工作流执行",
                code="test.jobs.workflow_run.validate",
                type=Permission.PermissionType.API,
                path="/api/v1/tasks/runs/validate",
                method="POST",
            ),
            Permission.objects.create(
                name="取消工作流执行",
                code="test.jobs.workflow_run.cancel",
                type=Permission.PermissionType.API,
                path="/api/v1/tasks/runs/:id/cancel",
                method="POST",
            ),
            Permission.objects.create(
                name="订阅工作流执行事件",
                code="test.jobs.workflow_run.log",
                type=Permission.PermissionType.API,
                path="/api/v1/tasks/runs/:id/log",
                method="GET",
            ),
            Permission.objects.create(
                name="创建快捷命令执行",
                code="test.jobs.quick_command.create",
                type=Permission.PermissionType.API,
                path="/api/v1/jobs/quick-commands/runs",
                method="POST",
            ),
            Permission.objects.create(
                name="创建定时任务",
                code="test.jobs.scheduled_job.create",
                type=Permission.PermissionType.API,
                path="/api/v1/jobs/scheduled-jobs",
                method="POST",
            ),
        )
        sync_casbin_rules()
        CasbinEnforcerService.reload()

    def tearDown(self):
        CasbinEnforcerService.reload()
        super().tearDown()

    def create_running_node_run(self):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        return NodeRun.objects.create(
            workflow_run=run,
            workflow_node=self.node,
            command_version=self.command_version,
            status=NodeRun.Status.RUNNING,
        )

    def create_terminal_run(self):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        run.status = WorkflowRun.Status.SUCCESS
        run.save(update_fields=["status", "updated_at"])
        return run

    def test_dispatch_failure_moves_run_to_terminal_failed_state(self):
        from apps.jobs.tasks import _mark_dispatch_failed

        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        _mark_dispatch_failed(run.id, RuntimeError("planner crashed"))

        run.refresh_from_db()
        self.assertEqual(run.status, WorkflowRun.Status.FAILED)
        self.assertIn("planner crashed", run.failure_reason)
        self.assertIsNotNone(run.finished_at)
        self.assertTrue(
            JobEventLog.objects.filter(
                workflow_run=run,
                event_type="workflow_failed",
            ).exists()
        )

    def test_node_run_can_only_be_claimed_once(self):
        from apps.jobs.tasks import _claim_node_run

        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        node_run = NodeRun.objects.create(
            workflow_run=run,
            workflow_node=self.node,
            command_version=self.command_version,
            node_key=self.node.node_key,
            node_name=self.node.name,
            node_type=self.node.node_type,
            status=NodeRun.Status.QUEUED,
        )
        now = timezone.now()

        self.assertTrue(
            _claim_node_run(node_run.id, "task-1", now, node_run.attempt_count)
        )
        self.assertFalse(
            _claim_node_run(node_run.id, "task-2", now, node_run.attempt_count)
        )

        node_run.refresh_from_db()
        self.assertEqual(node_run.status, NodeRun.Status.RUNNING)
        self.assertEqual(node_run.celery_task_id, "task-1")

    def test_dispatch_failure_cancels_nodes_that_were_not_started(self):
        from apps.jobs.tasks import _mark_dispatch_failed

        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        node_run = NodeRun.objects.create(
            workflow_run=run,
            workflow_node=self.node,
            node_key=self.node.node_key,
            node_name=self.node.name,
            node_type=self.node.node_type,
            status=NodeRun.Status.QUEUED,
        )

        _mark_dispatch_failed(run.id, RuntimeError("broker unavailable"))

        node_run.refresh_from_db()
        self.assertEqual(node_run.status, NodeRun.Status.CANCELED)

    def test_attempt_terminal_status_preserves_timeout_and_cancel(self):
        from apps.jobs.tasks import _attempt_terminal_status

        self.assertEqual(
            _attempt_terminal_status(NodeRun.Status.TIMEOUT),
            "timeout",
        )
        self.assertEqual(
            _attempt_terminal_status(NodeRun.Status.CANCELED),
            "canceled",
        )

    def test_secret_workflow_inputs_are_encrypted_at_rest(self):
        from apps.jobs.input_secrets import REDACTED_VALUE, resolve_workflow_inputs

        version = WorkflowVersion.objects.create(
            workflow=self.workflow_version.workflow,
            version=2,
            input_schema=[
                {"name": "service", "type": "string"},
                {"name": "deploy_token", "type": "secret"},
            ],
        )

        publish_linear_fixture(version)
        run = create_workflow_run(
            workflow_version=version,
            target_hosts=[self.host],
            input_vars={"service": "api", "deploy_token": "top-secret-token"},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        self.assertEqual(run.input_vars["deploy_token"], REDACTED_VALUE)
        self.assertNotIn("top-secret-token", run.secret_input_vars_encrypted)
        self.assertNotIn("top-secret-token", json.dumps(run.context_vars))
        self.assertEqual(
            resolve_workflow_inputs(run)["deploy_token"],
            "top-secret-token",
        )

    def post_quick_command(self, data):
        from apps.jobs.views import QuickCommandRunViewSet

        request = APIRequestFactory().post(
            "/api/v1/jobs/quick-commands/runs",
            data,
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        return QuickCommandRunViewSet.as_view({"post": "create"})(request)

    def grant_high_risk_execution(self):
        permission, _ = Permission.objects.get_or_create(
            code="automation.command:execute_high_risk",
            defaults={
                "name": "Execute high-risk commands",
                "type": Permission.PermissionType.BUTTON,
            },
        )
        self.api_role.permission.add(permission)

    def test_quick_command_creates_unified_workflow_run(self):
        self.grant_high_risk_execution()
        response = self.post_quick_command(
            {
                "commandType": "linux_shell",
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 200)
        run = WorkflowRun.objects.get(id=response.data["data"]["id"])
        self.assertEqual(WorkflowRun.objects.count(), 1)
        self.assertEqual(run.input_vars["command_content"], "uptime")
        self.assertEqual(run.input_vars["execution_source"], "quick_command")
        self.assertEqual(run.trigger_type, WorkflowRun.TriggerType.MANUAL)
        self.assertEqual(run.run_domain, WorkflowRun.RunDomain.OPS)
        self.assertEqual(
            run.execution_kind,
            WorkflowRun.ExecutionKind.QUICK_COMMAND,
        )
        self.assertIsNone(run.input_vars["source_command_version_id"])
        self.assertEqual(run.workflow_version.workflow.code, "__quick_linux_shell")

    def test_scheduled_job_create_calculates_first_cron_run(self):
        from apps.jobs.views import ScheduledJobViewSet

        request = APIRequestFactory().post(
            "/api/v1/jobs/scheduled-jobs",
            {
                "name": "Hourly check",
                "workflow_version": self.workflow_version.id,
                "host_ids": [self.host.id],
                "cron_expression": "0 * * * *",
                "timezone": "Asia/Shanghai",
                "input_vars": {"environment": "test"},
                "host_strategy": "rolling",
                "forks": 8,
                "serial_batch": 3,
                "max_fail_percentage": 25,
                "timeout_seconds": 900,
                "queue_timeout_seconds": 45,
                "bypass_host_gateway": True,
                "enabled": True,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        before = timezone.now()

        response = ScheduledJobViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 200)
        schedule = ScheduledJob.objects.get()
        self.assertGreater(schedule.next_run_at, before)
        self.assertLessEqual(schedule.next_run_at, before + timedelta(minutes=61))
        self.assertEqual(schedule.input_vars, {"environment": "test"})
        self.assertEqual(schedule.worker_pool, self.worker_pool)
        self.assertEqual(schedule.host_strategy, "rolling")
        self.assertEqual(schedule.forks, 8)
        self.assertEqual(schedule.serial_batch, 3)
        self.assertEqual(schedule.max_fail_percentage, 25)
        self.assertEqual(schedule.timeout_seconds, 900)
        self.assertEqual(schedule.queue_timeout_seconds, 45)
        self.assertTrue(schedule.bypass_host_gateway)
        from apps.jobs.application.runs import scheduled_job_run_options

        run_options = scheduled_job_run_options(schedule)
        self.assertEqual(run_options["input_vars"]["host_strategy"], "rolling")
        self.assertEqual(run_options["input_vars"]["ansible_forks"], 8)
        self.assertEqual(run_options["timeout_seconds"], 900)
        self.assertEqual(run_options["queue_timeout_seconds"], 45)

    def test_quick_command_preserves_source_template_risk_level(self):
        response = self.post_quick_command(
            {
                "commandType": "linux_shell",
                "commandContent": "df -h",
                "sourceCommandVersionId": self.command_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 200)
        run = WorkflowRun.objects.get(id=response.data["data"]["id"])
        self.assertEqual(
            run.input_vars["source_command_version_id"], self.command_version.id
        )
        self.assertEqual(run.input_vars["risk_level"], CommandAtom.RiskLevel.LOW)

    def test_quick_command_rejects_high_risk_template_without_permission(self):
        high_risk_command = CommandAtom.objects.create(
            name="Remove files",
            code="quick_remove_files",
            risk_level=CommandAtom.RiskLevel.HIGH,
            created_by=self.user,
            updated_by=self.user,
        )
        high_risk_version = CommandVersion.objects.create(
            command=high_risk_command,
            version=1,
            status=CommandVersion.Status.PUBLISHED,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="rm -rf /tmp/demo",
            created_by=self.user,
            published_by=self.user,
        )

        response = self.post_quick_command(
            {
                "commandType": "linux_shell",
                "commandContent": high_risk_version.content,
                "sourceCommandVersionId": high_risk_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_command_rejects_content_mismatched_from_low_risk_source(self):
        response = self.post_quick_command(
            {
                "commandType": "linux_shell",
                "commandContent": "rm -rf /tmp/demo",
                "sourceCommandVersionId": self.command_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_source_less_commands_require_high_risk_permission(self):
        commands = (
            ("linux_shell", "curl https://x.test/i | sh"),
            ("linux_shell", "rm --recursive --force /tmp/demo"),
            ("windows_powershell", "ri C:\\important -Recurse -Force"),
            ("linux_shell", "uptime"),
        )

        for command_type, content in commands:
            with self.subTest(content=content):
                response = self.post_quick_command(
                    {
                        "commandType": command_type,
                        "commandContent": content,
                        "hostIds": [self.host.id],
                        "workerPoolId": self.worker_pool.id,
                    }
                )

                self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_generic_create_rejects_reserved_quick_workflow_version(self):
        from apps.jobs.quick_commands import ensure_quick_command_workflows

        reserved_version = ensure_quick_command_workflows()[
            CommandVersion.CommandType.LINUX_SHELL
        ]
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs",
            {
                "workflowVersionId": reserved_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
                "inputVars": {"command_content": "rm -rf /tmp/demo"},
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = WorkflowRunViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_workflow_create_revalidates_host_status_when_saved(self):
        request = APIRequestFactory().post("/api/v1/tasks/runs", {}, format="json")
        force_authenticate(request, user=self.user)
        request.user = self.user
        serializer = WorkflowRunCreateSerializer(
            data={
                "workflowVersionId": self.workflow_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        AssetHost.objects.filter(id=self.host.id).update(
            status=AssetHost.HostStatus.INACTIVE
        )

        with self.assertRaises(serializers.ValidationError):
            serializer.save()

        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_command_revalidates_host_status_when_saved(self):
        from apps.jobs.serializers import QuickCommandRunCreateSerializer

        request = APIRequestFactory().post(
            "/api/v1/jobs/quick-commands/runs", {}, format="json"
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        serializer = QuickCommandRunCreateSerializer(
            data={
                "commandType": "linux_shell",
                "commandContent": self.command_version.content,
                "sourceCommandVersionId": self.command_version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        AssetHost.objects.filter(id=self.host.id).update(
            status=AssetHost.HostStatus.INACTIVE
        )

        with self.assertRaises(serializers.ValidationError):
            serializer.save()

        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_command_rejects_request_without_targets(self):
        response = self.post_quick_command(
            {
                "commandType": "linux_shell",
                "commandContent": "uptime",
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_command_rejects_unknown_command_type(self):
        response = self.post_quick_command(
            {
                "commandType": "unknown",
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            }
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_command_create_permission_is_seeded(self):
        from apps.permission.seed_data import (
            SYSTEM_MENU_API_PERMISSIONS,
            SYSTEM_PERMISSIONS,
        )

        definition = next(
            item
            for item in SYSTEM_PERMISSIONS
            if item["code"] == "jobs.quick_command.create"
        )
        self.assertEqual(definition["path"], "/api/v1/jobs/quick-commands/runs")
        self.assertEqual(definition["method"], "POST")
        self.assertIn(
            "jobs.quick_command.create",
            SYSTEM_MENU_API_PERMISSIONS["jobs.quick_command:execute"],
        )

    def test_seeded_quick_command_operator_can_retrieve_selected_command_version(self):
        from apps.automation.views import CommandVersionViewSet
        from apps.permission.models import MenuButton
        from apps.permission.seed_data import seed_system_settings

        seed_system_settings(bind_superusers=False)
        execute_button = MenuButton.objects.get(code="jobs.quick_command:execute")
        self.api_role.permission.add(*execute_button.get_effective_permissions())
        sync_casbin_rules()
        CasbinEnforcerService.reload()
        request = APIRequestFactory().get(
            f"/api/v1/automation/command-versions/{self.command_version.id}"
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = CommandVersionViewSet.as_view({"get": "retrieve"})(
            request,
            pk=str(self.command_version.id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], self.command_version.id)

    def test_runner_ok_event_updates_existing_host_result(self):
        node_run = self.create_running_node_run()
        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                ({"event": "runner_on_start", "event_data": {"host": "web01"}}).get(
                    "uuid"
                )
                or uuid4().hex
            ),
            event={"event": "runner_on_start", "event_data": {"host": "web01"}},
        )
        self.assertEqual(
            HostRunResult.objects.get(node_run=node_run, hostname="web01").status,
            HostRunResult.Status.RUNNING,
        )
        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "res": {"stdout": "ok", "rc": 0},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_ok",
                "event_data": {"host": "web01", "res": {"stdout": "ok", "rc": 0}},
            },
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")

        self.assertEqual(result.status, HostRunResult.Status.OK)
        self.assertEqual(result.stdout, "ok")
        self.assertEqual(
            HostRunResult.objects.filter(node_run=node_run, hostname="web01").count(),
            1,
        )

    def test_late_start_event_does_not_overwrite_a_terminal_host_result(self):
        node_run = self.create_running_node_run()
        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "res": {"stdout": "completed", "rc": 0},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "res": {"stdout": "completed", "rc": 0},
                },
            },
        )

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                ({"event": "runner_on_start", "event_data": {"host": "web01"}}).get(
                    "uuid"
                )
                or uuid4().hex
            ),
            event={"event": "runner_on_start", "event_data": {"host": "web01"}},
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, HostRunResult.Status.OK)
        self.assertEqual(result.stdout, "completed")

    def test_runner_failed_event_marks_host_result_failed(self):
        node_run = self.create_running_node_run()

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_failed",
                        "event_data": {
                            "host": "web01",
                            "res": {"stderr": "command failed", "rc": 1},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_failed",
                "event_data": {
                    "host": "web01",
                    "res": {"stderr": "command failed", "rc": 1},
                },
            },
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, HostRunResult.Status.FAILED)
        self.assertEqual(result.stderr, "command failed")
        self.assertEqual(result.rc, 1)

    def test_runner_unreachable_event_marks_host_result_unreachable(self):
        node_run = self.create_running_node_run()

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_unreachable",
                        "event_data": {
                            "host": "web01",
                            "res": {"msg": "Host unreachable", "unreachable": True},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_unreachable",
                "event_data": {
                    "host": "web01",
                    "res": {"msg": "Host unreachable", "unreachable": True},
                },
            },
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, HostRunResult.Status.UNREACHABLE)
        self.assertEqual(result.stderr, "Host unreachable")

    def test_runner_skipped_event_marks_host_result_skipped(self):
        node_run = self.create_running_node_run()

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                ({"event": "runner_on_skipped", "event_data": {"host": "web01"}}).get(
                    "uuid"
                )
                or uuid4().hex
            ),
            event={"event": "runner_on_skipped", "event_data": {"host": "web01"}},
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, HostRunResult.Status.SKIPPED)

    def test_no_log_event_redacts_its_payload_and_host_output(self):
        node_run = self.create_running_node_run()

        log = append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "no_log": True,
                            "res": {"stdout": "do-not-store", "password": "hunter2"},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "no_log": True,
                    "res": {"stdout": "do-not-store", "password": "hunter2"},
                },
            },
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        serialized = json.dumps(
            {"payload": log.payload, "result": result.raw_event_data}
        )
        self.assertEqual(
            log.payload,
            {
                "event": "runner_on_ok",
                "event_data": {"host": "web01", "redacted": True},
            },
        )
        self.assertNotIn("do-not-store", serialized)
        self.assertNotIn("hunter2", serialized)
        self.assertEqual(result.stdout, "")

    def test_runner_event_redacts_sensitive_values_before_persistence(self):
        node_run = self.create_running_node_run()

        log = append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "res": {"stdout": "ok", "api_token": "do-not-store"},
                            "extra_vars": {"ansible_password": "hunter2"},
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "res": {"stdout": "ok", "api_token": "do-not-store"},
                    "extra_vars": {"ansible_password": "hunter2"},
                },
            },
        )

        serialized = json.dumps(log.payload)
        self.assertNotIn("do-not-store", serialized)
        self.assertNotIn("hunter2", serialized)
        self.assertNotIn("extra_vars", log.payload["event_data"])

    def test_runner_event_persists_only_safe_metadata_and_redacted_output(self):
        node_run = self.create_running_node_run()

        log = append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                (
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "task": "Run secure command",
                            "invocation": {
                                "module_args": {
                                    "_raw_params": "curl https://runner:raw-secret@example.test"
                                }
                            },
                            "res": {
                                "stdout": "password=hunter2 curl https://ops:uri-secret@example.test",
                                "rc": 0,
                            },
                        },
                    }
                ).get("uuid")
                or uuid4().hex
            ),
            event={
                "event": "runner_on_ok",
                "event_data": {
                    "host": "web01",
                    "task": "Run secure command",
                    "invocation": {
                        "module_args": {
                            "_raw_params": "curl https://runner:raw-secret@example.test"
                        }
                    },
                    "res": {
                        "stdout": "password=hunter2 curl https://ops:uri-secret@example.test",
                        "rc": 0,
                    },
                },
            },
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        serialized = json.dumps({"payload": log.payload, "raw": result.raw_event_data})
        self.assertNotIn("invocation", serialized)
        self.assertNotIn("module_args", serialized)
        self.assertNotIn("_raw_params", serialized)
        self.assertNotIn("raw-secret", serialized)
        self.assertNotIn("hunter2", serialized)
        self.assertNotIn("uri-secret", serialized)
        self.assertIn("password=[REDACTED]", result.stdout)
        self.assertIn("https://[REDACTED]@example.test", result.stdout)

    def test_runner_event_rejects_node_from_another_workflow_run(self):
        workflow_run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        other_node_run = self.create_running_node_run()

        with self.assertRaises(ValueError):
            append_run_event(
                run_id=(workflow_run).id,
                node_run_id=(other_node_run).id,
                event_key=str(
                    ({"event": "runner_on_start", "event_data": {"host": "web01"}}).get(
                        "uuid"
                    )
                    or uuid4().hex
                ),
                event={"event": "runner_on_start", "event_data": {"host": "web01"}},
            )

        self.assertEqual(
            JobEventLog.objects.filter(workflow_run=workflow_run).count(), 0
        )
        self.assertEqual(
            HostRunResult.objects.filter(node_run=other_node_run).count(), 0
        )

    def test_repeated_unresolved_host_events_update_one_host_result(self):
        node_run = self.create_running_node_run()
        event = {
            "event": "runner_on_ok",
            "event_data": {
                "host": "unresolved-web01",
                "res": {"stdout": "ok", "rc": 0},
            },
        }

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str((event).get("uuid") or uuid4().hex),
            event=event,
        )
        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str((event).get("uuid") or uuid4().hex),
            event=event,
        )

        self.assertEqual(
            HostRunResult.objects.filter(
                node_run=node_run,
                hostname="unresolved-web01",
            ).count(),
            1,
        )

    def test_different_unresolved_hostnames_create_distinct_host_results(self):
        node_run = self.create_running_node_run()

        for hostname in ("unresolved-web01", "unresolved-web02"):
            append_run_event(
                run_id=(node_run.workflow_run).id,
                node_run_id=(node_run).id,
                event_key=str(
                    (
                        {
                            "event": "runner_on_ok",
                            "event_data": {"host": hostname, "res": {"rc": 0}},
                        }
                    ).get("uuid")
                    or uuid4().hex
                ),
                event={
                    "event": "runner_on_ok",
                    "event_data": {"host": hostname, "res": {"rc": 0}},
                },
            )

        self.assertEqual(
            set(
                HostRunResult.objects.filter(node_run=node_run).values_list(
                    "host_key", flat=True
                )
            ),
            {"name:unresolved-web01", "name:unresolved-web02"},
        )

    def test_runner_canceled_event_marks_host_result_canceled(self):
        node_run = self.create_running_node_run()

        append_run_event(
            run_id=(node_run.workflow_run).id,
            node_run_id=(node_run).id,
            event_key=str(
                ({"event": "runner_on_canceled", "event_data": {"host": "web01"}}).get(
                    "uuid"
                )
                or uuid4().hex
            ),
            event={"event": "runner_on_canceled", "event_data": {"host": "web01"}},
        )

        result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, HostRunResult.Status.CANCELED)

    def test_create_workflow_run_stores_target_snapshot(self):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={"service": "nginx"},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        self.assertEqual(run.status, WorkflowRun.Status.PENDING)
        self.assertEqual(run.target_snapshot[0]["hostname"], self.host.hostname)
        self.assertEqual(run.target_snapshot[0]["address"], self.host.primary_ip)
        self.assertEqual(run.worker_pool_id, self.worker_pool.id)

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_node_preserves_confirmed_runner_cancel_and_timeout(self, executor):
        from apps.jobs.execution.registry import execute_ansible_node

        for status in ("canceled", "timeout"):
            with self.subTest(status=status):
                run = create_workflow_run(
                    workflow_version=self.workflow_version,
                    target_hosts=[self.host],
                    input_vars={},
                    worker_pool=self.worker_pool,
                    triggered_by=self.user,
                )
                node = NodeRun.objects.create(
                    workflow_run=run,
                    workflow_node=self.node,
                    node_key=self.node.node_key,
                    command_version=self.command_version,
                    status="running",
                    attempt_count=1,
                )
                executor.return_value.execute.return_value = RunnerResult(status, 1)
                result = execute_ansible_node(node.id)
                self.assertEqual(result.status, status)

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_asset_disabled_after_submission_is_not_executed(self, executor):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        AssetHost.objects.filter(pk=self.host.pk).update(status="inactive")
        result = execute_graph_fixture(run.id)
        self.assertEqual(result.status, WorkflowRun.Status.FAILED)
        executor.return_value.execute.assert_not_called()

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_workflow_persists_callback_events_without_terminal_aggregation(
        self, runner_service
    ):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        def execute(plan, event_handler, cancel_callback, **_kwargs):
            event_handler(
                normalize_runner_event(
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "invocation": {
                                "module_args": {"password": "do-not-store"},
                            },
                            "res": {
                                "stdout": "password=do-not-store",
                                "rc": 0,
                            },
                        },
                    }
                )
            )
            self.assertFalse(cancel_callback())
            return RunnerResult.from_mapping(
                {"status": "successful", "rc": 0, "stats": {"ok": {}}}
            )

        runner_service.return_value.execute.side_effect = execute

        result = execute_graph_fixture(run.id)

        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        host_result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        serialized = json.dumps(
            {
                "payloads": list(
                    JobEventLog.objects.filter(node_run=node_run).values_list(
                        "payload", flat=True
                    )
                ),
                "host_result": host_result.raw_event_data,
            }
        )
        self.assertEqual(result.status, WorkflowRun.Status.SUCCESS)
        self.assertEqual(
            HostRunResult.objects.filter(node_run=node_run, hostname="web01").count(),
            1,
        )
        self.assertEqual(host_result.status, HostRunResult.Status.OK)
        self.assertNotIn("invocation", serialized)
        self.assertNotIn("module_args", serialized)
        self.assertNotIn("do-not-store", serialized)
        self.assertNotIn("runner_result", serialized)

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_unavailable_materializes_failed_result_for_every_target(
        self, runner_service
    ):
        second_host = AssetHost.objects.create(
            hostname="web02",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host, second_host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        runner_service.return_value.execute.side_effect = AnsibleRunnerUnavailable(
            "ansible-runner unavailable"
        )

        execute_graph_fixture(run.id)

        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        host_results = HostRunResult.objects.filter(node_run=node_run)
        self.assertEqual(host_results.count(), 2)
        self.assertEqual(
            set(host_results.values_list("status", flat=True)),
            {HostRunResult.Status.FAILED},
        )
        self.assertEqual(
            set(host_results.values_list("host_key", flat=True)),
            {f"id:{self.host.id}", f"id:{second_host.id}"},
        )

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_exception_reuses_callback_result_without_duplicates(
        self, runner_service
    ):
        second_host = AssetHost.objects.create(
            hostname="web02",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host, second_host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        def execute(plan, event_handler, cancel_callback, **_kwargs):
            event_handler(
                normalize_runner_event(
                    {
                        "event": "runner_on_ok",
                        "event_data": {"host": "web01", "res": {"rc": 0}},
                    }
                )
            )
            raise RuntimeError("runner crashed")

        runner_service.return_value.execute.side_effect = execute

        execute_graph_fixture(run.id)

        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        host_results = HostRunResult.objects.filter(node_run=node_run)
        self.assertEqual(host_results.count(), 2)
        self.assertEqual(
            set(host_results.values_list("status", flat=True)),
            {HostRunResult.Status.FAILED},
        )
        self.assertEqual(
            HostRunResult.objects.filter(
                node_run=node_run,
                host_key=HostRunResult.host_key_for(self.host.id, self.host.hostname),
            ).count(),
            1,
        )

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_no_callbacks_materializes_failed_result_for_every_target(
        self, runner_service
    ):
        second_host = AssetHost.objects.create(
            hostname="web02",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host, second_host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        runner_service.return_value.execute.return_value = RunnerResult.from_mapping(
            {
                "status": "successful",
                "rc": 0,
                "stats": {},
            }
        )

        execute_graph_fixture(run.id)

        run.refresh_from_db()
        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        self.assertEqual(run.status, WorkflowRun.Status.FAILED)
        self.assertEqual(node_run.status, NodeRun.Status.FAILED)
        self.assertEqual(
            HostRunResult.objects.filter(
                node_run=node_run,
                status=HostRunResult.Status.FAILED,
            ).count(),
            2,
        )

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_cancel_callback_marks_active_node_and_host_work_canceled(
        self, runner_service
    ):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        def execute(plan, event_handler, cancel_callback, **_kwargs):
            event_handler(
                normalize_runner_event(
                    {
                        "event": "runner_on_start",
                        "event_data": {"host": "web01"},
                    }
                )
            )
            WorkflowRun.objects.filter(id=run.id).update(
                status=WorkflowRun.Status.CANCELED
            )
            self.assertTrue(cancel_callback())
            self.assertFalse(
                event_handler(
                    normalize_runner_event(
                        {
                            "event": "runner_on_ok",
                            "event_data": {
                                "host": "web01",
                                "res": {"stdout": "must-not-replace-canceled", "rc": 0},
                            },
                        }
                    )
                )
            )
            return RunnerResult.from_mapping(
                {"status": "canceled", "rc": 1, "stats": {}}
            )

        runner_service.return_value.execute.side_effect = execute

        result = execute_graph_fixture(run.id)

        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        host_result = HostRunResult.objects.get(node_run=node_run, hostname="web01")
        self.assertEqual(result.status, WorkflowRun.Status.CANCELED)
        self.assertEqual(node_run.status, NodeRun.Status.CANCELED)
        self.assertEqual(host_result.status, HostRunResult.Status.CANCELED)
        self.assertTrue(
            JobEventLog.objects.filter(
                node_run=node_run,
                event_type="node_canceled",
            ).exists()
        )

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_preclaim_cancellation_materializes_all_node_and_host_results(
        self, runner_service
    ):
        self.workflow_version = WorkflowVersion.objects.create(workflow=self.workflow, version=2)
        self.node.pk = None
        self.node.workflow_version = self.workflow_version
        self.node.save()
        second_node = WorkflowNode.objects.create(
            workflow_version=self.workflow_version,
            node_key="restart_service",
            name="Restart service",
            command_version=self.command_version,
            order_index=2,
        )
        publish_linear_fixture(self.workflow_version)
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        completed_node_run = NodeRun.objects.create(
            workflow_run=run,
            workflow_node=self.node,
            node_key=self.node.node_key,
            command_version=self.command_version,
            status=NodeRun.Status.SUCCESS,
        )
        HostRunResult.objects.create(
            node_run=completed_node_run,
            host_id=self.host.id,
            hostname=self.host.hostname,
            host_key=HostRunResult.host_key_for(self.host.id, self.host.hostname),
            ip=self.host.primary_ip,
            status=HostRunResult.Status.OK,
            stdout="completed",
        )
        WorkflowRun.objects.filter(id=run.id).update(status=WorkflowRun.Status.CANCELED)

        result = execute_graph_fixture(run.id)

        node_runs = {
            node_run.workflow_node_id: node_run
            for node_run in NodeRun.objects.filter(workflow_run=run).exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"})
        }
        self.assertEqual(result.status, WorkflowRun.Status.CANCELED)
        self.assertEqual(set(node_runs), {self.node.id, second_node.id})
        self.assertEqual(node_runs[self.node.id].status, NodeRun.Status.SUCCESS)
        self.assertEqual(node_runs[second_node.id].status, NodeRun.Status.CANCELED)
        completed_host_result = HostRunResult.objects.get(node_run=completed_node_run)
        self.assertEqual(completed_host_result.status, HostRunResult.Status.OK)
        self.assertEqual(completed_host_result.stdout, "completed")
        canceled_host_results = HostRunResult.objects.filter(
            node_run=node_runs[second_node.id],
            status=HostRunResult.Status.CANCELED,
        )
        self.assertEqual(
            canceled_host_results.count(),
            1,
        )
        runner_service.return_value.execute.assert_not_called()

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_midrun_cancellation_materializes_unstarted_node_work(
        self, runner_service
    ):
        self.workflow_version = WorkflowVersion.objects.create(workflow=self.workflow, version=2)
        self.node.pk = None
        self.node.workflow_version = self.workflow_version
        self.node.save()
        second_node = WorkflowNode.objects.create(
            workflow_version=self.workflow_version,
            node_key="restart_service",
            name="Restart service",
            command_version=self.command_version,
            order_index=2,
        )
        publish_linear_fixture(self.workflow_version)
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        def execute(plan, event_handler, cancel_callback, **_kwargs):
            self.assertEqual(plan.node_run_id, NodeRun.objects.get(workflow_run=run, node_key=self.node.node_key).id)
            WorkflowRun.objects.filter(id=run.id).update(
                status=WorkflowRun.Status.CANCELED
            )
            self.assertTrue(cancel_callback())
            return RunnerResult.from_mapping(
                {"status": "canceled", "rc": 1, "stats": {}}
            )

        runner_service.return_value.execute.side_effect = execute

        result = execute_graph_fixture(run.id)

        node_runs = {
            node_run.workflow_node_id: node_run
            for node_run in NodeRun.objects.filter(workflow_run=run).exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"})
        }
        self.assertEqual(result.status, WorkflowRun.Status.CANCELED)
        self.assertEqual(set(node_runs), {self.node.id, second_node.id})
        self.assertTrue(
            all(
                node_run.status == NodeRun.Status.CANCELED
                for node_run in node_runs.values()
            )
        )
        self.assertEqual(
            HostRunResult.objects.filter(
                node_run__workflow_run=run,
                status=HostRunResult.Status.CANCELED,
            ).count(),
            2,
        )
        self.assertEqual(
            set(
                HostRunResult.objects.filter(
                    node_run__workflow_run=run,
                    status=HostRunResult.Status.CANCELED,
                ).values_list("node_run_id", flat=True)
            ),
            {node_run.id for node_run in node_runs.values()},
        )
        self.assertEqual(runner_service.return_value.execute.call_count, 1)

    @patch("apps.jobs.execution.registry.AnsibleExecutor")
    def test_ansible_cancellation_fills_missing_targets_and_preserves_terminal_results(
        self, runner_service
    ):
        second_host = AssetHost.objects.create(
            hostname="web02",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host, second_host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )

        def execute(plan, event_handler, cancel_callback, **_kwargs):
            event_handler(
                normalize_runner_event(
                    {
                        "event": "runner_on_ok",
                        "event_data": {
                            "host": "web01",
                            "res": {"stdout": "completed", "rc": 0},
                        },
                    }
                )
            )
            WorkflowRun.objects.filter(id=run.id).update(
                status=WorkflowRun.Status.CANCELED
            )
            self.assertTrue(cancel_callback())
            return RunnerResult.from_mapping(
                {"status": "canceled", "rc": 1, "stats": {}}
            )

        runner_service.return_value.execute.side_effect = execute

        result = execute_graph_fixture(run.id)

        node_run = NodeRun.objects.exclude(node_type__in={"start", "end", "parallel_gateway", "parallel_join"}).get(workflow_run=run)
        host_results = {
            host_result.hostname: host_result
            for host_result in HostRunResult.objects.filter(node_run=node_run)
        }
        self.assertEqual(result.status, WorkflowRun.Status.CANCELED)
        self.assertEqual(set(host_results), {"web01", "web02"})
        self.assertEqual(host_results["web01"].status, HostRunResult.Status.OK)
        self.assertEqual(host_results["web01"].stdout, "completed")
        self.assertEqual(host_results["web02"].status, HostRunResult.Status.CANCELED)
        self.assertEqual(host_results["web02"].host_key, f"id:{second_host.id}")
        self.assertIsNotNone(host_results["web02"].finished_at)

    def test_create_workflow_run_requires_published_workflow_version(self):
        draft_version = WorkflowVersion.objects.create(
            workflow=self.workflow,
            version=2,
            status=WorkflowVersion.Status.DRAFT,
            created_by=self.user,
        )
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs",
            {
                "workflowVersionId": str(draft_version.id),
                "hostIds": [str(self.host.id)],
                "inputVars": {},
                "workerPoolId": str(self.worker_pool.id),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        response = WorkflowRunViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)

    def test_create_workflow_run_api_creates_pending_run(self):
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs",
            {
                "workflowVersionId": str(self.workflow_version.id),
                "hostIds": [str(self.host.id)],
                "inputVars": {"service": "nginx"},
                "workerPoolId": str(self.worker_pool.id),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        response = WorkflowRunViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            response.data["data"]["status"],
            [WorkflowRun.Status.PENDING, WorkflowRun.Status.SUCCESS],
        )
        self.assertEqual(response.data["data"]["targetCount"], 1)
        self.assertTrue(
            DomainAuditEvent.objects.filter(
                action="workflow_run.create",
                resource_type="workflow_run",
                actor=self.user,
            ).exists()
        )
        self.assertTrue(
            JobEventLog.objects.filter(
                workflow_run_id=response.data["data"]["id"],
                event_type="workflow_dispatch_requested",
            ).exists()
        )

    def test_create_workflow_run_api_persists_runtime_execution_options(self):
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs",
            {
                "workflowVersionId": str(self.workflow_version.id),
                "hostIds": [str(self.host.id)],
                "workerPoolId": str(self.worker_pool.id),
                "hostStrategy": "rolling",
                "forks": 8,
                "serialBatch": 3,
                "maxFailPercentage": 20,
                "bypassHostGateway": True,
                "timeoutSeconds": 900,
                "queueTimeoutSeconds": 45,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = WorkflowRunViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 200)
        run = WorkflowRun.objects.get(id=response.data["data"]["id"])
        self.assertEqual(run.worker_pool_id, self.worker_pool.id)
        self.assertEqual(run.timeout_seconds, 900)
        self.assertEqual(run.queue_timeout_seconds, 45)
        self.assertEqual(run.input_vars["host_strategy"], "rolling")
        self.assertEqual(run.input_vars["ansible_forks"], 8)
        self.assertEqual(run.input_vars["serial_batch"], 3)
        self.assertEqual(run.input_vars["max_fail_percentage"], 20)
        self.assertTrue(run.input_vars["bypass_host_gateway"])

    def test_validate_workflow_run_does_not_create_or_dispatch_run(self):
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs/validate",
            {
                "workflowVersionId": str(self.workflow_version.id),
                "hostIds": [str(self.host.id)],
                "workerPoolId": str(self.worker_pool.id),
                "hostStrategy": "rolling",
                "serialBatch": 2,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user

        response = WorkflowRunViewSet.as_view({"post": "validate_run"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["valid"])
        self.assertEqual(response.data["data"]["targetCount"], 1)
        self.assertEqual(response.data["data"]["workerPoolId"], self.worker_pool.id)
        self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_create_workflow_run_rejects_high_risk_without_permission(self):
        high_risk_command = CommandAtom.objects.create(
            name="Remove files",
            code="remove_files",
            category="system",
            risk_level=CommandAtom.RiskLevel.HIGH,
            created_by=self.user,
            updated_by=self.user,
        )
        high_risk_version = CommandVersion.objects.create(
            command=high_risk_command,
            version=1,
            status=CommandVersion.Status.PUBLISHED,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="rm -rf /tmp/demo",
            created_by=self.user,
            published_by=self.user,
        )
        high_risk_workflow = WorkflowTemplate.objects.create(
            name="High risk workflow",
            code="high_risk_workflow",
            created_by=self.user,
            updated_by=self.user,
        )
        high_risk_workflow_version = WorkflowVersion.objects.create(
            workflow=high_risk_workflow,
            version=1,
            status=WorkflowVersion.Status.PUBLISHED,
            created_by=self.user,
            published_by=self.user,
        )
        WorkflowNode.objects.create(
            workflow_version=high_risk_workflow_version,
            node_key="remove_files",
            name="Remove files",
            command_version=high_risk_version,
            order_index=1,
        )
        request = APIRequestFactory().post(
            "/api/v1/tasks/runs",
            {
                "workflowVersionId": str(high_risk_workflow_version.id),
                "hostIds": [str(self.host.id)],
                "inputVars": {},
                "workerPoolId": str(self.worker_pool.id),
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        request.user = self.user
        response = WorkflowRunViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            WorkflowRun.objects.filter(
                workflow_version=high_risk_workflow_version
            ).count(),
            0,
        )

    def test_cancel_workflow_run_api_creates_audit_event(self):
        run = create_workflow_run(
            workflow_version=self.workflow_version,
            target_hosts=[self.host],
            input_vars={},
            worker_pool=self.worker_pool,
            triggered_by=self.user,
        )
        request = APIRequestFactory().post(f"/api/v1/tasks/runs/{run.id}/cancel")
        force_authenticate(request, user=self.user)
        request.user = self.user
        response = WorkflowRunViewSet.as_view({"post": "cancel"})(
            request, pk=str(run.id)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DomainAuditEvent.objects.filter(
                action="workflow_run.cancel",
                resource_type="workflow_run",
                resource_id=str(run.id),
                actor=self.user,
            ).exists()
        )
