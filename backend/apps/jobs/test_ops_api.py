"""作业系统扩展接口（安全管控/网关/Playbook/Module/看板/配置）冒烟测试。"""

import os
import shlex
import shutil

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.automation.models import CommandAtom, CommandVersion
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetHost
from apps.jobs.models import WorkerPool

from .models import (
    CommandIntercept,
    Gateway,
    SecurityRule,
    WorkflowRun,
)
from apps.jobs.execution.plan_builder import COMMAND_OUTPUT_MARKER, InvalidGateway, InvalidSourcePlaybook, build_source_playbook, parse_module_args, prepare_gateway_execution, prepare_host_gateway_execution, wrap_command_lines_with_markers
from .views import (
    DashboardRecentView,
    DashboardStatsView,
    EngineSettingsView,
    GatewayViewSet,
    ModuleRunViewSet,
    NotifySettingsView,
    PlaybookRunViewSet,
    QuickCommandRunViewSet,
    SecurityRuleViewSet,
    SecurityStatsView,
    OpsWorkflowRunViewSet,
    WorkflowRunViewSet,
)


class OpsExtensionApiTests(TestCase):
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
            primary_ip="10.0.0.11",
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
                "network": "10.0.0.0/16",
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
        self.assertEqual(data["successRate"], 100.0)

        response = self._request("get", DashboardRecentView.as_view())
        self.assertEqual(response.data["data"], [])

    # ---------- 配置 ----------

    def test_engine_and_notify_settings_roundtrip(self):
        response = self._request("get", EngineSettingsView.as_view())
        self.assertEqual(response.data["data"]["default_user"], "root")

        response = self._request(
            "put",
            EngineSettingsView.as_view(),
            {"default_user": "ops", "forks": 20, "host_key_checking": False},
        )
        data = response.data["data"]
        self.assertEqual(data["default_user"], "ops")
        self.assertEqual(data["forks"], 20)
        self.assertFalse(data["host_key_checking"])

        response = self._request(
            "put",
            NotifySettingsView.as_view(),
            {"webhook_url": "https://example.com/hook", "webhook_secret": "s3cret"},
        )
        data = response.data["data"]
        self.assertEqual(data["webhook_url"], "https://example.com/hook")
        self.assertEqual(data["webhook_secret"], "s3cret")

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

    def test_host_default_gateway_is_frozen_in_run_snapshot(self):
        gateway = self._create_gateway()
        self.host.default_gateway = gateway
        self.host.save(update_fields=("default_gateway", "updated_at"))
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
        self.assertEqual(run.target_snapshot[0]["variables"]["gateway_ref_id"], gateway.id)

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
        self.assertEqual(response.data["data"]["list"][0]["run_domain"], "task")

        response = self._request(
            "get",
            OpsWorkflowRunViewSet.as_view({"get": "list"}),
            {"pageNum": 1, "pageSize": 20},
        )
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["data"]["list"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["run_domain"], "ops")
        self.assertEqual(items[0]["execution_kind"], "quick_command")

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
            target_snapshot=[{"host_id": self.host.id, "hostname": "web01"}],
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
        # T04/T13：克隆经 snapshot_targets 重新解析，目标主机不变且为完整非敏感快照
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
            target_snapshot=[{"host_id": self.host.id, "hostname": "web01"}],
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
        # T04/T13：克隆经 snapshot_targets 重新解析，目标主机不变且为完整非敏感快照
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

    def test_prepare_host_gateways_writes_per_host_proxy_vars(self):
        first = self._create_gateway(address="10.0.0.1:22")
        second = self._create_gateway(address="10.0.1.1:22")
        hosts, group_vars, private_dir = prepare_host_gateway_execution(
            [
                {
                    "hostname": "china",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": first.id},
                },
                {
                    "hostname": "sea",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": second.id},
                },
                {"hostname": "local", "connection_type": "ssh"},
            ]
        )
        self.assertEqual(group_vars, {})
        self.assertEqual(private_dir, "")
        self.assertIn(
            "10.0.0.1", hosts[0]["variables"]["ansible_ssh_common_args"]
        )
        self.assertIn(
            "10.0.1.1", hosts[1]["variables"]["ansible_ssh_common_args"]
        )
        self.assertNotIn("ansible_ssh_common_args", hosts[2].get("variables", {}))

    def test_run_gateway_overrides_host_default_gateway(self):
        host_gateway = self._create_gateway(address="10.0.0.1:22")
        override_gateway = self._create_gateway(address="10.0.9.1:22")
        hosts, _, _ = prepare_host_gateway_execution(
            [
                {
                    "hostname": "web",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": host_gateway.id},
                }
            ],
            {"gateway_id": override_gateway.id},
        )
        args = hosts[0]["variables"]["ansible_ssh_common_args"]
        self.assertIn("10.0.9.1", args)
        self.assertNotIn("10.0.0.1", args)

    def test_direct_mode_bypasses_host_default_gateway(self):
        host_gateway = self._create_gateway()
        hosts, group_vars, private_dir = prepare_host_gateway_execution(
            [
                {
                    "hostname": "web",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": host_gateway.id},
                }
            ],
            {"bypass_host_gateway": True},
        )
        self.assertEqual(group_vars, {})
        self.assertEqual(private_dir, "")
        self.assertNotIn("ansible_ssh_common_args", hosts[0].get("variables", {}))

    def test_prepare_multiple_key_gateways_uses_one_runner_directory(self):
        first = self._create_gateway(auth_type=Gateway.AuthType.KEY)
        second = self._create_gateway(
            auth_type=Gateway.AuthType.KEY, address="10.0.1.1:22"
        )
        hosts, _, private_dir = prepare_host_gateway_execution(
            [
                {
                    "hostname": "one",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": first.id},
                },
                {
                    "hostname": "two",
                    "connection_type": "ssh",
                    "variables": {"gateway_ref_id": second.id},
                },
            ]
        )
        try:
            self.assertTrue(
                os.path.exists(os.path.join(private_dir, f"gateway_{first.id}_key"))
            )
            self.assertTrue(
                os.path.exists(os.path.join(private_dir, f"gateway_{second.id}_key"))
            )
            self.assertIn(
                private_dir,
                hosts[0]["variables"]["ansible_ssh_common_args"],
            )
            self.assertIn(
                private_dir,
                hosts[1]["variables"]["ansible_ssh_common_args"],
            )
        finally:
            shutil.rmtree(private_dir, ignore_errors=True)

    def test_module_run_with_gateway_sets_input_vars(self):
        gateway = self._create_gateway()
        atom = CommandAtom.objects.create(name="Gateway shell", code="gateway-shell", resource_kind="module", status="published")
        version = CommandVersion.objects.create(command=atom, version=1, status="published", command_type="ansible_module", content="ansible.builtin.shell")
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
