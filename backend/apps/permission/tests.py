from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.permission.models import (
    CasbinRule,
    DictItem,
    DictType,
    Menu,
    MenuButton,
    Permission,
    PermissionAccessLog,
    PermissionAuditLog,
    Role,
    SystemConfig,
)
from apps.permission.seed_data import (
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_AUDITOR,
    seed_system_settings,
)
from apps.permission.serializers import MenuSerializer, RoleSerializer
from common.auth.rbac import verify_permission
from apps.permission.services import build_policy_rows
from apps.permission.views.menu import MenuViewSet
from apps.permission.views.role import RoleViewSet


class PermissionModelTests(TestCase):
    def test_role_permission_helpers(self):
        role = Role.objects.create(name="ops")
        api_permission = Permission.objects.create(
            name="View users",
            code="user.view",
            type=Permission.PermissionType.API,
            path="/api/v1/user/user-profile/",
            method="GET",
        )
        menu_permission = Permission.objects.create(
            name="User menu",
            code="menu.user.view",
            type=Permission.PermissionType.MENU,
            path="/user",
            method="GET",
        )
        role.permission.add(api_permission, menu_permission)

        self.assertEqual(list(role.get_api_permissions()), [api_permission])
        self.assertEqual(list(role.get_menu_permissions()), [menu_permission])

    def test_build_policy_rows_uses_permission_only(self):
        user = get_user_model().objects.create_user(
            username="tester",
            password="123456",
            email="tester@example.com",
            phone="13800000000",
        )
        role = Role.objects.create(name="ops")
        permission = Permission.objects.create(
            name="View users",
            code="user.view",
            type=Permission.PermissionType.API,
            path="/api/v1/user/user-profile/",
            method="GET",
        )
        user.role.add(role)
        role.permission.add(permission)

        rows = build_policy_rows()
        self.assertIn(
            {
                "ptype": "g",
                "v0": "tester",
                "v1": "ops",
                "v2": None,
                "v3": None,
                "v4": None,
                "v5": None,
            },
            rows,
        )
        self.assertIn(
            {
                "ptype": "p",
                "v0": "ops",
                "v1": "/api/v1/user/user-profile/",
                "v2": "GET",
                "v3": None,
                "v4": None,
                "v5": None,
            },
            rows,
        )


class MenuVisibilityTests(TestCase):
    def test_menu_effective_permissions(self):
        menu = Menu.objects.create(path="/settings", order=1, title="系统设置")
        permission = Permission.objects.create(
            name="System menu",
            code="menu.settings.view",
            type=Permission.PermissionType.MENU,
            path="/settings",
            method="GET",
        )
        menu.permission.add(permission)

        self.assertEqual(list(menu.get_effective_permissions()), [permission])

    def test_menu_serializer_defaults_icon_visibility_to_false(self):
        menu = Menu.objects.create(
            path="/ops",
            order=1,
            title="运维管理",
            icon="server",
        )

        self.assertFalse(MenuSerializer(menu).data["showIcon"])


class PermissionAuditLogTests(TestCase):
    def test_create_permission_generates_audit_log(self):
        Permission.objects.create(
            name="View users",
            code="user.view",
            type=Permission.PermissionType.API,
            path="/api/v1/user/user-profile/",
            method="GET",
        )

        log = PermissionAuditLog.objects.latest("id")
        self.assertEqual(log.action, PermissionAuditLog.Action.CREATED)
        self.assertEqual(log.target_type, "permission.Permission")

    def test_role_permission_relation_generates_audit_log(self):
        role = Role.objects.create(name="ops")
        permission = Permission.objects.create(
            name="View users",
            code="user.view",
            type=Permission.PermissionType.API,
            path="/api/v1/user/user-profile/",
            method="GET",
        )

        role.permission.add(permission)

        log = PermissionAuditLog.objects.filter(
            action=PermissionAuditLog.Action.RELATION_ADDED,
            target_type="apps.permission.Role.permission",
        ).latest("id")
        self.assertEqual(log.changes["permission_ids"], [permission.id])


class PermissionAccessLogTests(TestCase):
    def test_denied_permission_is_logged(self):
        user = get_user_model().objects.create_user(
            username="blocked",
            password="123456",
            email="blocked@example.com",
            phone="13800000001",
        )

        allowed, reason = verify_permission(user, "/api/v1/user/user-profile/", "GET")
        self.assertFalse(allowed)
        self.assertEqual(reason, "casbin_policy_denied")

        from apps.permission.audit import create_access_log

        create_access_log(
            user=user,
            path="/api/v1/user/user-profile/",
            method="GET",
            reason=reason,
        )
        log = PermissionAccessLog.objects.latest("id")
        self.assertEqual(log.status, PermissionAccessLog.Status.DENIED)
        self.assertEqual(log.actor_name, "blocked")


class BuiltInProtectionTests(TestCase):
    def test_system_role_cannot_be_deleted(self):
        role = Role.objects.create(name="system_admin", is_system=True)
        with self.assertRaises(Exception):
            role.delete()


class SeedSystemSettingsTests(TestCase):
    def test_seed_converts_legacy_menu_permissions_to_buttons_in_place(self):
        role = Role.objects.create(name="legacy_operator")
        legacy_create = Permission.objects.create(
            name="用户新增",
            code="sys:user:create",
            type=Permission.PermissionType.MENU,
            path="/system/user/create",
            method="GET",
        )
        legacy_import = Permission.objects.create(
            name="用户导入",
            code="sys:user:import",
            type=Permission.PermissionType.MENU,
            path="/system/user/import",
            method="GET",
        )
        role.permission.add(legacy_create, legacy_import)

        seed_system_settings(bind_superusers=False)

        legacy_create.refresh_from_db()
        legacy_import.refresh_from_db()
        self.assertEqual(legacy_create.type, Permission.PermissionType.BUTTON)
        self.assertEqual(legacy_import.type, Permission.PermissionType.BUTTON)
        self.assertIsNone(legacy_create.path)
        self.assertIsNone(legacy_create.method)
        self.assertIsNone(legacy_import.path)
        self.assertIsNone(legacy_import.method)
        self.assertEqual(
            set(role.permission.values_list("id", flat=True)),
            {legacy_create.id, legacy_import.id},
        )

        create_button = MenuButton.objects.get(code="sys:user:create")
        import_button = MenuButton.objects.get(code="sys:user:import")
        self.assertEqual(
            set(create_button.permission.values_list("code", flat=True)),
            {
                "sys:user:create",
                "template.user.create",
                "template.role.options",
                "template.dept.options",
            },
        )
        self.assertEqual(
            set(import_button.permission.values_list("code", flat=True)),
            {
                "sys:user:import",
                "template.user.import",
                "template.user.template",
            },
        )

    def test_seed_system_settings_creates_builtin_roles_permissions_and_menus(self):
        result = seed_system_settings(bind_superusers=False)

        self.assertGreater(result["api_permissions"], 0)
        self.assertGreater(result["menu_permissions"], 0)
        self.assertGreater(result["configs"], 0)
        self.assertGreater(result["dict_items"], 0)
        self.assertTrue(
            Role.objects.filter(name=SYSTEM_ROLE_ADMIN, is_system=True).exists()
        )
        self.assertTrue(
            Role.objects.filter(name=SYSTEM_ROLE_AUDITOR, is_system=True).exists()
        )
        self.assertTrue(
            Menu.objects.filter(
                title="系统管理",
                menu_group=Menu.MenuGroup.SYSTEM,
            ).exists()
        )
        self.assertTrue(
            Menu.objects.filter(
                title="用户管理",
                menu_group=Menu.MenuGroup.SYSTEM,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="sys:user:create",
                type=Permission.PermissionType.BUTTON,
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="sys:user:import",
                type=Permission.PermissionType.BUTTON,
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="template.user.export",
                type=Permission.PermissionType.API,
                path="/api/v1/users/export",
                method="GET",
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="permission.permission.options",
                type=Permission.PermissionType.API,
                path="/api/v1/permissions/options",
                method="GET",
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="file.upload",
                type=Permission.PermissionType.API,
                path="/api/v1/files",
                method="POST",
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="file.delete",
                type=Permission.PermissionType.API,
                path="/api/v1/files",
                method="DELETE",
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="menu.system.root",
                type=Permission.PermissionType.MENU,
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            Permission.objects.filter(
                code="menu.system.menu",
                type=Permission.PermissionType.MENU,
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            SystemConfig.objects.filter(
                config_key="log.operation.enabled",
                is_system=True,
            ).exists()
        )
        self.assertTrue(
            DictType.objects.filter(
                dict_code="gender",
            ).exists()
        )
        self.assertTrue(
            DictItem.objects.filter(
                dict_type__dict_code="gender",
                value="1",
                label="男",
            ).exists()
        )
        self.assertGreater(CasbinRule.objects.count(), 0)

    def test_seed_system_settings_creates_button_menu_nodes(self):
        seed_system_settings(bind_superusers=False)
        user_menu = Menu.objects.get(name="User")
        create_button = MenuButton.objects.get(
            menu=user_menu,
            code="sys:user:create",
        )
        import_button = MenuButton.objects.get(
            menu=user_menu,
            code="sys:user:import",
        )

        create_codes = set(create_button.permission.values_list("code", flat=True))
        import_codes = set(import_button.permission.values_list("code", flat=True))

        self.assertIn("sys:user:create", create_codes)
        self.assertIn("template.user.create", create_codes)
        self.assertIn("sys:user:import", import_codes)
        self.assertIn("template.user.import", import_codes)
        self.assertIn("template.user.template", import_codes)

        # 按钮不再是菜单子节点：用户管理菜单不再有子菜单行
        self.assertFalse(
            Menu.objects.filter(pid=user_menu).exists(),
            "buttons must not be stored as child menu rows",
        )
        serializer_buttons = MenuSerializer(user_menu).data["buttons"]
        create_button = next(
            button for button in serializer_buttons if button["code"] == "sys:user:create"
        )
        self.assertEqual(create_button["desc"], "用户新增")
        self.assertIn("id", create_button)

    def test_seed_system_settings_is_idempotent(self):
        seed_system_settings(bind_superusers=False)
        first_counts = (
            Role.objects.count(),
            Permission.objects.count(),
            Menu.objects.count(),
            SystemConfig.objects.count(),
            DictType.objects.count(),
            DictItem.objects.count(),
            CasbinRule.objects.count(),
        )

        seed_system_settings(bind_superusers=False)
        second_counts = (
            Role.objects.count(),
            Permission.objects.count(),
            Menu.objects.count(),
            SystemConfig.objects.count(),
            DictType.objects.count(),
            DictItem.objects.count(),
            CasbinRule.objects.count(),
        )

        self.assertEqual(first_counts, second_counts)

    def test_reseed_migrates_legacy_job_menu_role_grants(self):
        legacy_grants = {
            "automation.command:read": (
                "menu.jobs.command",
                "/api/v1/automation/templates",
            ),
            "automation.workflow:read": (
                "menu.jobs.workflow",
                "/api/v1/automation/workflows",
            ),
            "jobs.workflow_run:read": (
                "menu.jobs.run",
                "/api/v1/tasks/runs",
            ),
            "jobs.event:read": (
                "menu.jobs.run",
                "/api/v1/jobs/audit",
            ),
        }
        reused_button_codes = {
            "automation.command:read",
            "automation.workflow:read",
            "jobs.workflow_run:read",
        }
        actors = {}
        for index, legacy_code in enumerate(legacy_grants):
            username = f"legacy_job_operator_{index}"
            user = get_user_model().objects.create_user(username=username)
            role = Role.objects.create(name=username)
            user.role.add(role)
            legacy_permission = Permission.objects.create(
                name=legacy_code,
                code=legacy_code,
                type=Permission.PermissionType.MENU,
                is_system=True,
            )
            role.permission.add(legacy_permission)
            actors[legacy_code] = (user, role, legacy_permission.id)

        seed_system_settings(bind_superusers=False)

        for legacy_code, (replacement_code, path) in legacy_grants.items():
            user, role, legacy_permission_id = actors[legacy_code]
            role.refresh_from_db()
            role_codes = set(role.permission.values_list("code", flat=True))
            self.assertIn(replacement_code, role_codes)
            if legacy_code in reused_button_codes:
                self.assertIn(legacy_code, role_codes)
                converted_permission = Permission.objects.get(code=legacy_code)
                self.assertEqual(converted_permission.id, legacy_permission_id)
                self.assertEqual(
                    converted_permission.type,
                    Permission.PermissionType.BUTTON,
                )
            else:
                self.assertNotIn(legacy_code, role_codes)
                self.assertFalse(Permission.objects.filter(code=legacy_code).exists())
            allowed, reason = verify_permission(user, path, "GET")
            self.assertTrue(allowed, reason)

    def test_system_log_menu_binds_related_api_permissions(self):
        seed_system_settings(bind_superusers=False)
        log_menu = Menu.objects.get(name="Log")

        codes = set(
            log_menu.permission.filter(type=Permission.PermissionType.API).values_list(
                "code",
                flat=True,
            )
        )

        self.assertIn("logs.list", codes)
        self.assertIn("logs.analytics.overview", codes)
        self.assertIn("logs.analytics.trend", codes)

    def test_cmdb_host_menu_binds_read_apis_and_buttons_bind_write_apis(self):
        seed_system_settings(bind_superusers=False)
        host_menu = Menu.objects.get(name="CmdbHost")
        menu_codes = set(host_menu.permission.values_list("code", flat=True))

        self.assertIn("cmdb.host:read", menu_codes)
        self.assertIn("cmdb.host.list", menu_codes)
        self.assertIn("cmdb.host.detail", menu_codes)
        self.assertIn("jobs.worker_pool.list", menu_codes)
        self.assertNotIn("cmdb.host.create", menu_codes)
        self.assertNotIn("cmdb.host.delete", menu_codes)

        create_button = MenuButton.objects.get(code="cmdb.host:create")
        create_codes = set(create_button.permission.values_list("code", flat=True))
        self.assertIn("cmdb.host:create", create_codes)
        self.assertIn("cmdb.host.create", create_codes)

        delete_button = MenuButton.objects.get(code="cmdb.host:delete")
        delete_codes = set(delete_button.permission.values_list("code", flat=True))
        self.assertIn("cmdb.host:delete", delete_codes)
        self.assertIn("cmdb.host.delete", delete_codes)

    def test_automation_and_jobs_menus_bind_expected_api_permissions(self):
        seed_system_settings(bind_superusers=False)

        command_menu = Menu.objects.get(permission__code="menu.jobs.command")
        command_codes = set(command_menu.permission.values_list("code", flat=True))
        self.assertIn("menu.jobs.command", command_codes)
        self.assertIn("automation.command.list", command_codes)
        self.assertIn("automation.command_version.list", command_codes)
        self.assertNotIn("automation.command.create", command_codes)

        command_publish = MenuButton.objects.get(code="automation.command:publish")
        command_publish_codes = set(
            command_publish.permission.values_list("code", flat=True)
        )
        self.assertIn("automation.command:publish", command_publish_codes)
        self.assertIn("automation.command_version.publish", command_publish_codes)

        workflow_menu = Menu.objects.get(permission__code="menu.jobs.workflow")
        workflow_codes = set(workflow_menu.permission.values_list("code", flat=True))
        self.assertIn("automation.workflow.list", workflow_codes)
        self.assertIn("automation.workflow_node.list", workflow_codes)
        self.assertNotIn("jobs.workflow_run.create", workflow_codes)

        workflow_execute = MenuButton.objects.get(code="automation.workflow:execute")
        workflow_execute_codes = set(
            workflow_execute.permission.values_list("code", flat=True)
        )
        self.assertIn("automation.workflow:execute", workflow_execute_codes)
        self.assertIn("jobs.workflow_run.create", workflow_execute_codes)
        self.assertIn("automation.workflow_version.list", workflow_execute_codes)
        self.assertIn("cmdb.host.list", workflow_execute_codes)

        workflow_update = MenuButton.objects.get(code="automation.workflow:update")
        workflow_update_codes = set(
            workflow_update.permission.values_list("code", flat=True)
        )
        self.assertIn("automation.workflow_node.list", workflow_update_codes)
        self.assertIn("automation.workflow_node.create", workflow_update_codes)
        self.assertIn("automation.command_version.list", workflow_update_codes)

        job_menu = Menu.objects.get(permission__code="menu.jobs.run")
        job_codes = set(job_menu.permission.values_list("code", flat=True))
        self.assertIn("menu.jobs.run", job_codes)
        self.assertIn("jobs.workflow_run.list", job_codes)
        self.assertIn("jobs.workflow_run.nodes", job_codes)
        self.assertIn("jobs.workflow_run.log", job_codes)
        self.assertNotIn("jobs.workflow_run.cancel", job_codes)

        stream_permission = Permission.objects.get(code="jobs.workflow_run.log")
        self.assertEqual(
            stream_permission.path,
            "/api/v1/tasks/runs/:id/log",
        )
        self.assertEqual(stream_permission.method, "GET")

        self.assertIn("jobs.event.list", job_codes)
        self.assertNotIn("audit.event.list", job_codes)

        cancel_button = MenuButton.objects.get(code="jobs.workflow_run:cancel")
        cancel_codes = set(cancel_button.permission.values_list("code", flat=True))
        self.assertIn("jobs.workflow_run:cancel", cancel_codes)
        self.assertIn("jobs.workflow_run.cancel", cancel_codes)

    def test_job_center_menus_bind_template_and_execution_api_permissions(self):
        seed_system_settings(bind_superusers=False)

        expected_types = {
            "menu.jobs.quick_command": Menu.MenuType.MENU,
            "menu.jobs.command": Menu.MenuType.MENU,
            "menu.jobs.workflow": Menu.MenuType.MENU,
            "menu.jobs.run": Menu.MenuType.MENU,
        }
        menus = {}
        for code, menu_type in expected_types.items():
            menu = Menu.objects.get(permission__code=code)
            self.assertEqual(menu.menu_type, menu_type)
            self.assertEqual(menu.pid.menu_type, Menu.MenuType.CATALOG)
            menus[code] = menu

        quick_codes = set(
            menus["menu.jobs.quick_command"].permission.values_list("code", flat=True)
        )
        self.assertIn("automation.template.list", quick_codes)
        self.assertNotIn("jobs.quick_command.create", quick_codes)

        workflow_codes = set(
            menus["menu.jobs.workflow"].permission.values_list("code", flat=True)
        )
        self.assertIn("automation.workflow.list", workflow_codes)
        self.assertNotIn("jobs.workflow_run.create", workflow_codes)

        command_codes = set(
            menus["menu.jobs.command"].permission.values_list("code", flat=True)
        )
        self.assertIn("automation.command.list", command_codes)
        self.assertIn("automation.command_version.list", command_codes)

        run_codes = set(
            menus["menu.jobs.run"].permission.values_list("code", flat=True)
        )
        self.assertIn("jobs.workflow_run.list", run_codes)
        self.assertIn("jobs.workflow_run.log", run_codes)

        read_button = MenuButton.objects.get(code="jobs.workflow_run:read")
        self.assertEqual(read_button.menu, menus["menu.jobs.run"])
        self.assertIn(
            "jobs.workflow_run.list",
            read_button.permission.values_list("code", flat=True),
        )

        execute = MenuButton.objects.get(code="jobs.quick_command:execute")
        self.assertEqual(execute.menu, menus["menu.jobs.quick_command"])
        self.assertIn(
            "jobs.quick_command.create",
            execute.permission.values_list("code", flat=True),
        )
        self.assertIn(
            "automation.command_version.detail",
            execute.permission.values_list("code", flat=True),
        )

        for code, api_code in (
            ("jobs.workflow_run:cancel", "jobs.workflow_run.cancel"),
            ("jobs.workflow_run:retry", "jobs.workflow_run.retry_failed"),
        ):
            button = MenuButton.objects.get(code=code)
            self.assertEqual(button.menu, menus["menu.jobs.run"])
            self.assertIn(api_code, button.permission.values_list("code", flat=True))

    def test_job_center_menu_permissions_expand_to_role_api_permissions(self):
        seed_system_settings(bind_superusers=False)
        role = Role.objects.create(name="job_center_operator")
        role.permission.add(
            Permission.objects.get(code="menu.jobs.quick_command"),
            Permission.objects.get(code="jobs.quick_command:execute"),
        )
        execute_button = MenuButton.objects.get(code="jobs.quick_command:execute")
        role.permission.add(*execute_button.get_effective_permissions())

        api_codes = set(role.get_api_permissions().values_list("code", flat=True))
        self.assertIn("automation.template.list", api_codes)
        self.assertIn("jobs.quick_command.create", api_codes)
        self.assertIn("automation.command_version.detail", api_codes)

    def test_task_flow_designer_menu_binds_designer_and_resource_permissions(self):
        seed_system_settings(bind_superusers=False)

        flow_menu = Menu.objects.get(permission__code="menu.task.flow_design")
        flow_codes = set(flow_menu.permission.values_list("code", flat=True))

        self.assertIn("automation.workflow_version.list", flow_codes)
        self.assertIn("automation.workflow_version.graph", flow_codes)
        self.assertIn("automation.template.list", flow_codes)
        self.assertIn("automation.api_endpoint.list", flow_codes)
        self.assertIn("automation.jenkins_server.jobs", flow_codes)
        self.assertIn("automation.notification_channel.list", flow_codes)

        execution_menu = Menu.objects.get(permission__code="menu.task.execution")
        execution_codes = set(execution_menu.permission.values_list("code", flat=True))
        self.assertIn("automation.workflow_version.graph", execution_codes)

    def test_job_workflow_menu_uses_existing_workflow_management_component(self):
        seed_system_settings(bind_superusers=False)

        workflow_menu = Menu.objects.get(permission__code="menu.jobs.workflow")

        self.assertEqual(workflow_menu.component, "automation/workflow/index")


class RoleMenuAssignmentTests(TestCase):
    def setUp(self):
        seed_system_settings(bind_superusers=False)
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            password="123456",
            email="admin@example.com",
            phone="13800000000",
        )
        self.role = Role.objects.create(name="config_operator")
        self.config_menu = Menu.objects.get(name="Config")
        self.create_button = MenuButton.objects.get(
            menu=self.config_menu,
            code="sys:config:create",
        )
        self.update_button = MenuButton.objects.get(
            menu=self.config_menu,
            code="sys:config:update",
        )
        self.delete_button = MenuButton.objects.get(
            menu=self.config_menu,
            code="sys:config:delete",
        )
        self.refresh_button = MenuButton.objects.get(
            menu=self.config_menu,
            code="sys:config:refresh",
        )

    def _assign_menus(self, menu_ids=None, button_ids=None, home_path=None):
        factory = APIRequestFactory()
        payload = {"menuIds": [str(menu_id) for menu_id in (menu_ids or [])]}
        if button_ids is not None:
            payload["buttonIds"] = [str(button_id) for button_id in button_ids]
        if home_path is not None:
            payload["homePath"] = home_path
        request = factory.put(
            f"/api/v1/roles/{self.role.id}/menus",
            payload,
            format="json",
        )
        force_authenticate(request, user=self.user)
        view = RoleViewSet.as_view({"put": "menus"})
        return view(request, pk=str(self.role.id))

    def _get_menu_ids(self):
        factory = APIRequestFactory()
        request = factory.get(f"/api/v1/roles/{self.role.id}/menu-ids")
        force_authenticate(request, user=self.user)
        view = RoleViewSet.as_view({"get": "menu_ids"})
        response = view(request, pk=str(self.role.id))
        return response.data["data"]

    def test_partial_button_assignment_does_not_grant_sibling_button_apis(self):
        response = self._assign_menus(button_ids=[self.create_button.id, self.update_button.id])
        self.assertEqual(response.status_code, 200)

        permission_codes = set(
            self.role.permission.order_by("code").values_list("code", flat=True)
        )

        self.assertIn("sys:config:create", permission_codes)
        self.assertIn("sys:config:update", permission_codes)
        self.assertIn("template.config.create", permission_codes)
        self.assertIn("template.config.update", permission_codes)
        self.assertNotIn("sys:config:delete", permission_codes)
        self.assertNotIn("sys:config:refresh", permission_codes)
        self.assertNotIn("template.config.delete", permission_codes)
        self.assertNotIn("template.config.refresh", permission_codes)

    def test_menu_id_echo_only_returns_selected_button_nodes(self):
        self._assign_menus(button_ids=[self.create_button.id, self.update_button.id])

        data = self._get_menu_ids()

        checked_menu_ids = set(data["menuIds"])
        checked_button_ids = set(data["buttonIds"])

        self.assertIn(str(self.create_button.id), checked_button_ids)
        self.assertIn(str(self.update_button.id), checked_button_ids)
        self.assertNotIn(str(self.delete_button.id), checked_button_ids)
        self.assertNotIn(str(self.refresh_button.id), checked_button_ids)
        self.assertNotIn(str(self.config_menu.id), checked_menu_ids)

    def test_selecting_menu_only_grants_read_page_apis_not_write_apis(self):
        response = self._assign_menus(menu_ids=[self.config_menu.id])
        self.assertEqual(response.status_code, 200)

        permission_codes = set(
            self.role.permission.order_by("code").values_list("code", flat=True)
        )

        self.assertIn("menu.system.config", permission_codes)
        self.assertIn("template.config.list", permission_codes)
        self.assertIn("template.config.detail", permission_codes)
        self.assertIn("template.config.snapshot", permission_codes)
        self.assertNotIn("template.config.create", permission_codes)
        self.assertNotIn("template.config.update", permission_codes)
        self.assertNotIn("template.config.delete", permission_codes)
        self.assertNotIn("template.config.refresh", permission_codes)

    def test_half_checked_parent_payload_does_not_grant_write_apis(self):
        response = self._assign_menus(
            menu_ids=[self.config_menu.id],
            button_ids=[self.create_button.id, self.update_button.id],
        )
        self.assertEqual(response.status_code, 200)

        permission_codes = set(
            self.role.permission.order_by("code").values_list("code", flat=True)
        )

        self.assertIn("menu.system.config", permission_codes)
        self.assertIn("sys:config:create", permission_codes)
        self.assertIn("sys:config:update", permission_codes)
        self.assertIn("template.config.list", permission_codes)
        self.assertIn("template.config.create", permission_codes)
        self.assertIn("template.config.update", permission_codes)
        self.assertNotIn("template.config.delete", permission_codes)
        self.assertNotIn("template.config.refresh", permission_codes)

    def test_echo_save_preserves_selected_parent_menu_read_apis(self):
        self._assign_menus(
            menu_ids=[self.config_menu.id],
            button_ids=[self.create_button.id, self.update_button.id],
        )

        echoed = self._get_menu_ids()
        response = self._assign_menus(
            menu_ids=echoed["menuIds"],
            button_ids=echoed["buttonIds"],
        )
        self.assertEqual(response.status_code, 200)

        permission_codes = set(
            self.role.permission.order_by("code").values_list("code", flat=True)
        )

        self.assertIn("menu.system.config", permission_codes)
        self.assertIn("template.config.list", permission_codes)
        self.assertIn("template.config.detail", permission_codes)
        self.assertIn("template.config.snapshot", permission_codes)
        self.assertIn("sys:config:create", permission_codes)
        self.assertIn("sys:config:update", permission_codes)
        self.assertNotIn("sys:config:delete", permission_codes)
        self.assertNotIn("sys:config:refresh", permission_codes)

    def test_casbin_policy_rows_only_include_selected_button_apis(self):
        user = get_user_model().objects.create_user(
            username="config-user",
            password="123456",
            email="config-user@example.com",
            phone="13800000001",
        )
        user.role.add(self.role)
        self._assign_menus(button_ids=[self.create_button.id, self.update_button.id])

        policy_rows = build_policy_rows()
        policies = {
            (row["v0"], row["v1"], row["v2"])
            for row in policy_rows
            if row["ptype"] == "p" and row["v0"] == self.role.name
        }

        self.assertIn(("config_operator", "/api/v1/configs", "POST"), policies)
        self.assertIn(
            ("config_operator", "/api/v1/configs/:id", "PUT|PATCH"),
            policies,
        )
        self.assertNotIn(
            ("config_operator", "/api/v1/configs/:id", "DELETE"),
            policies,
        )
        self.assertNotIn(
            ("config_operator", "/api/v1/configs/refresh", "PUT"),
            policies,
        )

    def test_role_assign_button_grants_menu_options_api(self):
        assign_button = MenuButton.objects.get(code="sys:role:assign")

        codes = set(assign_button.permission.values_list("code", flat=True))

        self.assertIn("sys:role:assign", codes)
        self.assertIn("template.role.menu_ids", codes)
        self.assertIn("template.role.menus", codes)
        self.assertIn("template.menu.options", codes)

    def test_user_create_update_buttons_grant_dialog_option_apis(self):
        for code in ("sys:user:create", "sys:user:update"):
            button = MenuButton.objects.get(code=code)
            codes = set(button.permission.values_list("code", flat=True))

            self.assertIn("template.role.options", codes)
            self.assertIn("template.dept.options", codes)

    def test_role_create_update_buttons_grant_dept_options_api(self):
        for code in ("sys:role:create", "sys:role:update"):
            button = MenuButton.objects.get(code=code)
            codes = set(button.permission.values_list("code", flat=True))

            self.assertIn("template.dept.options", codes)

    def test_repair_seed_menu_permissions_removes_stale_parent_write_api(self):
        from django.core.management import call_command

        stale_api = Permission.objects.get(code="template.config.delete")
        self.config_menu.permission.add(stale_api)

        self.assertIn(
            "template.config.delete",
            set(self.config_menu.permission.values_list("code", flat=True)),
        )

        call_command("repair_menu_data", "--sync-seed-permissions")
        self.config_menu.refresh_from_db()

        codes = set(self.config_menu.permission.values_list("code", flat=True))
        self.assertIn("menu.system.config", codes)
        self.assertIn("template.config.list", codes)
        self.assertNotIn("template.config.delete", codes)

    def test_role_assignment_persists_selected_api_policies_to_casbin_rules(self):
        self._assign_menus(button_ids=[self.create_button.id, self.update_button.id])

        policies = set(
            CasbinRule.objects.filter(ptype="p", v0=self.role.name).values_list(
                "v0",
                "v1",
                "v2",
            )
        )

        self.assertIn(("config_operator", "/api/v1/configs", "POST"), policies)
        self.assertIn(("config_operator", "/api/v1/configs/:id", "PUT|PATCH"), policies)
        self.assertNotIn(("config_operator", "/api/v1/configs/:id", "DELETE"), policies)
        self.assertNotIn(
            ("config_operator", "/api/v1/configs/refresh", "PUT"), policies
        )

    def test_assign_menus_persists_and_echoes_home_path(self):
        response = self._assign_menus(
            menu_ids=[self.config_menu.id],
            home_path="config",
        )
        self.assertEqual(response.status_code, 200)

        self.role.refresh_from_db()
        self.assertEqual(self.role.home_path, "config")

        data = self._get_menu_ids()
        self.assertEqual(data["homePath"], "config")

        # 清空首页
        response = self._assign_menus(menu_ids=[self.config_menu.id], home_path="")
        self.assertEqual(response.status_code, 200)
        self.role.refresh_from_db()
        self.assertIsNone(self.role.home_path)


class RoleFieldTests(TestCase):
    def test_seed_roles_carry_code_description_and_status(self):
        seed_system_settings(bind_superusers=False)

        admin_role = Role.objects.get(name=SYSTEM_ROLE_ADMIN)
        self.assertEqual(admin_role.code, "R_ADMIN")
        self.assertTrue(admin_role.is_active)
        self.assertTrue(admin_role.description)

        auditor_role = Role.objects.get(name=SYSTEM_ROLE_AUDITOR)
        self.assertEqual(auditor_role.code, "R_AUDITOR")
        self.assertTrue(auditor_role.is_active)

    def test_role_serializer_accepts_camel_case_payload(self):
        serializer = RoleSerializer(
            data={
                "roleName": "运维工程师",
                "roleCode": "R_OPS",
                "roleDesc": "运维岗位角色",
                "status": "2",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        role = serializer.save()
        self.assertEqual(role.name, "运维工程师")
        self.assertEqual(role.code, "R_OPS")
        self.assertEqual(role.description, "运维岗位角色")
        self.assertFalse(role.is_active)

        representation = RoleSerializer(role).data
        self.assertEqual(representation["roleName"], "运维工程师")
        self.assertEqual(representation["roleCode"], "R_OPS")
        self.assertEqual(representation["roleDesc"], "运维岗位角色")
        self.assertEqual(representation["status"], "2")

    def test_role_serializer_keeps_legacy_code_alias(self):
        serializer = RoleSerializer(data={"code": "legacy_role"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        role = serializer.save()
        self.assertEqual(role.name, "legacy_role")
        self.assertEqual(RoleSerializer(role).data["code"], "legacy_role")


class DynamicRouteTests(TestCase):
    def setUp(self):
        seed_system_settings(bind_superusers=False)
        self.user = get_user_model().objects.create_superuser(
            username="route-admin",
            password="123456",
            email="route-admin@example.com",
            phone="13800000000",
        )

    def _get_routes(self, user=None):
        factory = APIRequestFactory()
        request = factory.get("/api/v1/menus/routes")
        force_authenticate(request, user=user or self.user)
        view = MenuViewSet.as_view({"get": "routes"})
        response = view(request)
        return response.data["data"]

    def test_routes_response_matches_soybean_user_route_shape(self):
        data = self._get_routes()

        self.assertIn("routes", data)
        self.assertIn("home", data)
        self.assertEqual(data["home"], "home")

        # 种子根目录 route_name 为 "/system"
        system_route = next(
            route for route in data["routes"] if route["name"] == "/system"
        )
        # 旧数据 component="Layout" 归一化为 layout.base
        self.assertEqual(system_route["component"], "layout.base")
        self.assertEqual(system_route["path"], "/system")
        self.assertEqual(system_route["meta"]["title"], "系统管理")
        self.assertIn("order", system_route["meta"])

        user_route = next(
            child
            for child in system_route["children"]
            if child["name"] == "manage_user"
        )
        # 旧组件 system/user/index 映射为前端 manage_user 路由
        self.assertEqual(user_route["path"], "/manage/user")
        self.assertEqual(user_route["component"], "view.manage_user")
        self.assertEqual(user_route["meta"]["title"], "用户管理")
        # 按钮不再出现在路由树中
        self.assertNotIn("buttons", user_route)

    def test_routes_home_resolves_from_role_home_path(self):
        role = Role.objects.create(name="home_tester", home_path="config")
        self.user.role.add(role)

        data = self._get_routes()
        self.assertEqual(data["home"], "config")

    def test_routes_meta_carries_route_meta_fields(self):
        menu = Menu.objects.get(name="User")
        menu.i18n_key = "route.manage_user"
        menu.icon = "ic:round-manage-accounts"
        menu.icon_type = Menu.IconType.ICONIFY
        menu.multi_tab = True
        menu.fixed_index_in_tab = 2
        menu.query = [{"key": "id", "value": "1"}]
        menu.href = "https://example.com"
        menu.active_menu = "user_list"
        menu.save()

        data = self._get_routes()
        system_route = next(
            route for route in data["routes"] if route["name"] == "/system"
        )
        user_route = next(
            child for child in system_route["children"] if child["name"] == "manage_user"
        )
        meta = user_route["meta"]
        self.assertEqual(meta["i18nKey"], "route.manage_user")
        self.assertEqual(meta["icon"], "ic:round-manage-accounts")
        self.assertTrue(meta["multiTab"])
        self.assertEqual(meta["fixedIndexInTab"], 2)
        self.assertEqual(meta["query"], [{"key": "id", "value": "1"}])
        self.assertEqual(meta["href"], "https://example.com")
        self.assertEqual(meta["activeMenu"], "user_list")

    def test_routes_local_icon_uses_local_icon_meta(self):
        menu = Menu.objects.get(name="User")
        menu.icon = "logo"
        menu.icon_type = Menu.IconType.LOCAL
        menu.save()

        data = self._get_routes()
        system_route = next(
            route for route in data["routes"] if route["name"] == "/system"
        )
        user_route = next(
            child for child in system_route["children"] if child["name"] == "manage_user"
        )
        self.assertEqual(user_route["meta"]["localIcon"], "logo")
        self.assertNotIn("icon", user_route["meta"])

    def test_routes_drops_unmappable_legacy_components(self):
        # 前端无对应页面的旧组件（如 cmdb/host/index）应降级为无组件，避免动态路由解析失败
        data = self._get_routes()
        cmdb_route = next(
            route for route in data["routes"] if route["name"] == "Cmdb"
        )
        host_route = next(
            child for child in cmdb_route["children"] if child["name"] == "CmdbHost"
        )
        self.assertIsNone(host_route["component"])
        # 根目录 Layout 仍归一化为 layout.base
        self.assertEqual(cmdb_route["component"], "layout.base")

    def test_pages_action_returns_view_components(self):
        factory = APIRequestFactory()
        request = factory.get("/api/v1/menus/pages")
        force_authenticate(request, user=self.user)
        view = MenuViewSet.as_view({"get": "pages"})
        response = view(request)

        pages = response.data["data"]
        self.assertIsInstance(pages, list)
        self.assertIn("system/user/index", pages)
        # 目录组件（Layout/ParentView）不应出现在页面列表
        self.assertNotIn("Layout", pages)
        self.assertNotIn("ParentView", pages)


class MenuRouteMetaSerializerTests(TestCase):
    def test_menu_serializer_round_trips_route_meta_fields(self):
        serializer = MenuSerializer(
            data={
                "type": "M",
                "routeName": "MetaPage",
                "routePath": "meta-page",
                "title": "元信息页",
                "component": "view.meta-page",
                "sort": 3,
                "i18nKey": "route.meta-page",
                "icon": "logo",
                "iconType": "2",
                "multiTab": True,
                "fixedIndexInTab": 1,
                "query": [{"key": "tab", "value": "a"}],
                "href": "https://example.com",
                "constant": True,
                "status": "1",
                "hideInMenu": True,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        menu = serializer.save()

        self.assertEqual(menu.i18n_key, "route.meta-page")
        self.assertEqual(menu.icon_type, "2")
        self.assertTrue(menu.multi_tab)
        self.assertEqual(menu.fixed_index_in_tab, 1)
        self.assertEqual(menu.query, [{"key": "tab", "value": "a"}])
        self.assertEqual(menu.href, "https://example.com")
        self.assertTrue(menu.constant)
        self.assertTrue(menu.is_active)
        self.assertTrue(menu.hidden)

        representation = MenuSerializer(menu).data
        self.assertEqual(representation["i18nKey"], "route.meta-page")
        self.assertEqual(representation["iconType"], "2")
        self.assertTrue(representation["multiTab"])
        self.assertEqual(representation["fixedIndexInTab"], 1)
        self.assertEqual(representation["query"], [{"key": "tab", "value": "a"}])
        self.assertEqual(representation["href"], "https://example.com")
        self.assertTrue(representation["constant"])
        self.assertEqual(representation["status"], "1")
        self.assertTrue(representation["hideInMenu"])

    def test_menu_serializer_status_disable_maps_to_is_active_false(self):
        serializer = MenuSerializer(
            data={
                "type": "M",
                "routeName": "DisabledPage",
                "routePath": "disabled-page",
                "title": "停用页",
                "component": "view.disabled-page",
                "sort": 1,
                "status": "2",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        menu = serializer.save()
        self.assertFalse(menu.is_active)
        self.assertEqual(MenuSerializer(menu).data["status"], "2")
