from django.core.management.base import BaseCommand
from django.db import transaction

from apps.permission.models import Menu, MenuButton, Permission
from apps.permission.seed_data import SYSTEM_MENU_API_PERMISSIONS


class Command(BaseCommand):
    help = "Repair menu types, route fields, and menu/button permissions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync-seed-permissions",
            action="store_true",
            help="Reset seeded menu API bindings to seed_data.SYSTEM_MENU_API_PERMISSIONS.",
        )

    @staticmethod
    def route_code(path):
        raw = (path or "").strip().strip("/")
        return raw.replace("/", ":").replace("-", "_") or "root"

    @staticmethod
    def normalize_route_path(path, parent_id):
        if not path:
            return path
        path = str(path).strip()
        if path.startswith(("http://", "https://")):
            return path
        if parent_id is None and not path.startswith("/"):
            return f"/{path}"
        return path

    @staticmethod
    def infer_menu_type(menu):
        component = menu.component or ""
        has_children = Menu.objects.filter(pid_id=menu.id).exists()
        if has_children or component in ("Layout", "ParentView"):
            return Menu.MenuType.CATALOG
        return Menu.MenuType.MENU

    def normalize_menu(self, menu):
        changed_fields = []
        menu_type = self.infer_menu_type(menu)
        if menu.menu_type != menu_type:
            menu.menu_type = menu_type
            changed_fields.append("menu_type")

        normalized_path = self.normalize_route_path(menu.path, menu.pid_id)
        if normalized_path != menu.path:
            menu.path = normalized_path
            changed_fields.append("path")

        if menu.menu_type == Menu.MenuType.CATALOG:
            expected_component = "Layout" if menu.pid_id is None else "ParentView"
            if menu.component != expected_component:
                menu.component = expected_component
                changed_fields.append("component")
            if not menu.name:
                menu.name = menu.path
                changed_fields.append("name")
            if not menu.always_show:
                menu.always_show = True
                changed_fields.append("always_show")

        if changed_fields:
            menu.save(update_fields=sorted(set(changed_fields)))
        return bool(changed_fields)

    def sync_permission(self, menu, sync_seed_permissions=False):
        existing = menu.permission.filter(
            type=Permission.PermissionType.MENU,
        ).first()
        code = existing.code if existing else f"menu:{self.route_code(menu.path)}"
        permission_type = Permission.PermissionType.MENU
        path = menu.path
        method = "GET"

        if not code:
            return False

        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "name": menu.title or menu.name or code,
                "type": permission_type,
                "path": path,
                "method": method,
                "is_system": existing.is_system if existing else False,
                "is_active": True,
            },
        )
        if sync_seed_permissions and code in SYSTEM_MENU_API_PERMISSIONS:
            api_permission_ids = set(
                Permission.objects.filter(
                    code__in=SYSTEM_MENU_API_PERMISSIONS[code],
                    type=Permission.PermissionType.API,
                    is_active=True,
                ).values_list("id", flat=True)
            )
        else:
            api_permission_ids = set(
                menu.permission.filter(
                    type=Permission.PermissionType.API,
                    is_active=True,
                ).values_list("id", flat=True)
            )
        desired_ids = {permission.id, *api_permission_ids}
        current_ids = set(menu.permission.values_list("id", flat=True))
        if current_ids != desired_ids:
            menu.permission.set(desired_ids)
            return True
        return False

    def sync_button_permissions(self, sync_seed_permissions=False):
        """为每个菜单按钮确保 type='button' 权限标识并同步 API 权限绑定。"""
        updated = 0
        buttons = MenuButton.objects.select_related("menu").prefetch_related(
            "permission"
        )
        for button in buttons:
            permission = Permission.objects.filter(code=button.code).first()
            if permission is None:
                permission = Permission.objects.create(
                    name=button.desc or button.code,
                    code=button.code,
                    type=Permission.PermissionType.BUTTON,
                    is_active=True,
                )
            elif permission.type != Permission.PermissionType.BUTTON:
                permission.type = Permission.PermissionType.BUTTON
                permission.path = None
                permission.method = None
                permission.save(update_fields=["type", "path", "method"])
            if sync_seed_permissions and button.code in SYSTEM_MENU_API_PERMISSIONS:
                api_permission_ids = set(
                    Permission.objects.filter(
                        code__in=SYSTEM_MENU_API_PERMISSIONS[button.code],
                        type=Permission.PermissionType.API,
                        is_active=True,
                    ).values_list("id", flat=True)
                )
            else:
                api_permission_ids = set(
                    button.permission.filter(
                        type=Permission.PermissionType.API,
                        is_active=True,
                    ).values_list("id", flat=True)
                )
            desired_ids = {permission.id, *api_permission_ids}
            current_ids = set(button.permission.values_list("id", flat=True))
            if current_ids != desired_ids:
                button.permission.set(desired_ids)
                updated += 1
        return updated

    @transaction.atomic
    def handle(self, *args, **options):
        normalized_count = 0
        permission_count = 0
        for menu in Menu.objects.order_by("id"):
            if self.normalize_menu(menu):
                normalized_count += 1
            if self.sync_permission(
                menu,
                sync_seed_permissions=options["sync_seed_permissions"],
            ):
                permission_count += 1
        button_count = self.sync_button_permissions(
            sync_seed_permissions=options["sync_seed_permissions"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Menu data repaired: "
                f"{normalized_count} menus normalized, "
                f"{permission_count} permission bindings updated, "
                f"{button_count} button bindings updated."
            )
        )
