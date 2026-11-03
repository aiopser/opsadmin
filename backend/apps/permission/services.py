import os
import threading
from collections import OrderedDict

import casbin
from django.conf import settings
from django.db import transaction
from django.db.models import Max

from apps.permission.models import CasbinRule, Menu, Permission, Role


# ----------------------- 菜单分组辅助 -----------------------

MENU_GROUP_PATTERNS = {
    "system": (
        "/system",
        "/user",
        "/prem",
    ),
}

SYSTEM_SETTING_KEYWORDS = {
    "user": ("user", "department", "member", "account", "组织", "用户", "部门"),
    "permission": ("prem", "permission", "role", "menu", "权限", "角色", "菜单"),
}


def infer_menu_group(menu):
    text_parts = [
        menu.path or "",
        menu.name or "",
        menu.title or "",
        menu.component or "",
        menu.redirect or "",
    ]
    haystack = " ".join(text_parts).lower()
    for group, patterns in MENU_GROUP_PATTERNS.items():
        if any(pattern.lower() in haystack for pattern in patterns):
            return group
    return Menu.MenuGroup.SYSTEM


def infer_system_setting_category(menu):
    text_parts = [
        menu.path or "",
        menu.name or "",
        menu.title or "",
        menu.component or "",
    ]
    haystack = " ".join(text_parts).lower()
    for category, keywords in SYSTEM_SETTING_KEYWORDS.items():
        if any(keyword.lower() in haystack for keyword in keywords):
            return category
    return "permission"


def build_grouped_menu_tree(menu_queryset, formatter):
    grouped = OrderedDict(
        [
            (Menu.MenuGroup.SYSTEM, []),
        ]
    )

    top_level = list(menu_queryset.filter(pid=None).order_by("order", "id"))
    for item in top_level:
        grouped[Menu.MenuGroup.SYSTEM].append(formatter(item))
    return grouped


# ----------------------- Casbin 策略同步 -----------------------


def _normalize_policy_item(item):
    return {
        "ptype": item["ptype"],
        "v0": item.get("user") or item.get("role"),
        "v1": item.get("role") or item.get("path"),
        "v2": item.get("path") or item.get("method"),
        "v3": item.get("method"),
        "v4": item.get("v4"),
        "v5": item.get("v5"),
    }


def build_policy_rows():
    rows = []
    for role in Role.objects.filter(is_active=True).prefetch_related("user", "permission"):
        rows.extend(_normalize_policy_item(item) for item in role.adapter())
        for permission in role.get_api_permissions():
            rows.append(
                {
                    "ptype": "p",
                    "v0": role.name,
                    "v1": permission.path,
                    "v2": permission.method,
                    "v3": None,
                    "v4": None,
                    "v5": None,
                }
            )
    return rows


def sync_casbin_rules():
    rows = build_policy_rows()
    with transaction.atomic():
        CasbinRule.objects.all().delete()
        CasbinRule.objects.bulk_create(
            [CasbinRule(**row) for row in rows],
            ignore_conflicts=True,
        )
        transaction.on_commit(CasbinEnforcerService.reload)


class CasbinEnforcerService:
    _lock = threading.RLock()
    _enforcer = None
    _policy_revision = None

    @staticmethod
    def _current_revision():
        # Policy rewrites allocate new primary keys. Reading the indexed maximum
        # also invalidates cached enforcers in other API/Worker processes.
        return CasbinRule.objects.aggregate(revision=Max("id"))["revision"]

    @classmethod
    def _build_enforcer(cls):
        from apps.permission.utils.adapter import Adapter

        model_conf_file = os.path.join(settings.BASE_DIR, "config", "prem_model.conf")
        return casbin.Enforcer(model_conf_file, adapter=Adapter())

    @classmethod
    def get_enforcer(cls):
        with cls._lock:
            revision = cls._current_revision()
            if cls._enforcer is None or cls._policy_revision != revision:
                cls._enforcer = cls._build_enforcer()
                cls._policy_revision = revision
            return cls._enforcer

    @classmethod
    def reload(cls):
        with cls._lock:
            revision = cls._current_revision()
            cls._enforcer = cls._build_enforcer()
            cls._policy_revision = revision
            return cls._enforcer
