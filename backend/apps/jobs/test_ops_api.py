"""作业系统扩展接口（安全管控/网关/Playbook/Module/看板/配置）冒烟测试。"""

import os
import shlex
import shutil

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.models import CommandAtom, CommandVersion
from apps.audit_center.models import DomainAuditEvent
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost
from apps.cmdb.targets import snapshot_targets
from apps.jobs.models import WorkerPool

from .models import (
    CommandIntercept,
    Gateway,
    SecurityRule,
    WorkflowRun,
)
from apps.jobs.execution.plan_builder import (
    COMMAND_OUTPUT_MARKER,
    InvalidGateway,
    InvalidSourcePlaybook,
    build_source_playbook,
    parse_module_args,
    prepare_gateway_execution,
    prepare_host_gateway_execution,
    wrap_command_lines_with_markers,
)
from .views import (
    DashboardRecentView,
    DashboardStatsView,
    EngineSettingsView,
    GatewayViewSet,
    ModuleRunViewSet,
    PlaybookRunViewSet,
    QuickCommandRunViewSet,
    SecurityRuleViewSet,
    SecurityStatsView,
    OpsWorkflowRunViewSet,
    WorkflowRunViewSet,
)


class OpsExtensionApiTests(TestCase):
    def test_execution_requests_are_idempotent_and_reject_changed_payload(self):
        payload = {
            "commandType": "linux_shell",
            "commandContent": "uptime",
            "hostIds": [self.host.id],
            "workerPoolId": self.worker_pool.id,
            "executionRequestId": "review-request-unique-001",
        }
        view = QuickCommandRunViewSet.as_view({"post": "create"})
        first = self._request("post", view, payload)
        second = self._request("post", view, payload)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(first.data["data"]["id"], second.data["data"]["id"])
        changed = self._request("post", view, {**payload, "commandContent": "date"})
        self.assertEqual(changed.status_code, 409, changed.data)

    def test_invalid_module_arguments_are_rejected_during_preview(self):
        for arguments in ('msg="unterminated', "msg=hello world"):
            with self.subTest(arguments=arguments):
                response = self._request(
                    "post",
                    ModuleRunViewSet.as_view({"post": "preview"}),
                    {
                        "moduleName": "ansible.builtin.debug",
                        "moduleArgs": arguments,
                        "hostIds": [self.host.id],
                        "workerPoolId": self.worker_pool.id,
                    },
                )
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("moduleArgs", response.data["msg"])

    def test_module_default_values_with_spaces_are_preserved(self):
        resource = CommandAtom.objects.create(
            name="Debug spaces",
            code="test.module.spaces",
            status="published",
            resource_kind="module",
        )
        version = CommandVersion.objects.create(
            command=resource,
            version=1,
            status="published",
            command_type="ansible_module",
            content="ansible.builtin.debug",
            default_vars={
                "module_args": {
                    "msg": "hello world's test",
                    "headers": {"X-Value": "one"},
                    "names": ["nginx", "git"],
                }
            },
        )
        response = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                "moduleVersionId": version.id,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.get(pk=response.data["data"]["id"])
        task = build_source_playbook(run)[0]["tasks"][0]
        self.assertEqual(
            task["ansible.builtin.debug"],
            {
                "msg": "hello world's test",
                "headers": {"X-Value": "one"},
                "names": ["nginx", "git"],
            },
        )

    def test_quick_execution_rejects_disabled_source_and_reserved_variables(self):
        resource = CommandAtom.objects.create(
            name="Disabled", code="test.disabled.source", status="draft"
        )
        version = CommandVersion.objects.create(
            command=resource,
            version=1,
            status="published",
            command_type="linux_shell",
            content="uptime",
        )
        base = {
            "commandType": "linux_shell",
            "commandContent": version.content,
            "hostIds": [self.host.id],
            "workerPoolId": self.worker_pool.id,
        }
        for fields in (
            {"sourceCommandVersionId": version.id},
            {"extraVars": {"command_content": "other"}},
            {"extraVars": []},
        ):
            with self.subTest(fields=fields):
                response = self._request(
                    "post",
                    QuickCommandRunViewSet.as_view({"post": "preview"}),
                    {**base, **fields},
                )
                self.assertEqual(response.status_code, 400, response.data)

    def test_playbook_and_module_preserve_resource_defaults_and_runtime_overrides(self):
        from apps.jobs.execution.snapshots import execution_node, ensure_node_runs
        from apps.jobs.execution.plan_builder import _merge_node_vars

        for kind, command_type, content, view, fields in (
            (
                "playbook",
                "playbook",
                "- hosts: all\n  tasks: []\n",
                PlaybookRunViewSet,
                {},
            ),
            (
                "module",
                "ansible_module",
                "ansible.builtin.debug",
                ModuleRunViewSet,
                {"moduleArgs": ""},
            ),
        ):
            with self.subTest(kind=kind):
                resource = CommandAtom.objects.create(
                    name=kind,
                    code=f"test.extra.{kind}",
                    status="published",
                    resource_kind=kind,
                )
                version = CommandVersion.objects.create(
                    command=resource,
                    version=1,
                    status="published",
                    command_type=command_type,
                    content=content,
                    default_vars={"greeting": "default", "count": 2},
                    become_enabled=True,
                    timeout_seconds=90,
                )
                source = (
                    {"playbookVersionId": version.id, "playbookContent": content}
                    if kind == "playbook"
                    else {"moduleVersionId": version.id}
                )
                payload = {
                    **fields,
                    **source,
                    "extraVars": {"greeting": "override"},
                    "hostIds": [self.host.id],
                    "workerPoolId": self.worker_pool.id,
                }
                preview = self._request(
                    "post", view.as_view({"post": "preview"}), payload
                )
                self.assertEqual(preview.status_code, 200, preview.data)
                summary = preview.data["data"]["contentSummary"]
                self.assertIn(
                    {"name": "extra_vars", "value": "资源默认 2 项，本次填写 1 项，同名覆盖"}, summary
                )
                response = self._request(
                    "post", view.as_view({"post": "create"}), payload
                )
                self.assertEqual(response.status_code, 200, response.data)
                run = WorkflowRun.objects.get(pk=response.data["data"]["id"])
                ensure_node_runs(run)
                node = execution_node(run.node_runs.get(node_key="quick_command"))
                variables = _merge_node_vars(run, node)
                self.assertEqual(variables["greeting"], "override")
                self.assertEqual(variables["count"], 2)
                self.assertTrue(node.command_version.become_enabled)
                self.assertIsNone(node.timeout_seconds)
                self.assertEqual(
                    run.execution_settings["nodes"]["quick_command"]["values"][
                        "timeoutSeconds"
                    ],
                    90,
                )
                self.assertEqual(
                    run.execution_settings["nodes"]["quick_command"]["sources"][
                        "timeoutSeconds"
                    ],
                    "resource",
                )

    def test_quick_resource_variables_are_inherited_overridden_and_frozen(self):
        from apps.jobs.execution.snapshots import execution_node
        from apps.jobs.execution.plan_builder import _merge_node_vars
        from apps.jobs.execution.snapshots import ensure_node_runs

        resource = CommandAtom.objects.create(
            name="变量脚本",
            code="test.extra.vars",
            status="published",
        )
        version = CommandVersion.objects.create(
            command=resource,
            version=1,
            status="published",
            command_type="linux_shell",
            content="echo {{ greeting }}",
            default_vars={"greeting": "default", "count": 2},
        )
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": "linux_shell",
                "commandContent": version.content,
                "sourceCommandVersionId": version.id,
                "extraVars": {"greeting": "override"},
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.get(pk=response.data["data"]["id"])
        CommandVersion.objects.filter(pk=version.pk).update(status="archived")
        ensure_node_runs(run)
        node_run = run.node_runs.get(node_key="quick_command")
        values = _merge_node_vars(run, execution_node(node_run))
        self.assertEqual(values["greeting"], "override")
        self.assertEqual(values["count"], 2)

    def test_playbook_source_version_content_mismatch_rejected(self):
        resource = CommandAtom.objects.create(
            name="变量剧本",
            code="test.extra.playbook",
            status="published",
            resource_kind="playbook",
        )
        version = CommandVersion.objects.create(
            command=resource,
            version=1,
            status="published",
            command_type="playbook",
            content="- hosts: all\n  tasks: []\n",
        )
        response = self._request(
            "post",
            PlaybookRunViewSet.as_view({"post": "create"}),
            {
                "playbookVersionId": version.id,
                "playbookContent": "- hosts: all\n  tasks:\n    - debug: msg=changed\n",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 400, response.data)

    # T13 契约：所有可克隆运行必须携带发布冻结的合法图快照。
    MINIMAL_GRAPH = {
        "nodes": [
            {"id": "start", "type": "start"},
            {"id": "end", "type": "end"},
        ],
        "edges": [{"id": "start-end", "source": "start", "target": "end"}],
    }

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="ops-user",
            password="123456",
            email="ops-user@example.com",
            phone="13800000009",
        )
        self.worker_pool = WorkerPool.objects.create(
            code="default",
            name="Default Worker Pool",
            queue_name="ansible.default",
            is_default=True,
        )
        self.host = AssetHost.objects.create(
            hostname="web01",
            internal_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            cpu_cores=2,
            memory_mb=4096,
            system_disk_gb=40,
            data_disk_gb=200,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        self.factory = APIRequestFactory()
        module = CommandAtom.objects.create(
            name="Yum package manager",
            code="module.yum.test",
            category="package",
            resource_kind=CommandAtom.ResourceKind.MODULE,
            status=CommandAtom.Status.PUBLISHED,
        )
        self.module_version = CommandVersion.objects.create(
            command=module,
            version=1,
            status=CommandVersion.Status.PUBLISHED,
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content="yum",
        )

    def _request(self, method, view, data=None, **kwargs):
        handler = getattr(self.factory, method)
        request = handler("/api/v1/test", data, format="json", **kwargs)
        force_authenticate(request, user=self.user)
        return view(request, **kwargs)

    # ---------- 安全管控 ----------

    def test_security_rule_crud_and_toggle(self):
        response = self._request(
            "post",
            SecurityRuleViewSet.as_view({"post": "create"}),
            {
                "pattern": "shutdown -h",
                "match_mode": "prefix",
                "risk_level": "fatal",
                "description": "禁止关机",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        rule_id = response.data["data"]["id"]

        response = self._request(
            "post",
            SecurityRuleViewSet.as_view({"post": "toggle"}),
            pk=rule_id,
        )
        self.assertEqual(response.data["data"]["enabled"], False)

    def test_security_rule_invalid_regex_rejected(self):
        response = self._request(
            "post",
            SecurityRuleViewSet.as_view({"post": "create"}),
            {"pattern": "(", "match_mode": "regex"},
        )
        self.assertEqual(response.status_code, 400)

    def test_quick_command_blocked_by_blacklist(self):
        SecurityRule.objects.create(
            pattern="rm -rf /",
            match_mode=SecurityRule.MatchMode.REGEX,
            risk_level=SecurityRule.RiskLevel.FATAL,
            enabled=True,
        )
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "rm -rf /tmp/../etc",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 400)
        intercept = CommandIntercept.objects.latest("id")
        self.assertEqual(intercept.operator, self.user)
        self.assertIn("rm -rf /", intercept.hit_pattern)
        rule = SecurityRule.objects.filter(pattern="rm -rf /").latest("id")
        self.assertEqual(rule.blocked_count, 1)

    def test_quick_execution_previews_do_not_create_runs(self):
        cases = (
            (
                QuickCommandRunViewSet,
                {"commandType": "linux_shell", "commandContent": "uptime"},
            ),
            (
                PlaybookRunViewSet,
                {"playbookContent": "- hosts: all\n  tasks:\n    - debug: msg=ok\n"},
            ),
            (ModuleRunViewSet, {"moduleName": "ping", "moduleArgs": ""}),
        )
        for viewset, payload in cases:
            with self.subTest(viewset=viewset.__name__):
                response = self._request(
                    "post",
                    viewset.as_view({"post": "preview"}),
                    {
                        "hostIds": [self.host.id],
                        "workerPoolId": self.worker_pool.id,
                        **payload,
                    },
                )
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(
                    response.data["data"]["targets"][0]["hostId"], self.host.id
                )
                self.assertTrue(response.data["data"]["confirmationFingerprint"])
                self.assertTrue(response.data["data"]["contentSummary"])
                self.assertNotIn("commandContent", str(response.data["data"]))
                self.assertNotIn("playbookContent", str(response.data["data"]))
                self.assertEqual(WorkflowRun.objects.count(), 0)

    def test_quick_run_accepts_unchanged_confirmation(self):
        payload = {
            "commandType": "linux_shell",
            "commandContent": "uptime",
            "hostIds": [self.host.id],
            "workerPoolId": self.worker_pool.id,
        }
        preview = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "preview"}),
            payload,
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        run = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                **payload,
                "expectedConfirmationFingerprint": preview.data["data"][
                    "confirmationFingerprint"
                ],
            },
        )
        self.assertEqual(run.status_code, 200, run.data)

    def test_module_run_rejects_resource_risk_changed_after_preview(self):
        payload = {
            "moduleVersionId": self.module_version.id,
            "hostIds": [self.host.id],
            "workerPoolId": self.worker_pool.id,
        }
        preview = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "preview"}),
            payload,
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        CommandAtom.objects.filter(pk=self.module_version.command_id).update(
            risk_level=CommandAtom.RiskLevel.HIGH,
        )
        run = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                **payload,
                "expectedConfirmationFingerprint": preview.data["data"][
                    "confirmationFingerprint"
                ],
            },
        )
        self.assertEqual(run.status_code, 400, run.data)
        self.assertFalse(WorkflowRun.objects.exists())

    def test_quick_run_rejects_changed_preview_targets(self):
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": "linux_shell",
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "expectedTargetIds": [],
            },
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(WorkflowRun.objects.exists())

    def test_security_stats_view(self):
        before = SecurityRule.objects.filter(enabled=True).count()
        SecurityRule.objects.create(pattern="mkfs.test", enabled=True)
        response = self._request("get", SecurityStatsView.as_view())
        self.assertEqual(response.data["data"]["ruleCount"], before + 1)
        self.assertEqual(response.data["data"]["monthBlocked"], 0)

    # ---------- 网关代理 ----------

    def test_gateway_crud_encrypts_secret(self):
        response = self._request(
            "post",
            GatewayViewSet.as_view({"post": "create"}),
            {
                "name": "测试网关",
                "address": "127.0.0.1:22",
                "cloud": "私有云",
                "auth_type": "key",
                "username": "ops",
                "secret": "PRIVATE-KEY",
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        gateway = Gateway.objects.get(name="测试网关")
        self.assertNotEqual(gateway.secret_encrypted, "PRIVATE-KEY")
        self.assertTrue(gateway.secret_encrypted)
        self.assertNotIn("secret", response.data["data"])
        event = DomainAuditEvent.objects.get(
            action="jobs.gateway.create", resource_id=str(gateway.pk)
        )
        self.assertEqual(event.after["name"], "测试网关")
        self.assertNotIn("secret", str(event.after))
        self.assertNotIn("PRIVATE-KEY", str(event.after))

    def test_gateway_rejects_unused_auto_network_rule(self):
        response = self._request(
            "post",
            GatewayViewSet.as_view({"post": "create"}),
            {"name": "bad-gateway", "address": "10.0.0.1:22", "network": "10.0.0.0/16"},
        )
        self.assertEqual(response.status_code, 400)

    # ---------- Playbook ----------

    def test_playbook_run(self):
        playbook_content = "---\n- hosts: all\n  tasks: []"
        response = self._request(
            "post",
            PlaybookRunViewSet.as_view({"post": "create"}),
            {
                "playbookContent": playbook_content,
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.get(id=response.data["data"]["id"])
        self.assertEqual(run.input_vars["execution_source"], "playbook")
        self.assertEqual(run.input_vars["playbook_content"], playbook_content)
        self.assertEqual(run.trigger_type, WorkflowRun.TriggerType.MANUAL)
        self.assertEqual(run.run_domain, WorkflowRun.RunDomain.OPS)
        self.assertEqual(run.execution_kind, WorkflowRun.ExecutionKind.PLAYBOOK)

    # ---------- Module ----------

    def test_module_run_create(self):
        response = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                "moduleVersionId": self.module_version.id,
                "moduleArgs": "name=vim state=present",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.get(id=response.data["data"]["id"])
        self.assertEqual(run.input_vars["execution_source"], "module")
        self.assertEqual(run.input_vars["module"], "yum")

    def test_module_run_blocked_by_blacklist(self):
        SecurityRule.objects.create(
            pattern="cat /etc/shadow",
            match_mode=SecurityRule.MatchMode.CONTAINS,
            risk_level=SecurityRule.RiskLevel.HIGH,
            enabled=True,
        )
        response = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                "moduleVersionId": self.module_version.id,
                "moduleArgs": "cat /etc/shadow",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(CommandIntercept.objects.exists())

    # ---------- 看板 ----------

    def test_dashboard_stats_and_recent(self):
        response = self._request("get", DashboardStatsView.as_view())
        data = response.data["data"]
        self.assertEqual(data["todayExecutions"], 0)
        self.assertEqual(data["finishedExecutions"], 0)
        self.assertIsNone(data["successRate"])
        self.assertIsNone(data["avgResponseSeconds"])

        response = self._request("get", DashboardRecentView.as_view())
        self.assertEqual(response.data["data"], [])

    def test_dashboard_domain_filters_task_runs_and_scheduled_count(self):
        task_run = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.SCHEDULED,
            run_domain=WorkflowRun.RunDomain.TASK,
        )
        WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            run_domain=WorkflowRun.RunDomain.OPS,
        )

        stats = self._request("get", DashboardStatsView.as_view(), {"domain": "task"})
        recent = self._request("get", DashboardRecentView.as_view(), {"domain": "task"})

        self.assertEqual(stats.data["data"]["todayExecutions"], 1)
        self.assertEqual(stats.data["data"]["scheduledExecutions"], 1)
        self.assertEqual([item["id"] for item in recent.data["data"]], [task_run.id])
        self.assertEqual(recent.data["data"][0]["name"], f"任务运行 #{task_run.id}")
        self.assertEqual(stats.data["data"]["finishedExecutions"], 0)
        self.assertIsNone(stats.data["data"]["successRate"])

    def test_dashboard_success_rate_uses_finished_runs_only(self):
        WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            run_domain=WorkflowRun.RunDomain.TASK,
            status=WorkflowRun.Status.SUCCESS,
            duration_ms=2300,
        )
        WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            run_domain=WorkflowRun.RunDomain.TASK,
            status=WorkflowRun.Status.RUNNING,
        )

        response = self._request(
            "get", DashboardStatsView.as_view(), {"domain": "task"}
        )
        self.assertEqual(response.data["data"]["todayExecutions"], 2)
        self.assertEqual(response.data["data"]["finishedExecutions"], 1)
        self.assertEqual(response.data["data"]["successRate"], 100.0)
        self.assertEqual(response.data["data"]["avgResponseSeconds"], 2.3)

    # ---------- 配置 ----------

    def test_engine_settings_roundtrip(self):
        response = self._request("get", EngineSettingsView.as_view())
        self.assertEqual(
            set(response.data["data"]),
            {
                "timeout",
                "forks",
                "host_strategy",
                "serial_batch",
                "max_fail_percentage",
            },
        )
        self.assertEqual(response.data["data"]["timeout"], 300)

        response = self._request(
            "put",
            EngineSettingsView.as_view(),
            {
                "timeout": 180,
                "forks": 20,
                "host_strategy": "rolling",
                "serial_batch": 4,
                "max_fail_percentage": 25,
            },
        )
        data = response.data["data"]
        self.assertEqual(data["timeout"], 180)
        self.assertEqual(data["forks"], 20)
        self.assertEqual(data["host_strategy"], "rolling")
        self.assertEqual(data["serial_batch"], 4)
        self.assertEqual(data["max_fail_percentage"], 25)

    # ---------- Playbook 资产预校验 ----------

    def test_playbook_run_rejects_invalid_yaml_content(self):
        response = self._request(
            "post",
            PlaybookRunViewSet.as_view({"post": "create"}),
            {
                "playbookContent": "- name: broken\n  hosts: all\n  tasks:\n  - name: x\n    shell: [unclosed",
                "hostIds": [self.host.id],
                "workerPoolId": self.worker_pool.id,
            },
        )
        self.assertEqual(response.status_code, 400)


class SourcePlaybookBuildTests(TestCase):
    """验证 execution_source 为 playbook/module 时的真实计划构造。"""

    def _run_with_vars(self, input_vars):
        return WorkflowRun(input_vars=input_vars)

    def test_quick_command_source_returns_none(self):
        run = self._run_with_vars({"execution_source": "quick_command"})
        self.assertIsNone(build_source_playbook(run))

    def test_playbook_source_builds_real_playbook(self):
        content = (
            "- name: Update Nginx\n"
            "  hosts: lb-prod\n"
            "  become: true\n"
            "  tasks:\n"
            "    - name: Reload nginx\n"
            "      ansible.builtin.service:\n"
            "        name: nginx\n"
            "        state: reloaded\n"
        )
        run = self._run_with_vars(
            {"execution_source": "playbook", "playbook_content": content}
        )
        plays = build_source_playbook(run)
        self.assertEqual(len(plays), 1)
        self.assertEqual(plays[0]["hosts"], "all")
        self.assertTrue(plays[0]["become"])
        self.assertEqual(plays[0]["tasks"][0]["name"], "Reload nginx")

    def test_playbook_source_invalid_yaml_raises(self):
        run = self._run_with_vars(
            {
                "execution_source": "playbook",
                "playbook_content": "- name: broken\n  tasks: [unclosed",
            }
        )
        with self.assertRaises(InvalidSourcePlaybook):
            build_source_playbook(run)

    def test_playbook_source_non_play_content_raises(self):
        run = self._run_with_vars(
            {"execution_source": "playbook", "playbook_content": "just plain text"}
        )
        with self.assertRaises(InvalidSourcePlaybook):
            build_source_playbook(run)

    def test_module_source_kv_args(self):
        run = self._run_with_vars(
            {
                "execution_source": "module",
                "module": "yum",
                "module_args": "name=vim state=present",
            }
        )
        plays = build_source_playbook(run)
        task = plays[0]["tasks"][0]
        self.assertEqual(task["yum"], {"name": "vim", "state": "present"})

    def test_module_source_free_form(self):
        run = self._run_with_vars(
            {
                "execution_source": "module",
                "module": "shell",
                "module_args": "df -h | grep /",
            }
        )
        plays = build_source_playbook(run)
        task = plays[0]["tasks"][0]
        self.assertEqual(task["shell"], {"_raw_params": "df -h | grep /"})

    def test_module_source_bad_args_raises(self):
        run = self._run_with_vars(
            {
                "execution_source": "module",
                "module": "yum",
                "module_args": "name=vim badtoken",
            }
        )
        with self.assertRaises(InvalidSourcePlaybook):
            build_source_playbook(run)

    def test_parse_module_args_quoted_value(self):
        parsed = parse_module_args('name=nginx state=restarted comment="web server"')
        self.assertEqual(
            parsed,
            {"name": "nginx", "state": "restarted", "comment": "web server"},
        )


class GatewayExecutionTests(OpsExtensionApiTests):
    """验证快速执行选择网关通道的下发与 ProxyCommand 构造。"""

    def _create_gateway(self, auth_type=Gateway.AuthType.PASSWORD, **kwargs):
        defaults = dict(
            address="10.0.0.1:2222",
            auth_type=auth_type,
            username="jump",
            secret_encrypted=encrypt_secret("s3cret"),
            status=Gateway.Status.NORMAL,
        )
        defaults.update(kwargs)
        return Gateway.objects.create(name=f"gw-{auth_type}", **defaults)

    def test_quick_command_run_with_gateway_sets_input_vars(self):
        gateway = self._create_gateway()
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": gateway.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertEqual(run.input_vars.get("gateway_id"), gateway.id)

    def test_quick_preview_shows_explicit_gateway(self):
        gateway = self._create_gateway()
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "preview"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": gateway.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["gatewayName"], gateway.name)

    def test_quick_command_run_without_gateway_keeps_local_direct(self):
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertNotIn("gateway_id", run.input_vars or {})

    def test_run_snapshot_has_no_implicit_gateway(self):
        self._create_gateway()
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertNotIn("gateway_ref_id", run.target_snapshot[0]["variables"])

    def test_quick_command_run_persists_host_execution_options(self):
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "hostStrategy": "rolling",
                "forks": 12,
                "serialBatch": 4,
                "maxFailPercentage": 25,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertEqual(run.input_vars["host_strategy"], "rolling")
        self.assertEqual(run.input_vars["ansible_forks"], 12)
        self.assertEqual(run.input_vars["serial_batch"], 4)
        self.assertEqual(run.input_vars["max_fail_percentage"], 25)

    def test_quick_command_run_rejects_unknown_gateway(self):
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": 999999,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_quick_command_run_rejects_abnormal_gateway(self):
        gateway = self._create_gateway(status=Gateway.Status.ABNORMAL)
        response = self._request(
            "post",
            QuickCommandRunViewSet.as_view({"post": "create"}),
            {
                "commandType": CommandVersion.CommandType.LINUX_SHELL,
                "commandContent": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": gateway.id,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_task_and_ops_run_lists_are_isolated_by_domain(self):
        """任务和作业列表必须由后端强制按领域隔离。"""
        task_run = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            run_domain=WorkflowRun.RunDomain.TASK,
        )
        ops_run = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            run_domain=WorkflowRun.RunDomain.OPS,
            execution_kind=WorkflowRun.ExecutionKind.QUICK_COMMAND,
        )

        response = self._request(
            "get",
            WorkflowRunViewSet.as_view({"get": "list"}),
            {"pageNum": 1, "pageSize": 20},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["total"], 1)
        self.assertEqual(response.data["data"]["list"][0]["runDomain"], "task")

        response = self._request(
            "get",
            OpsWorkflowRunViewSet.as_view({"get": "list"}),
            {"pageNum": 1, "pageSize": 20},
        )
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["data"]["list"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["runDomain"], "ops")
        self.assertEqual(items[0]["executionKind"], "quick_command")

        task_response = self._request(
            "get",
            WorkflowRunViewSet.as_view({"get": "retrieve"}),
            pk=ops_run.id,
        )
        self.assertEqual(task_response.status_code, 404)
        ops_response = self._request(
            "get",
            OpsWorkflowRunViewSet.as_view({"get": "retrieve"}),
            pk=task_run.id,
        )
        self.assertEqual(ops_response.status_code, 404)

    def test_workflow_run_retry_failed_returns_new_run(self):
        """失败任务重试应克隆原运行并返回新运行数据。"""
        run = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            status=WorkflowRun.Status.FAILED,
            target_snapshot=snapshot_targets(actor=self.user, targets=[self.host]),
            graph_snapshot=self.MINIMAL_GRAPH,
            queue_timeout_seconds=60,
        )
        response = self._request(
            "post",
            WorkflowRunViewSet.as_view({"post": "retry_failed"}),
            pk=run.id,
        )
        self.assertEqual(response.status_code, 200, response.data)
        retry_run = WorkflowRun.objects.latest("id")
        self.assertEqual(response.data["data"]["id"], retry_run.id)
        self.assertNotEqual(retry_run.id, run.id)
        # 克隆保留完整历史快照，仅重新校验当前权限和可用状态。
        self.assertEqual(retry_run.target_snapshot, run.target_snapshot)
        self.assertEqual(
            [(t["host_id"], t["hostname"]) for t in retry_run.target_snapshot],
            [(t["host_id"], t["hostname"]) for t in run.target_snapshot],
        )
        self.assertIn("address", retry_run.target_snapshot[0])
        self.assertIn("connection_type", retry_run.target_snapshot[0])

    def test_workflow_run_rerun_clones_finished_run(self):
        """重跑：已结束的任务克隆原运行重新调度，未结束的拒绝。"""
        run = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            status=WorkflowRun.Status.SUCCESS,
            target_snapshot=snapshot_targets(actor=self.user, targets=[self.host]),
            graph_snapshot=self.MINIMAL_GRAPH,
            queue_timeout_seconds=60,
        )
        response = self._request(
            "post",
            WorkflowRunViewSet.as_view({"post": "rerun"}),
            pk=run.id,
        )
        self.assertEqual(response.status_code, 200, response.data)
        rerun_run = WorkflowRun.objects.latest("id")
        self.assertEqual(response.data["data"]["id"], rerun_run.id)
        self.assertNotEqual(rerun_run.id, run.id)
        # 克隆保留完整历史快照，仅重新校验当前权限和可用状态。
        self.assertEqual(rerun_run.target_snapshot, run.target_snapshot)
        self.assertEqual(
            [(t["host_id"], t["hostname"]) for t in rerun_run.target_snapshot],
            [(t["host_id"], t["hostname"]) for t in run.target_snapshot],
        )
        self.assertIn("address", rerun_run.target_snapshot[0])
        self.assertEqual(rerun_run.trigger_type, WorkflowRun.TriggerType.MANUAL)

        running = WorkflowRun.objects.create(
            worker_pool=self.worker_pool,
            trigger_type=WorkflowRun.TriggerType.MANUAL,
            status=WorkflowRun.Status.RUNNING,
            queue_timeout_seconds=60,
        )
        response = self._request(
            "post",
            WorkflowRunViewSet.as_view({"post": "rerun"}),
            pk=running.id,
        )
        self.assertEqual(response.status_code, 400)

    def test_prepare_gateway_execution_empty(self):
        self.assertEqual(prepare_gateway_execution(None), ({}, ""))
        self.assertEqual(prepare_gateway_execution({}), ({}, ""))

    def test_prepare_gateway_execution_password_proxy(self):
        gateway = self._create_gateway()
        group_vars, private_dir = prepare_gateway_execution({"gateway_id": gateway.id})
        self.assertEqual(private_dir, "")
        args = group_vars["ansible_ssh_common_args"]
        self.assertIn("ProxyCommand", args)
        self.assertIn("sshpass", args)
        self.assertIn("jump@10.0.0.1", args)
        self.assertIn("-p 2222", args)

    def test_prepare_gateway_execution_key_writes_temp_key(self):
        gateway = self._create_gateway(auth_type=Gateway.AuthType.KEY)
        group_vars, private_dir = prepare_gateway_execution({"gateway_id": gateway.id})
        try:
            self.assertTrue(private_dir)
            key_path = os.path.join(private_dir, "gateway_key")
            self.assertTrue(os.path.exists(key_path))
            args = group_vars["ansible_ssh_common_args"]
            self.assertIn("ssh -i", args)
            self.assertNotIn("sshpass", args)
        finally:
            if private_dir:
                shutil.rmtree(private_dir, ignore_errors=True)

    def test_prepare_gateway_execution_missing_gateway_raises(self):
        with self.assertRaises(InvalidGateway):
            prepare_gateway_execution({"gateway_id": 999999})

    def test_prepare_gateway_execution_abnormal_gateway_raises(self):
        gateway = self._create_gateway(status=Gateway.Status.ABNORMAL)
        with self.assertRaises(InvalidGateway):
            prepare_gateway_execution({"gateway_id": gateway.id})

    def test_prepare_host_gateway_explicit_applies_to_all_ssh_hosts(self):
        gateway = self._create_gateway(address="10.0.0.1:22")
        hosts, group_vars, private_dir = prepare_host_gateway_execution(
            [
                {"hostname": "one", "connection_type": "ssh"},
                {"hostname": "two", "connection_type": "ssh"},
            ],
            {"gateway_id": gateway.id},
        )
        self.assertEqual(group_vars, {})
        self.assertEqual(private_dir, "")
        self.assertIn("10.0.0.1", hosts[0]["variables"]["ansible_ssh_common_args"])
        self.assertIn("10.0.0.1", hosts[1]["variables"]["ansible_ssh_common_args"])

    def test_prepare_host_gateway_without_gateway_keeps_direct(self):
        # 未选网关时一律直连：不做 CIDR 自动匹配，也不读主机默认网关
        self._create_gateway()
        hosts, group_vars, private_dir = prepare_host_gateway_execution(
            [
                {"hostname": "inner", "address": "10.60.1.5", "connection_type": "ssh"},
                {"hostname": "another", "connection_type": "ssh"},
            ]
        )
        self.assertEqual(group_vars, {})
        self.assertEqual(private_dir, "")
        self.assertNotIn("ansible_ssh_common_args", hosts[0].get("variables", {}))
        self.assertNotIn("ansible_ssh_common_args", hosts[1].get("variables", {}))

    def test_prepare_host_gateway_rejects_non_ssh_host(self):
        gateway = self._create_gateway(address="10.0.0.1:22")
        with self.assertRaises(InvalidGateway):
            prepare_host_gateway_execution(
                [{"hostname": "win", "connection_type": "winrm"}],
                {"gateway_id": gateway.id},
            )

    def test_explicit_gateway_is_not_silently_bypassed(self):
        gateway = self._create_gateway(address="10.0.0.1:22")
        hosts, _, private_dir = prepare_host_gateway_execution(
            [{"hostname": "web", "connection_type": "ssh", "variables": {}}],
            {"gateway_id": gateway.id, "bypass_host_gateway": True},
        )
        self.assertIn("ansible_ssh_common_args", hosts[0]["variables"])
        self.assertEqual(private_dir, "")

    def test_module_run_with_gateway_sets_input_vars(self):
        gateway = self._create_gateway()
        atom = CommandAtom.objects.create(
            name="Gateway shell",
            code="gateway-shell",
            resource_kind="module",
            status="published",
        )
        version = CommandVersion.objects.create(
            command=atom,
            version=1,
            status="published",
            command_type="ansible_module",
            content="ansible.builtin.shell",
        )
        response = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                "moduleVersionId": version.id,
                "moduleArgs": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": gateway.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertEqual(run.input_vars.get("gateway_id"), gateway.id)

    def test_playbook_run_with_gateway_sets_input_vars(self):
        gateway = self._create_gateway()
        response = self._request(
            "post",
            PlaybookRunViewSet.as_view({"post": "create"}),
            {
                "playbookContent": "- hosts: all\n  tasks:\n    - name: ping\n      ansible.builtin.ping: {}",
                "hostIds": [self.host.id],
                "gatewayId": gateway.id,
            },
        )
        self.assertEqual(response.status_code, 200, response.data)
        run = WorkflowRun.objects.latest("id")
        self.assertEqual(run.input_vars.get("gateway_id"), gateway.id)

    def test_module_run_rejects_unknown_gateway(self):
        response = self._request(
            "post",
            ModuleRunViewSet.as_view({"post": "create"}),
            {
                "module": "shell",
                "moduleArgs": "uptime",
                "hostIds": [self.host.id],
                "gatewayId": 999999,
            },
        )
        self.assertEqual(response.status_code, 400)


class CommandMarkerWrapTests(TestCase):
    """验证多行快速命令的分段标记注入。"""

    def test_single_line_unchanged(self):
        self.assertEqual(
            wrap_command_lines_with_markers(
                "uptime", CommandVersion.CommandType.LINUX_SHELL
            ),
            "uptime",
        )

    def test_multi_line_shell_injects_echo_markers(self):
        wrapped = wrap_command_lines_with_markers(
            "ls\npwd", CommandVersion.CommandType.LINUX_SHELL
        )
        lines = wrapped.split("\n")
        self.assertEqual(lines[0], f"echo '###DEVOPS_CMD### [1/2] ls'")
        self.assertEqual(lines[1], "ls")
        self.assertEqual(lines[2], f"echo '###DEVOPS_CMD### [2/2] pwd'")
        self.assertEqual(lines[3], "pwd")
        self.assertIn(COMMAND_OUTPUT_MARKER, wrapped)

    def test_multi_line_powershell_injects_write_output(self):
        wrapped = wrap_command_lines_with_markers(
            "Get-Date\nwhoami", CommandVersion.CommandType.WINDOWS_POWERSHELL
        )
        self.assertIn("Write-Output '###DEVOPS_CMD### [1/2] Get-Date'", wrapped)
        self.assertIn("Write-Output '###DEVOPS_CMD### [2/2] whoami'", wrapped)

    def test_blank_lines_skipped(self):
        wrapped = wrap_command_lines_with_markers(
            "ls\n\n  \npwd\n", CommandVersion.CommandType.LINUX_SHELL
        )
        self.assertIn("[2/2] pwd", wrapped)
        self.assertNotIn("[3/3]", wrapped)

    def test_marker_with_quotes_safely_quoted(self):
        wrapped = wrap_command_lines_with_markers(
            "echo 'a b'\npwd", CommandVersion.CommandType.LINUX_SHELL
        )
        # shlex.quote 保证含引号的命令文本不会破坏 echo 语句，
        # shell 解析后应能还原出完整标记文本
        echo_line = wrapped.split("\n")[0]
        self.assertTrue(echo_line.startswith("echo "))
        self.assertEqual(shlex.split(echo_line)[1], "###DEVOPS_CMD### [1/2] echo 'a b'")
