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


class MenuLayoutSyncTests(TestCase):
    def test_layout_sync_preserves_custom_and_cleared_icons(self):
        from io import StringIO
        from django.core.management import call_command

        seed_system_settings(bind_superusers=False)
        config = Menu.objects.get(name="Config")
        user = Menu.objects.get(name="User")
        original_order = config.order
        config.icon = "custom-settings"
        config.icon_type = "2"
        config.show_icon = True
        config.order = 999
        config.save()
        user.icon = ""
        user.show_icon = False
        user.save()
        for _ in range(2):
            call_command(
                "init_system_settings",
                sync_menu_layout=True,
                skip_bind_superusers=True,
                stdout=StringIO(),
            )
        config.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(config.icon, "custom-settings")
        self.assertEqual(config.icon_type, "2")
        self.assertTrue(config.show_icon)
        self.assertEqual(config.order, original_order)
        self.assertEqual(user.icon, "")
        self.assertFalse(user.show_icon)


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
    def test_new_seed_does_not_create_removed_job_center_or_event_permissions(self):
        seed_system_settings(bind_superusers=False)
        self.assertFalse(Permission.objects.filter(code__startswith="menu.jobs.").exists())
        self.assertFalse(Permission.objects.filter(path__startswith="/api/v1/jobs/events").exists())

    def test_quick_execution_button_grants_creation_and_target_reads(self):
        seed_system_settings(bind_superusers=False)
        button = MenuButton.objects.get(code="jobs.quick_command:execute")
        self.assertEqual(button.menu.component, "view.ops_quick-execute_script")
        codes = set(button.permission.values_list("code", flat=True))
        self.assertTrue({"jobs.quick_command.create", "cmdb.host.list", "jobs.worker_pool.list"} <= codes)
        # 执行链路经 snapshot_targets/resolve_worker_pool，需补齐 detail 级权限
        self.assertTrue({"cmdb.host.detail", "cmdb.credential_ref.detail", "jobs.worker_pool.detail"} <= codes)

    def test_quick_execution_split_buttons_bind_run_creation_apis(self):
        seed_system_settings(bind_superusers=False)
        playbook = MenuButton.objects.get(code="jobs.playbook_run:execute")
        self.assertEqual(playbook.menu.component, "view.ops_quick-execute_playbook")
        self.assertIn(
            "jobs.playbook_run.create",
            playbook.permission.values_list("code", flat=True),
        )
        module = MenuButton.objects.get(code="jobs.module_run:execute")
        self.assertEqual(module.menu.component, "view.ops_quick-execute_module")
        self.assertIn(
            "jobs.module_run.create",
            module.permission.values_list("code", flat=True),
        )

    def test_run_read_buttons_bind_domain_specific_events_and_tickets(self):
        seed_system_settings(bind_superusers=False)
        for prefix, path in (("jobs", "tasks"), ("ops", "ops")):
            button = MenuButton.objects.get(code=f"{prefix}.workflow_run:read")
            codes = set(button.permission.values_list("code", flat=True))
            for action in ("detail", "events", "log", "realtime_ticket"):
                self.assertIn(f"{prefix}.workflow_run.{action}", codes)
            event = Permission.objects.get(code=f"{prefix}.workflow_run.events")
            self.assertEqual(event.path, f"/api/v1/{path}/runs/:id/events")
            self.assertNotIn(f"{prefix}.workflow_run.cancel", codes)

    def test_operator_role_expands_current_quick_execution_permissions(self):
        seed_system_settings(bind_superusers=False)
        role = Role.objects.create(name="current_quick_operator")
        button = MenuButton.objects.get(code="jobs.quick_command:execute")
        role.permission.add(*button.get_effective_permissions())
        self.assertIn("jobs.quick_command.create", role.get_api_permissions().values_list("code", flat=True))
        self.assertNotIn("audit.event.export", role.get_api_permissions().values_list("code", flat=True))

    def test_flow_designer_uses_notification_templates(self):
        seed_system_settings(bind_superusers=False)
        menu = Menu.objects.get(permission__code="menu.task.flow_design")
        codes = set(menu.permission.values_list("code", flat=True))
        self.assertTrue({"automation.workflow_version.graph", "automation.node_resource.list", "automation.notification_template.list"} <= codes)

    def test_task_list_and_execution_history_use_separate_menus(self):
        seed_system_settings(bind_superusers=False)
        task_list = Menu.objects.get(permission__code="menu.task.list")
        self.assertEqual(task_list.component, "view.task_run")
        self.assertFalse(task_list.buttons.filter(code="jobs.workflow_run:retry").exists())

        history_menu = Menu.objects.get(permission__code="menu.task.execution-history")
        self.assertEqual(history_menu.component, "view.task_execution-history")
        button = MenuButton.objects.get(code="jobs.workflow_run:retry", menu=history_menu)
        self.assertTrue({"jobs.workflow_run.retry_failed", "jobs.workflow_run.rerun", "jobs.node_run.retry"} <= set(button.permission.values_list("code", flat=True)))

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


    def test_operation_log_menu_moves_to_audit_and_binds_related_api_permissions(self):
        seed_system_settings(bind_superusers=False)
        log_menu = Menu.objects.get(name="Log")
        self.assertEqual(log_menu.pid.name, "Audit")
        self.assertEqual(log_menu.title, "操作日志")

        codes = set(
            log_menu.permission.filter(type=Permission.PermissionType.API).values_list(
                "code",
                flat=True,
            )
        )

        self.assertIn("logs.list", codes)
        self.assertIn("logs.analytics.overview", codes)
        self.assertIn("logs.analytics.trend", codes)
        login_menu = Menu.objects.get(name="audit_login")
        self.assertEqual(login_menu.pid.name, "Audit")
        self.assertIn(
            "audit.login_event.list",
            set(login_menu.permission.values_list("code", flat=True)),
        )

    def test_existing_system_log_role_keeps_operation_log_access_after_seed(self):
        legacy = Permission.objects.create(
            code="menu.system.log",
            name="旧系统日志菜单",
            type=Permission.PermissionType.MENU,
            is_system=True,
        )
        role = Role.objects.create(name="existing_log_reader")
        role.permission.add(legacy)

        seed_system_settings(bind_superusers=False)

        self.assertFalse(Permission.objects.filter(code="menu.system.log").exists())
        self.assertTrue(role.permission.filter(code="menu.audit.operations").exists())
        self.assertTrue(role.permission.filter(code="logs.list").exists())

    def test_cmdb_host_menu_binds_read_apis_and_buttons_bind_write_apis(self):
        seed_system_settings(bind_superusers=False)
        host_menu = Menu.objects.get(name="cmdb_host")
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

    def test_tag_button_merged_into_host_menu_and_source_owned(self):
        seed_system_settings(bind_superusers=False)
        host_menu = Menu.objects.get(name="cmdb_host")
        source_menu = Menu.objects.get(name="cmdb_source")

        # 标签管理菜单已移除，标签新建按钮并入主机资产菜单
        self.assertFalse(Menu.objects.filter(name="cmdb_tag").exists())
        self.assertEqual(MenuButton.objects.get(code="cmdb.tag:create").menu, host_menu)
        self.assertEqual(MenuButton.objects.get(code="cmdb.asset_source:sync").menu, source_menu)
        self.assertFalse(
            MenuButton.objects.filter(code__in=("cmdb.tag:update", "cmdb.tag:delete")).exists()
        )
        self.assertFalse(Permission.objects.filter(code__in=("cmdb.tag:update", "cmdb.tag:delete")).exists())
        self.assertIn(
            "cmdb.asset_sync_record.list",
            set(source_menu.permission.values_list("code", flat=True)),
        )

        # 旧库残留的标签编辑按钮权限在重播种后被清理
        Permission.objects.create(
            code="cmdb.tag:update",
            name="标签编辑",
            type=Permission.PermissionType.BUTTON,
            is_system=True,
        )
        seed_system_settings(bind_superusers=False)
        self.assertFalse(Permission.objects.filter(code="cmdb.tag:update").exists())
        self.assertEqual(MenuButton.objects.get(code="cmdb.tag:create").menu, host_menu)

    def test_existing_cmdb_button_role_keeps_permissions(self):
        tag_write = Permission.objects.create(
            code="cmdb.tag:create",
            name="标签新增",
            type=Permission.PermissionType.BUTTON,
            is_system=True,
        )
        source_write = Permission.objects.create(
            code="cmdb.asset_source:sync",
            name="来源同步",
            type=Permission.PermissionType.BUTTON,
            is_system=True,
        )
        role = Role.objects.create(name="cmdb_editor")
        role.permission.add(tag_write, source_write)

        seed_system_settings(bind_superusers=False)

        codes = set(role.permission.values_list("code", flat=True))
        # 标签新建权限保留（标签创建已并入主机表单）
        self.assertIn("cmdb.tag:create", codes)
        self.assertIn("cmdb.asset_source:read", codes)
        self.assertIn("cmdb.asset_sync_record.list", codes)







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
    def test_menu_repair_preserves_ids_icons_and_real_links(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps

        config = Menu.objects.get(component="system/config/index")
        config.icon = "carbon:settings-edit"
        config.href = config.icon
        config.save(update_fields=["icon", "href"])
        user = Menu.objects.get(component="system/user/index")
        user.path = "/User"
        user.href = "https://example.com/docs"
        user.save(update_fields=["path", "href"])
        permission_ids = list(user.permission.values_list("id", flat=True))
        repair = import_module("apps.permission.migrations.0005_repair_menu_icon_links")
        editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        repair.repair_menu_data(apps, editor)
        repair.repair_menu_data(apps, editor)
        config.refresh_from_db()
        user.refresh_from_db()
        self.assertIsNone(config.href)
        self.assertEqual(config.icon, "carbon:settings-edit")
        self.assertEqual(user.path, "user")
        self.assertEqual(user.href, "https://example.com/docs")
        self.assertEqual(list(user.permission.values_list("id", flat=True)), permission_ids)

    def test_icon_value_in_external_link_does_not_override_config_navigation(self):
        menu = Menu.objects.get(component="system/config/index")
        menu.icon = "carbon:settings-edit"
        menu.href = menu.icon
        menu.save(update_fields=["icon", "href"])
        system = next(r for r in self._get_routes()["routes"] if r["name"] == "system")
        config = next(r for r in system["children"] if r["name"] == "manage_config")
        self.assertEqual(config["path"], "/manage/config")
        self.assertNotIn("href", config["meta"])

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

    def test_execution_detail_preserves_generated_name_and_identifier_path(self):
        data = self._get_routes()
        task = next(route for route in data["routes"] if route["path"] == "/task")
        detail = next(route for route in task["children"] if route["component"] == "view.task_run-detail")
        self.assertEqual(detail["name"], "task_run-detail")
        self.assertEqual(detail["path"], "/task/run-detail/:id")
        self.assertTrue(detail["meta"]["hideInMenu"])

        ops = next(route for route in data["routes"] if route["path"] == "/ops")
        ops_detail = next(route for route in ops["children"] if route["component"] == "view.ops_run-detail")
        self.assertEqual(ops_detail["name"], "ops_run-detail")
        self.assertEqual(ops_detail["path"], "/ops/run-detail/:id")
        self.assertTrue(ops_detail["meta"]["hideInMenu"])

    def test_action_permissions_expose_only_matching_hidden_run_routes(self):
        role = Role.objects.create(name="route-operator")
        role.permission.add(
            Permission.objects.get(code="jobs.workflow_run:create"),
            Permission.objects.get(code="ops.workflow_run:read"),
        )
        user = get_user_model().objects.create_user(
            username="route-operator", password="123456",
            email="route-operator@example.com", phone="13800000123",
        )
        user.role.add(role)

        data = self._get_routes(user)
        visible_names = {
            child["name"]
            for root in data["routes"]
            for child in root.get("children", [])
        }
        self.assertIn("task_run-create", visible_names)
        self.assertIn("ops_run-detail", visible_names)
        self.assertNotIn("task_run-detail", visible_names)

    def test_routes_response_matches_soybean_user_route_shape(self):
        data = self._get_routes()

        self.assertIn("routes", data)
        self.assertIn("home", data)
        self.assertEqual(data["home"], "home")

        # 种子根目录 route_name 为 "/system"
        system_route = next(
            route for route in data["routes"] if route["name"] == "system"
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

    def test_legacy_component_with_accidental_view_prefix_still_resolves(self):
        menu = Menu.objects.get(component="system/user/index")
        menu.component = "view.system/user/index"
        menu.path = "/User"
        menu.save(update_fields=["component", "path"])
        data = self._get_routes()
        system = next(route for route in data["routes"] if route["name"] == "system")
        user = next(child for child in system["children"] if child["name"] == "manage_user")
        self.assertEqual(user["component"], "view.manage_user")
        self.assertEqual(user["path"], "/manage/user")

    def test_system_pages_saved_as_legacy_route_names_remain_navigable(self):
        pages = {
            "User": ("system/user/index", "manage_user"),
            "Role": ("system/role/index", "manage_role"),
            "SysMenu": ("system/menu/index", "manage_menu"),
            "Dept": ("system/dept/index", "manage_dept"),
            "Dict": ("system/dict/index", "manage_dict"),
            "Config": ("system/config/index", "manage_config"),
        }
        for name, (legacy, _) in pages.items():
            menu = Menu.objects.get(component=legacy)
            menu.component = f"view.{name}"
            menu.path = f"/{name}"
            menu.save(update_fields=["component", "path"])
        data = self._get_routes()
        system = next(route for route in data["routes"] if route["name"] == "system")
        actual = {child["name"]: child for child in system["children"]}
        for _, expected in pages.values():
            self.assertIn(expected, actual)
            self.assertEqual(actual[expected]["component"], f"view.{expected}")

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
            route for route in data["routes"] if route["name"] == "system"
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
            route for route in data["routes"] if route["name"] == "system"
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
            child for child in cmdb_route["children"] if child["name"] == "cmdb_host"
        )
        # 主机资产组件已归一为可映射的 view.cmdb_host，应保留
        self.assertEqual(host_route["component"], "view.cmdb_host")
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
    def test_icon_identifier_is_not_a_valid_external_link(self):
        serializer = MenuSerializer(data={
            "type": "M", "routeName": "Config", "routePath": "config",
            "title": "系统配置", "component": "system/config/index",
            "href": "carbon:settings-edit", "sort": 7,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("href", serializer.errors)

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
