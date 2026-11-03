# 种子数据已拆分至 apps/permission/seeds/ 包，本文件只保留执行逻辑。
# 历史导入路径（seed_data.SYSTEM_PERMISSIONS 等）保持可用。
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.permission.models import (
    DictItem,
    DictType,
    Menu,
    MenuButton,
    Permission,
    Role,
    SystemConfig,
)
from apps.permission.services import sync_casbin_rules
from apps.permission.seeds.configs import SYSTEM_CONFIGS, SYSTEM_DICTS
from apps.permission.seeds.menus import SYSTEM_MENUS
from apps.permission.seeds.permissions import (
    LEGACY_MENU_PERMISSION_REPLACEMENTS,
    SYSTEM_MENU_API_PERMISSIONS,
    SYSTEM_PERMISSIONS,
)
from apps.permission.seeds.roles import (
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_ADMIN_CODE,
    SYSTEM_ROLE_AUDITOR,
    SYSTEM_ROLE_AUDITOR_CODE,
)


class _SeedCache:
    """种子过程的对象缓存。

    预载现有数据到内存字典，把种子过程中的逐条 `.first()` / `update_or_create`
    查询（N+1，跨网段 MySQL 下 RTT 放大明显）降为每类数据一次 SELECT；
    写路径通过字段比对跳过无变化的 UPDATE / M2M 重写，保证重跑接近零写。
    """

    def __init__(self):
        self.permissions = {p.code: p for p in Permission.objects.all()}
        self.menus = {m.name: m for m in Menu.objects.all()}
        self.menu_buttons = {
            (b.menu_id, b.code): b for b in MenuButton.objects.all()
        }
        self.configs = {c.config_key: c for c in SystemConfig.objects.all()}
        self.dict_types = {t.dict_code: t for t in DictType.objects.all()}
        self.dict_items = {
            (i.dict_type_id, i.value): i for i in DictItem.objects.all()
        }
        # 同一组 code 集合的 API 权限查询结果按 tuple(code) 记忆化
        self._api_perm_ids_by_codes = {}

    def api_perm_ids(self, codes):
        key = tuple(sorted(codes))
        if key not in self._api_perm_ids_by_codes:
            self._api_perm_ids_by_codes[key] = set(
                Permission.objects.filter(
                    code__in=key,
                    type=Permission.PermissionType.API,
                    is_active=True,
                ).values_list("id", flat=True)
            )
        return self._api_perm_ids_by_codes[key]


_seed_cache = None


def _get_seed_cache():
    global _seed_cache
    if _seed_cache is None:
        _seed_cache = _SeedCache()
    return _seed_cache


def _upsert_permission(definition, parent=None):
    defaults = {
        "name": definition["name"],
        "type": definition["type"],
        "path": definition.get("path"),
        "method": definition.get("method"),
        "pid": parent,
        "is_system": True,
        "is_active": True,
    }
    cache = _get_seed_cache()
    permission = cache.permissions.get(definition["code"])
    if permission is None:
        permission = Permission.objects.create(code=definition["code"], **defaults)
        cache.permissions[permission.code] = permission
        return permission
    if any(getattr(permission, field) != value for field, value in defaults.items()):
        for field, value in defaults.items():
            setattr(permission, field, value)
        permission.save()
    return permission


def _upsert_menu(
    definition,
    permission,
    parent=None,
    order=1,
    sync_menu_layout=False,
):
    menu_type = definition.get(
        "menu_type",
        Menu.MenuType.CATALOG if definition.get("children") else Menu.MenuType.MENU,
    )
    menu_order = definition.get("order", order)
    defaults = {
        "order": menu_order,
        "menu_type": menu_type,
        "path": definition["path"],
        "component": definition.get("component"),
        "name": definition.get("route_name"),
        "title": definition.get("title"),
        "icon": definition.get("icon"),
        "show_icon": definition.get(
            "show_icon",
            bool(definition.get("icon")),
        ),
        "redirect": definition.get("redirect"),
        "active_menu": definition.get("active_menu"),
        "hidden": definition.get("hidden", False),
        "always_show": definition.get("always_show", True),
        "no_cache": definition.get("no_cache", False),
        "breadcrumb": definition.get("breadcrumb", False),
        "affix": definition.get("affix", False),
        "menu_group": Menu.MenuGroup.SYSTEM,
        "pid": parent,
    }
    menu = _get_seed_cache().menus.get(definition.get("route_name"))
    menu_created = menu is None
    if menu is None:
        menu = Menu.objects.create(**defaults)
        _get_seed_cache().menus[menu.name] = menu
    else:
        # Icons are user-managed, including an intentionally cleared icon.
        # Layout synchronization repairs structure/order, not visual choices.
        defaults["icon"] = menu.icon
        defaults["show_icon"] = menu.show_icon
        if not sync_menu_layout:
            defaults["order"] = menu.order
        if any(getattr(menu, field) != value for field, value in defaults.items()):
            for field, value in defaults.items():
                setattr(menu, field, value)
            menu.save()
    related_api_codes = definition.get("api_permissions")
    if related_api_codes is None:
        related_api_codes = SYSTEM_MENU_API_PERMISSIONS.get(definition["code"], ())
    desired_ids = _get_seed_cache().api_perm_ids(related_api_codes) | {permission.id}
    desired_qs = Permission.objects.filter(id__in=desired_ids)
    if menu_created:
        menu.permission.add(*desired_qs)
    else:
        current_ids = set(menu.permission.values_list("id", flat=True))
        if current_ids != desired_ids:
            menu.permission.set(desired_qs)
    _upsert_menu_buttons(menu, definition, menu_created=menu_created)
    return menu


def _upsert_menu_buttons(menu, definition, menu_created=False):
    """按种子定义同步菜单按钮（MenuButton）及其权限绑定。"""
    cache = _get_seed_cache()
    button_definitions = definition.get("buttons") or []
    for item in button_definitions:
        code = item["code"]
        button = cache.menu_buttons.get((menu.id, code))
        if button is None:
            button = MenuButton.objects.create(
                menu=menu,
                code=code,
                desc=item["title"],
            )
            cache.menu_buttons[(menu.id, code)] = button
            button_created = True
        else:
            button_created = False
            if button.desc != item["title"]:
                button.desc = item["title"]
                button.save(update_fields=["desc"])
        button_permission = cache.permissions.get(code)
        if button_permission is None:
            button_permission = Permission.objects.create(
                name=item["title"] or code,
                code=code,
                type=Permission.PermissionType.BUTTON,
                is_system=True,
                is_active=True,
            )
            cache.permissions[code] = button_permission
        related_api_codes = item.get("api_permissions")
        if related_api_codes is None:
            related_api_codes = SYSTEM_MENU_API_PERMISSIONS.get(code, ())
        desired_ids = cache.api_perm_ids(related_api_codes) | {button_permission.id}
        desired_qs = Permission.objects.filter(id__in=desired_ids)
        if button_created:
            button.permission.add(*desired_qs)
        else:
            current_ids = set(button.permission.values_list("id", flat=True))
            if current_ids != desired_ids:
                button.permission.set(desired_qs)
    return menu


def _seed_menu_permission_node(definition, permissions, parent=None):
    permissions[definition["code"]] = _upsert_permission(
        {
            "code": definition["code"],
            "name": definition["name"],
            "type": Permission.PermissionType.MENU,
            "path": definition["path"],
            "method": "GET",
        },
        parent=parent,
    )
    for button in definition.get("buttons", []):
        permissions[button["code"]] = _upsert_permission(
            {
                "code": button["code"],
                "name": button["title"],
                "type": Permission.PermissionType.BUTTON,
                "path": None,
                "method": None,
            },
            parent=permissions[definition["code"]],
        )
    for child in definition.get("children", []):
        _seed_menu_permission_node(
            child,
            permissions,
            parent=permissions[definition["code"]],
        )


def _seed_menu_permissions():
    permissions = {}
    for menu_definition in SYSTEM_MENUS:
        _seed_menu_permission_node(menu_definition, permissions)
    return permissions


def _seed_api_permissions():
    permissions = {}
    for definition in SYSTEM_PERMISSIONS:
        permissions[definition["code"]] = _upsert_permission(definition)
    return permissions


def _seed_menu_node(
    definition,
    menu_permissions,
    menus,
    parent=None,
    order=1,
    sync_menu_layout=False,
):
    current_menu = _upsert_menu(
        definition,
        permission=menu_permissions[definition["code"]],
        parent=parent,
        order=order,
        sync_menu_layout=sync_menu_layout,
    )
    menus[definition["code"]] = current_menu
    for child_index, child in enumerate(definition.get("children", []), start=1):
        _seed_menu_node(
            child,
            menu_permissions,
            menus,
            parent=current_menu,
            order=child_index,
            sync_menu_layout=sync_menu_layout,
        )


def _seed_menus(menu_permissions, sync_menu_layout=False):
    menus = {}
    for top_index, definition in enumerate(SYSTEM_MENUS, start=1):
        _seed_menu_node(
            definition,
            menu_permissions,
            menus,
            order=top_index,
            sync_menu_layout=sync_menu_layout,
        )
    return menus


def _seed_system_configs():
    cache = _get_seed_cache()
    configs = {}
    for definition in SYSTEM_CONFIGS:
        defaults = {
            "config_name": definition["config_name"],
            "config_value": definition["config_value"],
            "config_group": definition["config_group"],
            "remark": definition.get("remark", ""),
            "is_system": True,
        }
        config = cache.configs.get(definition["config_key"])
        if config is None:
            config = SystemConfig.objects.create(
                config_key=definition["config_key"], **defaults
            )
            cache.configs[config.config_key] = config
        elif any(getattr(config, field) != value for field, value in defaults.items()):
            for field, value in defaults.items():
                setattr(config, field, value)
            config.save()
        configs[config.config_key] = config
    return configs


def _seed_dicts():
    cache = _get_seed_cache()
    items = {}
    for definition in SYSTEM_DICTS:
        type_defaults = {
            "name": definition["name"],
            "status": 1,
            "remark": definition.get("remark", ""),
        }
        dict_type = cache.dict_types.get(definition["dict_code"])
        if dict_type is None:
            dict_type = DictType.objects.create(
                dict_code=definition["dict_code"], **type_defaults
            )
            cache.dict_types[dict_type.dict_code] = dict_type
        elif any(
            getattr(dict_type, field) != value
            for field, value in type_defaults.items()
        ):
            for field, value in type_defaults.items():
                setattr(dict_type, field, value)
            dict_type.save()
        for item_definition in definition.get("items", []):
            item_defaults = {
                "label": item_definition["label"],
                "status": item_definition.get("status", 1),
                "sort": item_definition.get("sort", 1),
                "tag_type": item_definition.get("tag_type", DictItem.TagType.NONE),
            }
            item = cache.dict_items.get((dict_type.id, item_definition["value"]))
            if item is None:
                item = DictItem.objects.create(
                    dict_type=dict_type,
                    value=item_definition["value"],
                    **item_defaults,
                )
                cache.dict_items[(dict_type.id, item.value)] = item
            elif any(
                getattr(item, field) != value for field, value in item_defaults.items()
            ):
                for field, value in item_defaults.items():
                    setattr(item, field, value)
                item.save()
            items[f"{dict_type.dict_code}:{item.value}"] = item
    return items


def _prune_stale_seed_data(seed_permission_codes, seed_menu_names, seed_button_assignments):
    Menu.objects.exclude(name__in=seed_menu_names).delete()
    cache = _get_seed_cache()
    valid_button_ids = {
        cache.menu_buttons[(cache.menus[menu_name].id, code)].id
        for menu_name, code in seed_button_assignments
    }
    MenuButton.objects.exclude(id__in=valid_button_ids).delete()
    Permission.objects.filter(is_system=True).exclude(
        code__in=seed_permission_codes
    ).delete()
    Role.objects.filter(is_system=True).exclude(
        name__in=[SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_AUDITOR]
    ).delete()


def _migrate_legacy_menu_role_permissions():
    for legacy_code, replacement_code in LEGACY_MENU_PERMISSION_REPLACEMENTS.items():
        roles = list(Role.objects.filter(permission__code=legacy_code).distinct())
        if not roles:
            continue
        replacement_menu = Menu.objects.get(permission__code=replacement_code)
        replacement_permissions = list(replacement_menu.get_effective_permissions())
        for role in roles:
            role.permission.add(*replacement_permissions)


def _migrate_moved_cmdb_button_roles():
    """保留已有来源写权限角色在拆分菜单后的页面访问权。"""
    for menu_name, button_prefix in (
        ("cmdb_source", "cmdb.asset_source:"),
    ):
        menu = _get_seed_cache().menus[menu_name]
        read_permissions = list(menu.permission.all())
        roles = Role.objects.filter(
            permission__code__startswith=button_prefix
        ).distinct()
        for role in roles:
            role.permission.add(*read_permissions)


def _seed_menu_names():
    names = []

    def collect(definition):
        route_name = definition.get("route_name")
        if route_name:
            names.append(route_name)
        for child in definition.get("children", []):
            collect(child)

    for definition in SYSTEM_MENUS:
        collect(definition)
    return names


def _seed_button_assignments():
    assignments = []

    def collect(definition):
        assignments.extend(
            (definition["route_name"], item["code"])
            for item in definition.get("buttons") or []
        )
        for child in definition.get("children", []):
            collect(child)

    for definition in SYSTEM_MENUS:
        collect(definition)
    return assignments


def _seed_permission_codes():
    codes = [definition["code"] for definition in SYSTEM_PERMISSIONS]

    def collect(definition):
        codes.append(definition["code"])
        codes.extend(button["code"] for button in definition.get("buttons") or [])
        for child in definition.get("children", []):
            collect(child)

    for definition in SYSTEM_MENUS:
        collect(definition)
    return codes


def _set_role_permissions(role, permissions):
    """角色权限 M2M 同步：与现有绑定一致时跳过写。"""
    desired_ids = {permission.id for permission in permissions}
    current_ids = set(role.permission.values_list("id", flat=True))
    if current_ids != desired_ids:
        role.permission.set(permissions)


def _seed_roles(all_permissions):
    admin_role, _ = Role.objects.update_or_create(
        name=SYSTEM_ROLE_ADMIN,
        defaults={
            "is_system": True,
            "code": SYSTEM_ROLE_ADMIN_CODE,
            "description": "系统管理员，拥有全部权限",
            "is_active": True,
        },
    )
    _set_role_permissions(admin_role, all_permissions)

    auditor_role, _ = Role.objects.update_or_create(
        name=SYSTEM_ROLE_AUDITOR,
        defaults={
            "is_system": True,
            "code": SYSTEM_ROLE_AUDITOR_CODE,
            "description": "系统审计员，仅拥有只读权限",
            "is_active": True,
        },
    )
    _set_role_permissions(
        auditor_role,
        [
            permission
            for permission in all_permissions
            if permission.type == Permission.PermissionType.MENU
            or (
                permission.type == Permission.PermissionType.API
                and permission.method
                and "GET" in permission.method
            )
        ],
    )
    return admin_role, auditor_role


def bind_role_to_superusers(role):
    for user in get_user_model().objects.filter(is_superuser=True):
        user.role.add(role)


@transaction.atomic
def seed_system_settings(bind_superusers=True, sync_menu_layout=False):
    # 播种期间暂停权限同步/审计信号，结束时统一 sync_casbin_rules 一次
    from .signals import suspend_permission_signals

    global _seed_cache
    _seed_cache = None  # 每次种子执行重建预载缓存

    with suspend_permission_signals():
        seed_menu_names = _seed_menu_names()
        seed_button_assignments = _seed_button_assignments()
        seed_permission_codes = _seed_permission_codes()
        api_permissions = _seed_api_permissions()
        menu_permissions = _seed_menu_permissions()
        _seed_menus(menu_permissions, sync_menu_layout=sync_menu_layout)
        _migrate_legacy_menu_role_permissions()
        _migrate_moved_cmdb_button_roles()
        _prune_stale_seed_data(
            seed_permission_codes, seed_menu_names, seed_button_assignments
        )
        system_configs = _seed_system_configs()
        dict_items = _seed_dicts()
        all_permissions = list(
            Permission.objects.filter(
                code__in=[
                    *api_permissions.keys(),
                    *menu_permissions.keys(),
                ]
            ).order_by("id")
        )
        admin_role, auditor_role = _seed_roles(all_permissions)
        if bind_superusers:
            bind_role_to_superusers(admin_role)
        sync_casbin_rules()
    return {
        "api_permissions": len(api_permissions),
        "menu_permissions": len(menu_permissions),
        "roles": [admin_role.name, auditor_role.name],
        "menus": Menu.objects.filter(menu_group=Menu.MenuGroup.SYSTEM).count(),
        "configs": len(system_configs),
        "dict_items": len(dict_items),
    }
