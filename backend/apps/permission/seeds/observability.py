"""Capabilities for completed monitoring modules; APIs remain independently gated."""
from apps.permission.models import Menu, Permission


def api(code, path, method, name):
    return {
        "code": code,
        "name": name,
        "type": Permission.PermissionType.API,
        "path": path,
        "method": method,
    }


def crud(prefix, path, name, writable=True, delete=True):
    values = [
        api(prefix + ".list", path, "GET", name + "列表"),
        api(prefix + ".detail", path + "/:id", "GET", name + "详情"),
    ]
    if writable:
        values += [
            api(prefix + ".create", path, "POST", name + "新增"),
            api(prefix + ".update", path + "/:id", "PUT", name + "编辑"),
            api(prefix + ".patch", path + "/:id", "PATCH", name + "部分编辑"),
        ]
        if delete:
            values.append(api(prefix + ".delete", path + "/:id", "DELETE", name + "删除"))
    return values


ADDITIONAL_PERMISSIONS = [
    *crud("monitoring.enrollment", "/api/v1/monitoring/enrollment-policies", "纳管策略"),
    *crud(
        "monitoring.enrollment_run",
        "/api/v1/monitoring/enrollment-runs",
        "纳管记录",
        writable=False,
    ),
    *[
        api(
            f"monitoring.enrollment.{action}",
            f"/api/v1/monitoring/enrollment-policies/:id/{action}",
            "GET" if action == "preview" else "POST",
            "纳管策略" + action,
        )
        for action in ("preview", "run", "enable", "pause")
    ],
    *crud(
        "integrations.jumpserver",
        "/api/v1/integrations/jumpserver/connections",
        "JumpServer连接",
    ),
    *[
        api(
            f"integrations.jumpserver.{action}",
            f"/api/v1/integrations/jumpserver/connections/:id/{action}",
            "GET" if action == "records" else "POST",
            "JumpServer" + action,
        )
        for action in ("test", "preview", "confirm", "records")
    ],
    *crud("security.subscription", "/api/v1/security/subscriptions", "漏洞订阅"),
    api(
        "security.subscription.collect",
        "/api/v1/security/subscriptions/:id/collect",
        "POST",
        "漏洞采集",
    ),
    *crud("security.advisory", "/api/v1/security/advisories", "漏洞公告", writable=False),
    *crud(
        "security.collection", "/api/v1/security/collections", "漏洞采集记录", writable=False
    ),
]

ADDITIONAL_MENU_API_PERMISSIONS = {
    "menu.monitoring.policies": (
        "monitoring.enrollment.list",
        "monitoring.enrollment.detail",
        "monitoring.enrollment.preview",
        "monitoring.enrollment_run.list",
        "monitoring.enrollment_run.detail",
    ),
    "monitoring.enrollment:create": (
        "monitoring.enrollment.create",
        "consul.connection.list",
        "cmdb.host_group.list",
    ),
    "monitoring.enrollment:update": (
        "monitoring.enrollment.update",
        "monitoring.enrollment.patch",
        "consul.connection.list",
        "cmdb.host_group.list",
    ),
    "monitoring.enrollment:delete": ("monitoring.enrollment.delete",),
    "monitoring.enrollment:run": (
        "monitoring.enrollment.run",
        "monitoring.enrollment.enable",
        "monitoring.enrollment.pause",
        "monitoring.enrollment.preview",
        "monitoring.target.sync",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.host_group.list",
    ),
    "menu.monitoring.integrations": (
        "integrations.jumpserver.list",
        "integrations.jumpserver.detail",
        "integrations.jumpserver.records",
    ),
    "integrations.jumpserver:manage": (
        "integrations.jumpserver.create",
        "integrations.jumpserver.update",
        "integrations.jumpserver.patch",
        "integrations.jumpserver.delete",
    ),
    "integrations.jumpserver:sync": (
        "integrations.jumpserver.test",
        "integrations.jumpserver.preview",
        "integrations.jumpserver.confirm",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.host_group.list",
    ),
    "menu.monitoring.security": (
        "security.subscription.list",
        "security.subscription.detail",
        "security.advisory.list",
        "security.advisory.detail",
        "security.collection.list",
        "security.collection.detail",
        "automation.notification_template.list",
    ),
    "security.subscription:manage": (
        "security.subscription.create",
        "security.subscription.update",
        "security.subscription.patch",
        "security.subscription.delete",
        "automation.notification_template.list",
    ),
    "security.subscription:collect": ("security.subscription.collect",),
}


def menu_leaf(key, title, order, buttons):
    return {
        "code": "menu.monitoring." + key,
        "name": title + "菜单",
        "path": key,
        "route_name": "monitoring_" + key,
        "title": title,
        "menu_type": Menu.MenuType.MENU,
        "component": "view.monitoring_" + key,
        "order": order,
        "icon": "carbon:dashboard",
        "buttons": [{"code": code, "title": label} for code, label in buttons],
    }


ADDITIONAL_MENUS = [
    menu_leaf(
        "policies",
        "动态纳管策略",
        3,
        [
            ("monitoring.enrollment:create", "新增策略"),
            ("monitoring.enrollment:update", "编辑策略"),
            ("monitoring.enrollment:run", "执行与启停"),
            ("monitoring.enrollment:delete", "删除策略"),
        ],
    ),
    menu_leaf(
        "integrations",
        "JumpServer 集成",
        4,
        [
            ("integrations.jumpserver:manage", "配置连接"),
            ("integrations.jumpserver:sync", "测试与同步"),
        ],
    ),
    menu_leaf(
        "security",
        "漏洞订阅",
        5,
        [
            ("security.subscription:manage", "配置订阅"),
            ("security.subscription:collect", "执行采集"),
        ],
    ),
]

for code in ADDITIONAL_MENU_API_PERMISSIONS:
    if ":" in code:
        ADDITIONAL_PERMISSIONS.append(
            {
                "code": code,
                "name": code,
                "type": Permission.PermissionType.BUTTON,
                "path": None,
                "method": None,
            }
        )
