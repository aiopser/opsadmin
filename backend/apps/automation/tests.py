from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from apps.automation.audit import build_automation_audit_snapshot
from apps.automation.models import (
    CommandAtom,
    CommandVersion,
    JenkinsJob,
    JenkinsServer,
    WorkflowNode,
    WorkflowTemplate,
    WorkflowVersion,
)
from apps.automation.serializers import CommandVersionSerializer
from common.workflow.schema import validate_graph


class WorkflowGraphValidationTests(SimpleTestCase):
    def test_accepts_connected_graph_with_one_start_and_end(self):
        graph = {
            "nodes": [
                {"id": "start", "type": "start", "timeoutSeconds": 1},
                {"id": "task", "type": "command", "timeoutSeconds": 60},
                {"id": "end", "type": "end", "timeoutSeconds": 1},
            ],
            "edges": [
                {"id": "e1", "source": "start", "target": "task"},
                {"id": "e2", "source": "task", "target": "end"},
            ],
        }

        self.assertEqual(validate_graph(graph), [])

    def test_rejects_duplicate_start_and_unreachable_node(self):
        graph = {
            "nodes": [
                {"id": "start-a", "type": "start", "timeoutSeconds": 1},
                {"id": "start-b", "type": "start", "timeoutSeconds": 1},
                {"id": "orphan", "type": "command", "timeoutSeconds": 60},
                {"id": "end", "type": "end", "timeoutSeconds": 1},
            ],
            "edges": [
                {"id": "e1", "source": "start-a", "target": "end"},
            ],
        }

        errors = validate_graph(graph)

        self.assertGreaterEqual(len(errors), 1)


class CommandVersionTests(TestCase):
    def test_published_command_version_cannot_be_modified(self):
        user = get_user_model().objects.create_user(
            username="operator",
            password="123456",
            email="operator@example.com",
            phone="13800000000",
        )
        command = CommandAtom.objects.create(
            name="Check version",
            code="check_version",
            category="system",
            risk_level=CommandAtom.RiskLevel.LOW,
            created_by=user,
            updated_by=user,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="uname -a",
            timeout_seconds=60,
            created_by=user,
        )
        version.publish(user)
        version.content = "rm -rf /"

        with self.assertRaises(ValueError):
            version.assert_mutable()


class AutomationAuditSnapshotTests(SimpleTestCase):
    def test_snapshot_uses_foreign_key_id(self):
        version = CommandVersion(
            command_id=42,
            version=1,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="uname -a",
        )

        snapshot = build_automation_audit_snapshot(version)

        self.assertEqual(snapshot["command"], 42)


class WorkflowVersionTests(TestCase):
    def test_published_workflow_version_cannot_be_modified(self):
        user = get_user_model().objects.create_user(
            username="workflow-operator",
            password="123456",
            email="workflow@example.com",
            phone="13800000001",
        )
        workflow = WorkflowTemplate.objects.create(
            name="Check service",
            code="check_service",
            created_by=user,
            updated_by=user,
        )
        version = WorkflowVersion.objects.create(
            workflow=workflow,
            version=1,
            created_by=user,
        )
        from apps.automation.workflow_graph import replace_graph

        self.assertEqual(
            replace_graph(
                version,
                {
                    "nodes": [
                        {"id": "start", "type": "start"},
                        {"id": "end", "type": "end"},
                    ],
                    "edges": [{"id": "done", "source": "start", "target": "end"}],
                },
            ),
            [],
        )
        version.publish(user)

        with self.assertRaises(ValueError):
            version.assert_mutable()

    def test_playbook_version_rejects_invalid_yaml_before_publish(self):
        command = CommandAtom.objects.create(
            name="Deploy playbook",
            code="deploy_playbook",
            resource_kind=CommandAtom.ResourceKind.PLAYBOOK,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type=CommandVersion.CommandType.PLAYBOOK,
            content="tasks: [",
        )

        serializer = CommandVersionSerializer(version, data={}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("content", serializer.errors)

    def test_module_version_requires_valid_module_name(self):
        command = CommandAtom.objects.create(
            name="Service module",
            code="service_module",
            resource_kind=CommandAtom.ResourceKind.MODULE,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content="service; rm -rf /",
            argument_schema={},
        )

        serializer = CommandVersionSerializer(version, data={}, partial=True)

        self.assertFalse(serializer.is_valid())
        self.assertIn("module_name", serializer.errors)

        version.content = "ansible.builtin.service"
        version.argument_schema = []
        serializer = CommandVersionSerializer(version, data={}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("argument_schema", serializer.errors)

    def test_archived_workflow_version_cannot_be_modified(self):
        workflow = WorkflowTemplate.objects.create(name="Archived", code="archived")
        version = WorkflowVersion.objects.create(
            workflow=workflow,
            version=1,
            status=WorkflowVersion.Status.ARCHIVED,
        )

        with self.assertRaises(ValueError):
            version.assert_mutable()


class WorkflowGraphApiTests(TestCase):
    def test_jenkins_node_binds_synced_job_resource(self):
        from apps.automation.views import WorkflowVersionViewSet
        from apps.automation.workflow_graph import replace_graph

        workflow = WorkflowTemplate.objects.create(
            name="Jenkins graph", code="jenkins_graph"
        )
        version = WorkflowVersion.objects.create(workflow=workflow, version=1)
        server = JenkinsServer.objects.create(
            name="Production Jenkins",
            base_url="https://jenkins.example.com",
        )
        job = JenkinsJob.objects.create(server=server, name="release-api")
        replace_graph(
            version,
            {
                "nodes": [
                    {"id": "start", "name": "开始", "type": "start"},
                    {
                        "id": "release",
                        "name": "发布",
                        "type": "jenkins",
                        "resourceType": "jenkins_job",
                        "resourceId": job.id,
                        "config": {"parameters": {"ENV": "prod"}},
                        "timeoutSeconds": 600,
                    },
                    {"id": "end", "name": "结束", "type": "end"},
                ],
                "edges": [
                    {"id": "e1", "source": "start", "target": "release"},
                    {"id": "e2", "source": "release", "target": "end"},
                ],
            },
        )

        errors = WorkflowVersionViewSet()._validate_workflow_version(version)

        self.assertEqual(errors, [])

    def test_invalid_draft_graph_does_not_replace_runtime_graph(self):
        from apps.automation.views import WorkflowVersionViewSet

        user = get_user_model().objects.create_superuser(
            username="graph-admin",
            password="123456",
            email="graph-admin@example.com",
            phone="13800000003",
        )
        workflow = WorkflowTemplate.objects.create(
            name="Draft graph", code="draft_graph"
        )
        version = WorkflowVersion.objects.create(workflow=workflow, version=1)
        request = APIRequestFactory().put(
            f"/api/v1/automation/workflow-versions/{version.id}/graph",
            {
                "graph": {
                    "nodes": [{"id": "start", "type": "start"}],
                    "edges": [],
                },
            },
            format="json",
        )
        force_authenticate(request, user=user)

        response = WorkflowVersionViewSet.as_view({"put": "graph"})(
            request,
            pk=str(version.id),
        )

        version.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["data"]["valid"])
        self.assertTrue(version.validation_report)
        self.assertEqual(version.nodes.count(), 0)

    def test_validate_rejects_graph_without_executable_node(self):
        from apps.automation.views import WorkflowVersionViewSet
        from apps.automation.workflow_graph import replace_graph

        user = get_user_model().objects.create_superuser(
            username="empty-graph-admin",
            password="123456",
            email="empty-graph-admin@example.com",
            phone="13800000005",
        )
        workflow = WorkflowTemplate.objects.create(
            name="Empty graph", code="empty_graph"
        )
        version = WorkflowVersion.objects.create(workflow=workflow, version=1)
        replace_graph(
            version,
            {
                "nodes": [
                    {"id": "start", "name": "开始", "type": "start"},
                    {"id": "end", "name": "结束", "type": "end"},
                ],
                "edges": [{"id": "edge", "source": "start", "target": "end"}],
            },
        )
        request = APIRequestFactory().post(
            f"/api/v1/automation/workflow-versions/{version.id}/validate",
            {},
            format="json",
        )
        force_authenticate(request, user=user)

        response = WorkflowVersionViewSet.as_view({"post": "validate"})(
            request,
            pk=str(version.id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["data"]["valid"])
        self.assertIn("流程版本至少需要一个可执行任务节点", response.data["data"]["errors"])


class CommandVersionApiTests(TestCase):
    def test_command_cannot_be_enabled_without_published_version(self):
        from apps.automation.serializers import CommandAtomSerializer

        command = CommandAtom.objects.create(
            name="Unpublished script", code="unpublished_script"
        )
        serializer = CommandAtomSerializer(
            command, data={"status": "published"}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_publish_command_version(self):
        from apps.automation.views import CommandVersionViewSet

        user = get_user_model().objects.create_superuser(
            username="admin",
            password="123456",
            email="admin@example.com",
            phone="13800000000",
        )
        command = CommandAtom.objects.create(
            name="Check disk",
            code="check_disk",
            category="system",
            risk_level=CommandAtom.RiskLevel.LOW,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="df -h",
        )
        request = APIRequestFactory().post(
            f"/api/v1/automation/command-versions/{version.id}/publish"
        )
        force_authenticate(request, user=user)
        response = CommandVersionViewSet.as_view({"post": "publish"})(
            request,
            pk=str(version.id),
        )

        version.refresh_from_db()
        command.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(version.status, CommandVersion.Status.PUBLISHED)
        self.assertEqual(command.status, CommandAtom.Status.PUBLISHED)

    def test_publishing_new_version_does_not_enable_disabled_command(self):
        from apps.automation.views import CommandVersionViewSet

        user = get_user_model().objects.create_superuser(
            username="disabled-command-admin",
            password="123456",
            email="disabled-command-admin@example.com",
            phone="13800000003",
        )
        command = CommandAtom.objects.create(
            name="Disabled script",
            code="disabled_script_version_test",
            status=CommandAtom.Status.DISABLED,
        )
        version = CommandVersion.objects.create(
            command=command,
            version=1,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="echo ready",
        )
        request = APIRequestFactory().post(
            f"/api/v1/automation/command-versions/{version.id}/publish"
        )
        force_authenticate(request, user=user)

        response = CommandVersionViewSet.as_view({"post": "publish"})(
            request,
            pk=str(version.id),
        )

        command.refresh_from_db()
        version.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(version.status, CommandVersion.Status.PUBLISHED)
        self.assertEqual(command.status, CommandAtom.Status.DISABLED)


class AutomationTemplateApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="template-admin",
            password="123456",
            email="template-admin@example.com",
            phone="13800000002",
        )
        self.client.force_authenticate(self.user)

    def _create_command(
        self,
        code,
        parent_status,
        version_status,
        resource_kind=CommandAtom.ResourceKind.COMMAND,
    ):
        command = CommandAtom.objects.create(
            name=code.replace("_", " ").title(),
            code=code,
            status=parent_status,
            resource_kind=resource_kind,
        )
        return CommandVersion.objects.create(
            command=command,
            version=1,
            status=version_status,
            command_type=CommandVersion.CommandType.LINUX_SHELL,
            content="uname -a",
        )

    def _create_workflow(self, code, parent_status, version_status):
        workflow = WorkflowTemplate.objects.create(
            name=code.replace("_", " ").title(),
            code=code,
            status=parent_status,
        )
        return WorkflowVersion.objects.create(
            workflow=workflow,
            version=1,
            status=version_status,
        )

    def test_published_version_options_exclude_unenabled_templates(self):
        enabled = self._create_workflow(
            "enabled_workflow",
            WorkflowTemplate.Status.PUBLISHED,
            WorkflowVersion.Status.PUBLISHED,
        )
        self._create_workflow(
            "draft_workflow",
            WorkflowTemplate.Status.DRAFT,
            WorkflowVersion.Status.PUBLISHED,
        )
        self._create_workflow(
            "disabled_workflow",
            WorkflowTemplate.Status.DISABLED,
            WorkflowVersion.Status.PUBLISHED,
        )

        response = self.client.get(
            "/api/v1/automation/workflow-versions",
            {"status": "published", "workflow__status": "published"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["data"]],
            [enabled.id],
        )

    def test_template_list_returns_published_command_and_workflow_versions(self):
        self._create_command(
            "published_command",
            CommandAtom.Status.PUBLISHED,
            CommandVersion.Status.PUBLISHED,
        )
        self._create_workflow(
            "published_workflow",
            WorkflowTemplate.Status.PUBLISHED,
            WorkflowVersion.Status.PUBLISHED,
        )

        response = self.client.get("/api/v1/automation/templates")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "00000")
        self.assertEqual(
            {item["templateType"] for item in response.data["data"]},
            {"command", "workflow"},
        )
        self.assertTrue(
            all(item["versionStatus"] == "published" for item in response.data["data"])
        )

    def test_template_list_filters_type_and_excludes_disabled_or_unpublished_templates(
        self,
    ):
        included = self._create_command(
            "included_command",
            CommandAtom.Status.PUBLISHED,
            CommandVersion.Status.PUBLISHED,
        )
        self._create_command(
            "disabled_command",
            CommandAtom.Status.DISABLED,
            CommandVersion.Status.PUBLISHED,
        )
        self._create_command(
            "draft_version",
            CommandAtom.Status.PUBLISHED,
            CommandVersion.Status.DRAFT,
        )
        self._create_workflow(
            "published_workflow",
            WorkflowTemplate.Status.PUBLISHED,
            WorkflowVersion.Status.PUBLISHED,
        )

        response = self.client.get("/api/v1/automation/templates?type=command")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["id"], included.id)
        self.assertEqual(response.data["data"][0]["templateType"], "command")

    def test_template_list_filters_ansible_resource_kind(self):
        command = self._create_command(
            "published_command_kind",
            CommandAtom.Status.PUBLISHED,
            CommandVersion.Status.PUBLISHED,
        )
        script = self._create_command(
            "published_script_kind",
            CommandAtom.Status.PUBLISHED,
            CommandVersion.Status.PUBLISHED,
            CommandAtom.ResourceKind.SCRIPT,
        )

        response = self.client.get(
            "/api/v1/automation/templates?type=command&resource_kind=script"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["data"]], [script.id])
        self.assertEqual(response.data["data"][0]["resourceKind"], "script")
        self.assertNotEqual(command.id, script.id)


class NodeResourceCatalogApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="resource-admin",
            password="123456",
            email="resource-admin@example.com",
            phone="13800000008",
        )
        self.client.force_authenticate(self.user)

    def test_create_ansible_resource_creates_first_published_version(self):
        response = self.client.post(
            "/api/v1/automation/node-resources",
            {
                "resourceKind": "playbook",
                "name": "Deploy nginx",
                "code": "deploy_nginx",
                "category": "release",
                "riskLevel": "medium",
                "description": "Deploy nginx configuration",
                "commandType": "playbook",
                "content": "- hosts: all\n  tasks: []",
                "argumentSchema": {"environment": {"type": "string", "required": True}},
                "defaultVars": {"environment": "test"},
                "timeoutSeconds": 600,
                "becomeEnabled": True,
                "checkModeSupported": True,
                "publish": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        command = CommandAtom.objects.get(code="deploy_nginx")
        version = command.versions.get()
        self.assertEqual(command.resource_kind, CommandAtom.ResourceKind.PLAYBOOK)
        self.assertEqual(command.status, CommandAtom.Status.PUBLISHED)
        self.assertEqual(version.status, CommandVersion.Status.PUBLISHED)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.timeout_seconds, 600)
        self.assertEqual(response.data["data"]["resource"]["id"], command.id)
        self.assertEqual(response.data["data"]["version"]["id"], version.id)

    def test_catalog_returns_only_usable_resources_for_selected_node_type(self):
        published = CommandAtom.objects.create(
            name="Published module",
            code="published_module",
            resource_kind=CommandAtom.ResourceKind.MODULE,
            status=CommandAtom.Status.PUBLISHED,
        )
        published_version = CommandVersion.objects.create(
            command=published,
            version=1,
            status=CommandVersion.Status.PUBLISHED,
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content="ansible.builtin.service",
        )
        draft = CommandAtom.objects.create(
            name="Draft module",
            code="draft_module",
            resource_kind=CommandAtom.ResourceKind.MODULE,
            status=CommandAtom.Status.DRAFT,
        )
        CommandVersion.objects.create(
            command=draft,
            version=1,
            status=CommandVersion.Status.DRAFT,
            command_type=CommandVersion.CommandType.ANSIBLE_MODULE,
            content="ansible.builtin.command",
        )

        response = self.client.get("/api/v1/automation/node-resources?node_type=module")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["data"]["resources"]],
            [published_version.id],
        )
        module_type = next(
            item
            for item in response.data["data"]["types"]
            if item["nodeType"] == "module"
        )
        self.assertEqual(module_type["resourceCount"], 1)
        self.assertEqual(module_type["resourceType"], "command_version")
