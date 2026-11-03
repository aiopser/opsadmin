"""API / 菜单权限种子数据。"""

from apps.permission.models import Permission


# 作业中心菜单已废弃（被作业系统/任务系统替代），其 menu.jobs.* 菜单权限不再存在，
# 旧 API 权限码的角色迁移已历史执行完毕，故清空映射，避免重跑 seed 时因目标菜单缺失而报错。
LEGACY_MENU_PERMISSION_REPLACEMENTS = {"menu.system.log": "menu.audit.operations"}


def _rest_permissions(code_prefix, name_prefix, base_path, extra_actions=None):
    item_path = f"{base_path}:id/" if base_path.endswith("/") else f"{base_path}/:id"
    permissions = [
        {
            "code": f"{code_prefix}.list",
            "name": f"{name_prefix}列表",
            "type": Permission.PermissionType.API,
            "path": base_path,
            "method": "GET",
        },
        {
            "code": f"{code_prefix}.create",
            "name": f"{name_prefix}创建",
            "type": Permission.PermissionType.API,
            "path": base_path,
            "method": "POST",
        },
        {
            "code": f"{code_prefix}.detail",
            "name": f"{name_prefix}详情",
            "type": Permission.PermissionType.API,
            "path": item_path,
            "method": "GET",
        },
        {
            "code": f"{code_prefix}.update",
            "name": f"{name_prefix}更新",
            "type": Permission.PermissionType.API,
            "path": item_path,
            "method": "PUT|PATCH",
        },
        {
            "code": f"{code_prefix}.delete",
            "name": f"{name_prefix}删除",
            "type": Permission.PermissionType.API,
            "path": item_path,
            "method": "DELETE",
        },
    ]
    for action in extra_actions or []:
        permissions.append(
            {
                "code": f"{code_prefix}.{action['code']}",
                "name": action["name"],
                "type": Permission.PermissionType.API,
                "path": action["path"],
                "method": action["method"],
            }
        )
    return permissions


def _read_permissions(code_prefix, name_prefix, base_path, extra_actions=None):
    item_path = f"{base_path}:id/" if base_path.endswith("/") else f"{base_path}/:id"
    permissions = [
        {
            "code": f"{code_prefix}.list",
            "name": f"{name_prefix}列表",
            "type": Permission.PermissionType.API,
            "path": base_path,
            "method": "GET",
        },
        {
            "code": f"{code_prefix}.detail",
            "name": f"{name_prefix}详情",
            "type": Permission.PermissionType.API,
            "path": item_path,
            "method": "GET",
        },
    ]
    for action in extra_actions or []:
        permissions.append(
            {
                "code": f"{code_prefix}.{action['code']}",
                "name": action["name"],
                "type": Permission.PermissionType.API,
                "path": action["path"],
                "method": action["method"],
            }
        )
    return permissions


def _create_and_read_permissions(
    code_prefix, name_prefix, base_path, extra_actions=None
):
    permissions = _read_permissions(
        code_prefix,
        name_prefix,
        base_path,
        extra_actions=extra_actions,
    )
    permissions.insert(
        1,
        {
            "code": f"{code_prefix}.create",
            "name": f"{name_prefix}创建",
            "type": Permission.PermissionType.API,
            "path": base_path,
            "method": "POST",
        },
    )
    return permissions


def _button_permissions(code_prefix, name_prefix, actions):
    return [
        {
            "code": f"{code_prefix}:{action['code']}",
            "name": f"{name_prefix}{action['name']}",
            "type": Permission.PermissionType.BUTTON,
            "path": None,
            "method": None,
        }
        for action in actions
    ]


def _button_menu(code, title, api_permissions=None):
    definition = {
        "code": code,
        "title": title,
    }
    if api_permissions is not None:
        definition["api_permissions"] = api_permissions
    return definition


def _button_menus(prefix, actions):
    return [
        _button_menu(
            f"{prefix}:{action['code']}",
            action["title"],
            api_permissions=action.get("api_permissions"),
        )
        for action in actions
    ]


SYSTEM_PERMISSIONS = [
    *[
        {
            "code": f"consul.connection.{code}",
            "name": name,
            "type": Permission.PermissionType.API,
            "path": f"/api/v1/consul/connections/:id/{path}",
            "method": "GET",
        }
        for code, name, path in [
            ("datacenters", "查看Consul数据中心", "datacenters"),
            ("catalog_services", "查看Consul服务目录", "catalog-services"),
            ("catalog_instances", "查看Consul目录实例", "catalog-instances"),
            ("kv_keys", "查看Consul KV列表", "kv"),
            ("kv_value", "查看Consul KV值", "kv-value"),
        ]
    ],
    *[
        {
            "code": f"monitoring.target.{code}",
            "name": name,
            "type": Permission.PermissionType.API,
            "path": f"/api/v1/monitoring/targets/{path}",
            "method": "POST",
        }
        for code, name, path in [
            ("host_import_preview", "预览主机监控接入", "host-import-preview"),
            ("host_import", "批量接入主机监控", "host-import"),
        ]
    ],
    {
        "code": "monitoring.target:host_import",
        "name": "从资产接入监控",
        "type": Permission.PermissionType.BUTTON,
        "path": None,
        "method": None,
    },
    {
        "code": "monitoring.target.rules",
        "name": "查看监控告警规则",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/monitoring/connections/:id/alert-rules",
        "method": "GET",
    },
    *_rest_permissions(
        "consul.connection",
        "Consul连接",
        "/api/v1/consul/connections",
        extra_actions=[
            {
                "code": "test",
                "name": "测试Consul连接",
                "path": "/api/v1/consul/connections/:id/test",
                "method": "POST",
            },
            {
                "code": "services",
                "name": "查看Consul实例",
                "path": "/api/v1/consul/connections/:id/services",
                "method": "GET",
            },
            {
                "code": "kv_write",
                "name": "写入Consul KV",
                "path": "/api/v1/consul/connections/:id/kv-write",
                "method": "POST",
            },
            {
                "code": "kv_delete",
                "name": "删除Consul KV",
                "path": "/api/v1/consul/connections/:id/kv-delete",
                "method": "DELETE",
            },
        ],
    ),
    *_button_permissions(
        "consul.connection",
        "Consul连接",
        [
            {"code": code, "name": name}
            for code, name in [
                ("create", "新增"),
                ("update", "编辑"),
                ("delete", "删除"),
                ("test", "测试"),
                ("kv", "浏览KV"),
                ("kv_edit", "编辑KV"),
            ]
        ],
    ),
    *_rest_permissions(
        "consul.template",
        "Consul模板配置",
        "/api/v1/consul/templates",
        extra_actions=[
            {
                "code": "read_remote",
                "name": "读取Consul远端文件",
                "path": "/api/v1/consul/templates/read-remote",
                "method": "POST",
            },
            {
                "code": "read_status",
                "name": "查看Consul文件读取结果",
                "path": "/api/v1/consul/templates/remote-reads/:id",
                "method": "GET",
            },
            {
                "code": "compare_remote",
                "name": "比较Consul远端文件",
                "path": "/api/v1/consul/templates/compare-remote",
                "method": "POST",
            },
            {
                "code": "deploy",
                "name": "下发Consul模板配置",
                "path": "/api/v1/consul/templates/:id/deploy",
                "method": "POST",
            },
        ],
    ),
    *_button_permissions(
        "consul.template",
        "Consul模板配置",
        [
            {"code": code, "name": name}
            for code, name in [
                ("create", "新增"),
                ("update", "编辑"),
                ("delete", "删除"),
                ("deploy", "下发"),
                ("read_remote", "读取远端文件"),
            ]
        ],
    ),
    *_rest_permissions(
        "monitoring.target",
        "监控目标",
        "/api/v1/monitoring/targets",
        extra_actions=[
            {
                "code": "sync",
                "name": "同步监控目标",
                "path": "/api/v1/monitoring/targets/:id/sync",
                "method": "POST",
            },
            {
                "code": "deregister",
                "name": "注销监控目标",
                "path": "/api/v1/monitoring/targets/:id/deregister",
                "method": "POST",
            },
            {
                "code": "preview",
                "name": "预览监控注册",
                "path": "/api/v1/monitoring/targets/:id/preview",
                "method": "GET",
            },
            {
                "code": "config",
                "name": "查看Prometheus配置",
                "path": "/api/v1/monitoring/connections/:id/prometheus-config",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "monitoring.target",
        "监控目标",
        [
            {"code": code, "name": name}
            for code, name in [
                ("create", "新增"),
                ("update", "编辑"),
                ("delete", "删除"),
                ("sync", "同步"),
                ("deregister", "注销"),
            ]
        ],
    ),
    *_read_permissions(
        "monitoring.record", "监控同步记录", "/api/v1/monitoring/sync-records"
    ),
    *[
        {
            "code": f"provisioning.request.{action}",
            "name": label,
            "type": Permission.PermissionType.API,
            "path": f"/api/v1/provisioning/requests/:id/{action}",
            "method": method,
        }
        for action, label, method in [
            ("state-versions", "查看 state 版本", "GET"),
            ("restore-preview", "预览 state 恢复", "POST"),
            ("restore-confirm", "确认 state 恢复", "POST"),
        ]
    ],
    {
        "code": "provisioning.operations.health",
        "name": "资源交付运行状况",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/provisioning/operations/health",
        "method": "GET",
    },
    {
        "code": "provisioning.catalog.read",
        "name": "查询申请资源目录",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/provisioning/catalog",
        "method": "GET",
    },
    {
        "code": "provisioning.catalog.configure",
        "name": "查询模板配置资源目录",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/provisioning/catalog/configuration",
        "method": "GET",
    },
    *_rest_permissions(
        "provisioning.request",
        "资源申请",
        "/api/v1/provisioning/requests",
        extra_actions=[
            {
                "code": "events",
                "name": "资源申请操作记录",
                "path": "/api/v1/provisioning/requests/:id/events",
                "method": "GET",
            },
            *[
                {
                    "code": action,
                    "name": label,
                    "path": f"/api/v1/provisioning/requests/:id/{action}",
                    "method": "POST",
                }
                for action, label in [
                    ("plan", "生成变更计划"),
                    ("confirm", "确认变更计划"),
                    ("approve", "审批资源申请"),
                    ("reject", "拒绝资源申请"),
                    ("execute", "执行资源创建"),
                    ("reconcile", "核实资源纳管"),
                ]
            ],
        ],
    ),
    *_rest_permissions(
        "provisioning.template", "资源模板", "/api/v1/provisioning/templates"
    ),
    *_rest_permissions(
        "provisioning.version",
        "资源模板版本",
        "/api/v1/provisioning/versions",
        extra_actions=[
            {
                "code": "publish",
                "name": "发布资源模板版本",
                "path": "/api/v1/provisioning/versions/:id/publish",
                "method": "POST",
            }
        ],
    ),
    *_rest_permissions(
        "provisioning.credential",
        "资源创建凭据",
        "/api/v1/provisioning/credentials",
        extra_actions=[
            {
                "code": "use",
                "name": "使用资源创建凭据",
                "path": "/api/v1/provisioning/credentials/:id/use",
                "method": "POST",
            }
        ],
    ),
    {
        "code": "provisioning.review",
        "name": "查看全部资源申请",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/provisioning/review",
        "method": "GET",
    },
    {
        "code": "file.upload",
        "name": "文件上传",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/files",
        "method": "POST",
    },
    {
        "code": "file.delete",
        "name": "文件删除",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/files",
        "method": "DELETE",
    },
    {
        "code": "permission.permission.options",
        "name": "权限选项",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/permissions/options",
        "method": "GET",
    },
    *_rest_permissions(
        "template.user",
        "用户",
        "/api/v1/users",
        extra_actions=[
            {
                "code": "profile",
                "name": "当前用户资料",
                "path": "/api/v1/users/profile",
                "method": "GET",
            },
            {
                "code": "options",
                "name": "用户选项",
                "path": "/api/v1/users/options",
                "method": "GET",
            },
            {
                "code": "form",
                "name": "用户表单",
                "path": "/api/v1/users/:id/form",
                "method": "GET",
            },
            {
                "code": "password_reset",
                "name": "用户重置密码",
                "path": "/api/v1/users/:id/password/reset",
                "method": "PUT",
            },
            {
                "code": "template",
                "name": "用户导入模板",
                "path": "/api/v1/users/template",
                "method": "GET",
            },
            {
                "code": "export",
                "name": "用户导出",
                "path": "/api/v1/users/export",
                "method": "GET",
            },
            {
                "code": "import",
                "name": "用户导入",
                "path": "/api/v1/users/import",
                "method": "POST",
            },
        ],
    ),
    *_button_permissions(
        "sys:user",
        "用户",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "reset-password", "name": "重置密码"},
            {"code": "import", "name": "导入"},
            {"code": "export", "name": "导出"},
        ],
    ),
    *_rest_permissions(
        "template.dept",
        "部门",
        "/api/v1/depts",
        extra_actions=[
            {
                "code": "options",
                "name": "部门选项",
                "path": "/api/v1/depts/options",
                "method": "GET",
            },
            {
                "code": "form",
                "name": "部门表单",
                "path": "/api/v1/depts/:id/form",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "sys:dept",
        "部门",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "template.role",
        "角色",
        "/api/v1/roles",
        extra_actions=[
            {
                "code": "options",
                "name": "角色选项",
                "path": "/api/v1/roles/options",
                "method": "GET",
            },
            {
                "code": "form",
                "name": "角色表单",
                "path": "/api/v1/roles/:id/form",
                "method": "GET",
            },
            {
                "code": "menu_ids",
                "name": "角色菜单ID列表",
                "path": "/api/v1/roles/:id/menu-ids",
                "method": "GET",
            },
            {
                "code": "menus",
                "name": "分配角色菜单",
                "path": "/api/v1/roles/:id/menus",
                "method": "PUT",
            },
            {
                "code": "dept_ids",
                "name": "角色部门ID列表",
                "path": "/api/v1/roles/:id/dept-ids",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "sys:role",
        "角色",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "assign", "name": "分配权限"},
        ],
    ),
    *_rest_permissions(
        "template.menu",
        "菜单",
        "/api/v1/menus",
        extra_actions=[
            {
                "code": "routes",
                "name": "当前用户动态路由",
                "path": "/api/v1/menus/routes",
                "method": "GET",
            },
            {
                "code": "options",
                "name": "菜单选项",
                "path": "/api/v1/menus/options",
                "method": "GET",
            },
            {
                "code": "form",
                "name": "菜单表单",
                "path": "/api/v1/menus/:id/form",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "sys:menu",
        "菜单",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "template.dict",
        "字典",
        "/api/v1/dicts",
        extra_actions=[
            {
                "code": "options",
                "name": "字典选项",
                "path": "/api/v1/dicts/options",
                "method": "GET",
            },
            {
                "code": "form",
                "name": "字典表单",
                "path": "/api/v1/dicts/:id/form",
                "method": "GET",
            },
            {
                "code": "items.list",
                "name": "字典项列表",
                "path": "/api/v1/dicts/:dictCode/items",
                "method": "GET",
            },
            {
                "code": "items.create",
                "name": "字典项创建",
                "path": "/api/v1/dicts/:dictCode/items",
                "method": "POST",
            },
            {
                "code": "items.options",
                "name": "字典项选项",
                "path": "/api/v1/dicts/:dictCode/items/options",
                "method": "GET",
            },
            {
                "code": "items.form",
                "name": "字典项表单",
                "path": "/api/v1/dicts/:dictCode/items/:id/form",
                "method": "GET",
            },
            {
                "code": "items.update",
                "name": "字典项更新",
                "path": "/api/v1/dicts/:dictCode/items/:id",
                "method": "PUT|PATCH",
            },
            {
                "code": "items.delete",
                "name": "字典项删除",
                "path": "/api/v1/dicts/:dictCode/items/:id",
                "method": "DELETE",
            },
        ],
    ),
    *_button_permissions(
        "sys:dict",
        "字典",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "item", "name": "字典数据"},
        ],
    ),
    *_button_permissions(
        "sys:dict-item",
        "字典项",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "template.config",
        "系统配置",
        "/api/v1/configs",
        extra_actions=[
            {
                "code": "form",
                "name": "系统配置表单",
                "path": "/api/v1/configs/:id/form",
                "method": "GET",
            },
            {
                "code": "refresh",
                "name": "刷新系统配置缓存",
                "path": "/api/v1/configs/refresh",
                "method": "PUT",
            },
            {
                "code": "snapshot",
                "name": "系统配置快照",
                "path": "/api/v1/configs/snapshot",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "sys:config",
        "系统配置",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "refresh", "name": "刷新缓存"},
        ],
    ),
    {
        "code": "notification.email_settings.read",
        "name": "通知邮件服务器配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/email-settings",
        "method": "GET",
    },
    {
        "code": "notification.email_settings.update",
        "name": "保存通知邮件服务器配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/email-settings",
        "method": "PUT",
    },
    {
        "code": "notification.email_settings.test",
        "name": "发送测试邮件",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/email-settings/test",
        "method": "POST",
    },
    {
        "code": "notification.email_settings.test_connection",
        "name": "测试邮件服务器连接",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/email-settings/test-connection",
        "method": "POST",
    },
    {
        "code": "notification.wecom.read",
        "name": "读取企业微信应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/wecom-settings",
        "method": "GET",
    },
    {
        "code": "notification.wecom.update",
        "name": "保存企业微信应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/wecom-settings",
        "method": "PUT",
    },
    {
        "code": "notification.wecom.test",
        "name": "测试企业微信应用连接",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/wecom-settings/test-connection",
        "method": "POST",
    },
    {
        "code": "notification.dingtalk.read",
        "name": "读取钉钉应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/dingtalk-settings",
        "method": "GET",
    },
    {
        "code": "notification.dingtalk.update",
        "name": "保存钉钉应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/dingtalk-settings",
        "method": "PUT",
    },
    {
        "code": "notification.dingtalk.test",
        "name": "测试钉钉应用连接",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/dingtalk-settings/test-connection",
        "method": "POST",
    },
    {
        "code": "notification.feishu.read",
        "name": "读取飞书应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/feishu-settings",
        "method": "GET",
    },
    {
        "code": "notification.feishu.update",
        "name": "保存飞书应用配置",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/feishu-settings",
        "method": "PUT",
    },
    {
        "code": "notification.feishu.test",
        "name": "测试飞书应用连接",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/notifications/feishu-settings/test-connection",
        "method": "POST",
    },
    *_button_permissions(
        "sys:notification",
        "通知设置",
        [
            {"code": "update", "name": "保存通知设置"},
            {"code": "test", "name": "发送测试邮件"},
        ],
    ),
    *_rest_permissions(
        "cmdb.host",
        "主机",
        "/api/v1/cmdb/hosts",
        extra_actions=[
            {
                "code": "bulk_import",
                "name": "主机批量导入",
                "path": "/api/v1/cmdb/hosts/bulk-import",
                "method": "POST",
            },
            {
                "code": "excel_import",
                "name": "主机 Excel 导入",
                "path": "/api/v1/cmdb/hosts/excel-import",
                "method": "POST",
            },
            {
                "code": "relations",
                "name": "主机关联关系",
                "path": "/api/v1/cmdb/hosts/:id/relations",
                "method": "GET|POST",
            },
        ],
    ),
    *_button_permissions(
        "cmdb.host",
        "主机",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "bulk_import", "name": "批量导入"},
            {"code": "excel_import", "name": "Excel 导入"},
        ],
    ),
    *_rest_permissions(
        "cmdb.host_group",
        "主机分组",
        "/api/v1/cmdb/host-groups",
        extra_actions=[
            {
                "code": "members",
                "name": "主机分组成员",
                "path": "/api/v1/cmdb/host-groups/:id/members",
                "method": "GET|POST",
            },
        ],
    ),
    *_button_permissions(
        "cmdb.host_group",
        "主机分组",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "members", "name": "成员维护"},
        ],
    ),
    *_rest_permissions(
        "cmdb.asset_source",
        "资源来源",
        "/api/v1/cmdb/asset-sources",
        extra_actions=[
            {
                "code": "test_connection",
                "name": "测试云账号连接",
                "path": "/api/v1/cmdb/asset-sources/test-cloud-connection",
                "method": "POST",
            },
            {
                "code": "preview_sync",
                "name": "预览资源同步",
                "path": "/api/v1/cmdb/asset-sources/:id/preview-sync",
                "method": "POST",
            },
            {
                "code": "preview_cloud",
                "name": "预览云资产",
                "path": "/api/v1/cmdb/asset-sources/:id/preview-cloud",
                "method": "POST",
            },
            {
                "code": "sync_cloud",
                "name": "确认云资产同步",
                "path": "/api/v1/cmdb/asset-sources/:id/sync-cloud",
                "method": "POST",
            },
            {
                "code": "sync",
                "name": "资源同步",
                "path": "/api/v1/cmdb/asset-sources/:id/sync",
                "method": "POST",
            },
        ],
    ),
    *_button_permissions(
        "cmdb.asset_source",
        "资源来源",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "sync", "name": "同步"},
        ],
    ),
    *_read_permissions(
        "cmdb.asset_sync_record",
        "资产同步记录",
        "/api/v1/cmdb/asset-sync-records",
    ),
    *_read_permissions(
        "cmdb.search",
        "CMDB搜索",
        "/api/v1/cmdb/search",
    ),
    *_rest_permissions("cmdb.tag", "主机标签", "/api/v1/cmdb/tags"),
    # 标签管理已并入主机表单：仅保留新增按钮权限，编辑/删除入口随菜单移除
    *_button_permissions(
        "cmdb.tag",
        "主机标签",
        [
            {"code": "create", "name": "新增"},
        ],
    ),
    *_rest_permissions(
        "cmdb.credential_ref",
        "凭据管理",
        "/api/v1/cmdb/credential-refs",
    ),
    *_button_permissions(
        "cmdb.credential_ref",
        "凭据管理",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "jobs.worker_pool",
        "Worker池",
        "/api/v1/jobs/worker-pools",
    ),
    *_button_permissions(
        "jobs.worker_pool",
        "Worker池",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "automation.command",
        "命令",
        "/api/v1/automation/commands",
        extra_actions=[
            {
                "code": "versions",
                "name": "命令版本列表和创建",
                "path": "/api/v1/automation/commands/:id/versions",
                "method": "GET|POST",
            },
        ],
    ),
    *_button_permissions(
        "automation.command",
        "命令",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "publish", "name": "发布"},
            {"code": "archive", "name": "归档"},
            {"code": "execute_high_risk", "name": "执行高危命令"},
        ],
    ),
    *_rest_permissions(
        "automation.command_version",
        "命令版本",
        "/api/v1/automation/command-versions",
        extra_actions=[
            {
                "code": "publish",
                "name": "命令版本发布",
                "path": "/api/v1/automation/command-versions/:id/publish",
                "method": "POST",
            },
            {
                "code": "archive",
                "name": "命令版本归档",
                "path": "/api/v1/automation/command-versions/:id/archive",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.workflow",
        "流程模板",
        "/api/v1/automation/workflows",
        extra_actions=[
            {
                "code": "versions",
                "name": "流程版本列表和创建",
                "path": "/api/v1/automation/workflows/:id/versions",
                "method": "GET|POST",
            },
            {
                "code": "copy",
                "name": "复制流程模板",
                "path": "/api/v1/automation/workflows/:id/copy",
                "method": "POST",
            },
        ],
    ),
    *_button_permissions(
        "automation.workflow",
        "流程模板",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "publish", "name": "发布"},
            {"code": "archive", "name": "归档"},
            {"code": "execute", "name": "执行"},
        ],
    ),
    *_rest_permissions(
        "automation.workflow_version",
        "流程版本",
        "/api/v1/automation/workflow-versions",
        extra_actions=[
            {
                "code": "publish",
                "name": "流程版本发布",
                "path": "/api/v1/automation/workflow-versions/:id/publish",
                "method": "POST",
            },
            {
                "code": "archive",
                "name": "流程版本归档",
                "path": "/api/v1/automation/workflow-versions/:id/archive",
                "method": "POST",
            },
            {
                "code": "validate",
                "name": "流程版本校验",
                "path": "/api/v1/automation/workflow-versions/:id/validate",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.workflow_node",
        "流程节点",
        "/api/v1/automation/workflow-nodes",
    ),
    {
        "code": "automation.workflow_version.graph",
        "name": "Workflow graph read and update",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/automation/workflow-versions/:id/graph",
        "method": "GET|PUT",
    },
    {
        "code": "automation.template.list",
        "name": "可执行模板列表",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/automation/templates",
        "method": "GET",
    },
    {
        "code": "automation.node_resource.list",
        "name": "节点资源统一目录",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/automation/node-resources",
        "method": "GET",
    },
    {
        "code": "automation.node_resource.create",
        "name": "创建 Ansible 节点资源及首个版本",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/automation/node-resources",
        "method": "POST",
    },
    *_create_and_read_permissions(
        "jobs.workflow_run",
        "任务执行",
        "/api/v1/tasks/runs",
        extra_actions=[
            {
                "code": "validate",
                "name": "预览任务执行范围",
                "path": "/api/v1/tasks/runs/validate",
                "method": "POST",
            },
            {
                "code": "summary",
                "name": "执行状态汇总",
                "path": "/api/v1/tasks/runs/summary",
                "method": "GET",
            },
            {
                "code": "export",
                "name": "导出执行记录",
                "path": "/api/v1/tasks/runs/export",
                "method": "GET",
            },
            {
                "code": "cancel",
                "name": "取消执行",
                "path": "/api/v1/tasks/runs/:id/cancel",
                "method": "POST",
            },
            {
                "code": "retry_failed",
                "name": "重试失败节点",
                "path": "/api/v1/tasks/runs/:id/retry-failed",
                "method": "POST",
            },
            {
                "code": "rerun",
                "name": "重跑任务",
                "path": "/api/v1/tasks/runs/:id/rerun",
                "method": "POST",
            },
            {
                "code": "nodes",
                "name": "执行节点列表",
                "path": "/api/v1/tasks/runs/:id/nodes",
                "method": "GET",
            },
            {
                "code": "events",
                "name": "执行事件日志",
                "path": "/api/v1/tasks/runs/:id/events",
                "method": "GET",
            },
            {
                "code": "realtime_ticket",
                "name": "订阅执行通知",
                "path": "/api/v1/tasks/runs/:id/realtime-ticket",
                "method": "POST",
            },
            {
                "code": "log",
                "name": "执行实时日志",
                "path": "/api/v1/tasks/runs/:id/log",
                "method": "GET",
            },
        ],
    ),
    *_read_permissions(
        "ops.workflow_run",
        "作业执行",
        "/api/v1/ops/runs",
        extra_actions=[
            {
                "code": "summary",
                "name": "作业状态汇总",
                "path": "/api/v1/ops/runs/summary",
                "method": "GET",
            },
            {
                "code": "export",
                "name": "导出作业记录",
                "path": "/api/v1/ops/runs/export",
                "method": "GET",
            },
            {
                "code": "cancel",
                "name": "取消作业",
                "path": "/api/v1/ops/runs/:id/cancel",
                "method": "POST",
            },
            {
                "code": "retry_failed",
                "name": "重试失败作业",
                "path": "/api/v1/ops/runs/:id/retry-failed",
                "method": "POST",
            },
            {
                "code": "rerun",
                "name": "重跑作业",
                "path": "/api/v1/ops/runs/:id/rerun",
                "method": "POST",
            },
            {
                "code": "nodes",
                "name": "作业节点列表",
                "path": "/api/v1/ops/runs/:id/nodes",
                "method": "GET",
            },
            {
                "code": "events",
                "name": "作业事件日志",
                "path": "/api/v1/ops/runs/:id/events",
                "method": "GET",
            },
            {
                "code": "realtime_ticket",
                "name": "订阅执行通知",
                "path": "/api/v1/ops/runs/:id/realtime-ticket",
                "method": "POST",
            },
            {
                "code": "log",
                "name": "作业实时日志",
                "path": "/api/v1/ops/runs/:id/log",
                "method": "GET",
            },
        ],
    ),
    {
        "code": "jobs.quick_command.create",
        "name": "快捷命令执行创建",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/quick-commands/runs",
        "method": "POST",
    },
    {
        "code": "jobs.quick_command.preview",
        "name": "预览脚本执行范围",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/quick-commands/runs/preview",
        "method": "POST",
    },
    {
        "code": "jobs.playbook_run.create",
        "name": "剧本执行创建",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/playbook-runs",
        "method": "POST",
    },
    {
        "code": "jobs.playbook_run.preview",
        "name": "预览剧本执行范围",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/playbook-runs/preview",
        "method": "POST",
    },
    {
        "code": "jobs.module_run.create",
        "name": "Ansible模块执行创建",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/module-runs",
        "method": "POST",
    },
    {
        "code": "jobs.module_run.preview",
        "name": "预览模块执行范围",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/module-runs/preview",
        "method": "POST",
    },
    *_rest_permissions(
        "jobs.gateway",
        "Gateway proxy",
        "/api/v1/jobs/gateways",
        extra_actions=[
            {
                "code": "test",
                "name": "Test gateway connection",
                "path": "/api/v1/jobs/gateways/:id/test",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.workflow_edge",
        "流程连线",
        "/api/v1/automation/workflow-edges",
    ),
    *_rest_permissions(
        "automation.api_endpoint",
        "API 资源",
        "/api/v1/automation/api-endpoints",
        extra_actions=[
            {
                "code": "test",
                "name": "测试 API 资源",
                "path": "/api/v1/automation/api-endpoints/:id/test",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.jenkins_server",
        "Jenkins 实例",
        "/api/v1/automation/jenkins-servers",
        extra_actions=[
            {
                "code": "jobs",
                "name": "Jenkins Job 列表",
                "path": "/api/v1/automation/jenkins-servers/:id/jobs",
                "method": "GET",
            },
            {
                "code": "job_detail",
                "name": "Jenkins Job 详情",
                "path": "/api/v1/automation/jenkins-servers/:id/job-detail",
                "method": "GET",
            },
        ],
    ),
    *_rest_permissions(
        "automation.git_repository",
        "Git 仓库",
        "/api/v1/automation/git-repositories",
        extra_actions=[
            {
                "code": "files",
                "name": "Git 仓库文件列表",
                "path": "/api/v1/automation/git-repositories/:id/files",
                "method": "GET",
            },
            {
                "code": "load",
                "name": "加载 Git 仓库文件内容",
                "path": "/api/v1/automation/git-repositories/:id/load",
                "method": "POST",
            },
        ],
    ),
    {
        "code": "jobs.dashboard.health",
        "name": "任务平台健康状态",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/dashboard/health",
        "method": "GET",
    },
    {
        "code": "jobs.dashboard.execution_distribution",
        "name": "查看作业与任务执行分布",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/dashboard/execution-distribution",
        "method": "GET",
    },
    *_read_permissions(
        "automation.jenkins_job",
        "Jenkins Job",
        "/api/v1/automation/jenkins-jobs",
        extra_actions=[
            {
                "code": "run",
                "name": "试运行 Jenkins Job",
                "path": "/api/v1/automation/jenkins-jobs/:id/run",
                "method": "POST",
            },
        ],
    ),
    *_read_permissions(
        "automation.jenkins_build",
        "Jenkins Build",
        "/api/v1/automation/jenkins-builds",
        extra_actions=[
            {
                "code": "stop",
                "name": "停止 Jenkins Build",
                "path": "/api/v1/automation/jenkins-builds/:id/stop",
                "method": "POST",
            },
            {
                "code": "refresh",
                "name": "刷新 Jenkins Build",
                "path": "/api/v1/automation/jenkins-builds/:id/refresh",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.notification_channel",
        "通知通道",
        "/api/v1/automation/notification-channels",
    ),
    *_rest_permissions(
        "automation.notification_template",
        "通知模板",
        "/api/v1/automation/notification-templates",
        extra_actions=[
            {
                "code": "variables",
                "name": "查看通知变量",
                "path": "/api/v1/automation/notification-templates/variables",
                "method": "GET",
            },
            {
                "code": "preview",
                "name": "预览通知模板",
                "path": "/api/v1/automation/notification-templates/preview",
                "method": "POST",
            },
            {
                "code": "test_send",
                "name": "测试发送通知",
                "path": "/api/v1/automation/notification-templates/:id/test-send",
                "method": "POST",
            },
        ],
    ),
    *_read_permissions(
        "automation.notification_record",
        "通知发送记录",
        "/api/v1/automation/notification-records",
    ),
    *_button_permissions(
        "jobs.workflow_run",
        "流程执行",
        [
            {"code": "read", "name": "查看"},
            {"code": "cancel", "name": "取消"},
            {"code": "retry", "name": "重试"},
        ],
    ),
    # 作业中心菜单废弃后，以下按钮权限改由 SYSTEM_PERMISSIONS 独立维护，
    # 供作业系统快速执行、任务系统定时任务页面继续使用。
    *_button_permissions(
        "jobs.quick_command",
        "快捷命令",
        [
            {"code": "execute", "name": "执行脚本"},
        ],
    ),
    *_button_permissions(
        "jobs.playbook_run",
        "剧本执行",
        [
            {"code": "execute", "name": "执行Playbook"},
        ],
    ),
    *_button_permissions(
        "jobs.module_run",
        "模块执行",
        [
            {"code": "execute", "name": "执行模块"},
        ],
    ),
    *_button_permissions(
        "jobs.scheduled_job",
        "定时任务",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "run_now", "name": "立即执行"},
        ],
    ),
    *_button_permissions(
        "jobs.workflow_ticket",
        "任务单",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
            {"code": "run", "name": "运行"},
        ],
    ),
    *_read_permissions(
        "jobs.node_run",
        "节点执行",
        "/api/v1/jobs/node-runs",
        extra_actions=[
            {
                "code": "host_results",
                "name": "节点主机结果",
                "path": "/api/v1/jobs/node-runs/:id/host-results",
                "method": "GET",
            },
            {
                "code": "attempts",
                "name": "节点执行尝试",
                "path": "/api/v1/jobs/node-runs/:id/attempts",
                "method": "GET",
            },
            {
                "code": "retry",
                "name": "重试节点",
                "path": "/api/v1/jobs/node-runs/:id/retry",
                "method": "POST",
            },
            {
                "code": "ignore",
                "name": "忽略节点失败",
                "path": "/api/v1/jobs/node-runs/:id/ignore",
                "method": "POST",
            },
        ],
    ),
    *_read_permissions("jobs.host_result", "主机执行结果", "/api/v1/jobs/host-results"),
    *_read_permissions("audit.event", "平台审计", "/api/v1/audit/events"),
    *_read_permissions("audit.login_event", "登录日志", "/api/v1/audit/login-events"),
    {
        "code": "audit.event.export",
        "name": "导出审计事件",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/audit/events/export",
        "method": "GET",
    },
    *_rest_permissions(
        "jobs.scheduled_job",
        "定时任务",
        "/api/v1/jobs/scheduled-jobs",
        extra_actions=[
            {
                "code": "preview",
                "name": "预览定时任务执行范围",
                "path": "/api/v1/jobs/scheduled-jobs/:id/preview",
                "method": "GET",
            },
            {
                "code": "run_now",
                "name": "立即执行定时任务",
                "path": "/api/v1/jobs/scheduled-jobs/:id/run-now",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "jobs.workflow_ticket",
        "任务单",
        "/api/v1/tasks/tickets",
        extra_actions=[
            {
                "code": "preview",
                "name": "预览任务单执行范围",
                "path": "/api/v1/tasks/tickets/:id/preview",
                "method": "GET",
            },
            {
                "code": "run",
                "name": "运行任务单",
                "path": "/api/v1/tasks/tickets/:id/run",
                "method": "POST",
            },
        ],
    ),
    {
        "code": "logs.list",
        "name": "日志列表",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/logs",
        "method": "GET",
    },
    {
        "code": "logs.analytics.overview",
        "name": "访问概览统计",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/logs/analytics/overview",
        "method": "GET",
    },
    {
        "code": "logs.analytics.trend",
        "name": "访问趋势统计",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/logs/analytics/trend",
        "method": "GET",
    },
    *_rest_permissions(
        "wiki.page",
        "知识库文档",
        "/api/v1/wiki/pages",
        extra_actions=[
            {
                "code": "tree",
                "name": "知识库目录树",
                "path": "/api/v1/wiki/pages/tree",
                "method": "GET",
            },
        ],
    ),
    *_button_permissions(
        "wiki.page",
        "知识库文档",
        [
            {"code": "create", "name": "新建"},
            {"code": "update", "name": "保存"},
            {"code": "delete", "name": "删除"},
        ],
    ),
]

SYSTEM_MENU_API_PERMISSIONS = {
    "menu.monitoring.consul": (
        "consul.connection.datacenters",
        "consul.connection.catalog_services",
        "consul.connection.catalog_instances",
        "consul.connection.list",
        "consul.connection.detail",
        "consul.connection.services",
    ),
    "consul.connection:create": ("consul.connection.create",),
    "consul.connection:update": (
        "consul.connection.update",
        "consul.connection.detail",
    ),
    "consul.connection:delete": ("consul.connection.delete",),
    "consul.connection:test": ("consul.connection.test",),
    "consul.connection:kv": (
        "consul.connection.kv_keys",
        "consul.connection.kv_value",
    ),
    "consul.connection:kv_edit": (
        "consul.connection.kv_write",
        "consul.connection.kv_delete",
    ),
    "menu.monitoring.consul_template": (
        "consul.template.list",
        "consul.template.detail",
        "cmdb.host.list",
    ),
    "consul.template:create": ("consul.template.create", "cmdb.host.list"),
    "consul.template:update": (
        "consul.template.update",
        "consul.template.detail",
        "cmdb.host.list",
    ),
    "consul.template:delete": ("consul.template.delete",),
    "consul.template:read_remote": (
        "consul.template.read_remote",
        "consul.template.read_status",
        "consul.template.compare_remote",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.detail",
    ),
    "consul.template:deploy": (
        "consul.template.deploy",
        "consul.template.detail",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.detail",
        "consul.template.read_remote",
        "consul.template.read_status",
        "consul.template.compare_remote",
    ),
    "menu.monitoring.targets": (
        "monitoring.target.list",
        "monitoring.target.detail",
        "monitoring.target.preview",
        "monitoring.target.config",
        "monitoring.target.rules",
        "monitoring.record.list",
        "monitoring.record.detail",
        "consul.connection.list",
    ),
    "monitoring.target:create": (
        "monitoring.target.create",
        "consul.connection.list",
        "cmdb.host.list",
    ),
    "monitoring.target:host_import": (
        "monitoring.target.host_import_preview",
        "monitoring.target.host_import",
        "consul.connection.list",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.host_group.list",
        "monitoring.target.sync",
    ),
    "monitoring.target:update": (
        "monitoring.target.update",
        "monitoring.target.detail",
        "consul.connection.list",
        "cmdb.host.list",
    ),
    "monitoring.target:delete": ("monitoring.target.delete",),
    "monitoring.target:sync": ("monitoring.target.sync", "cmdb.host.detail"),
    "monitoring.target:deregister": ("monitoring.target.deregister",),
    "menu.task.provisioning": (
        "provisioning.request.list",
        "provisioning.request.detail",
        "provisioning.request.events",
        "provisioning.request.state-versions",
        "provisioning.template.list",
        "provisioning.version.list",
        "provisioning.credential.list",
    ),
    "menu.automation_resources.provisioning": (
        "provisioning.template.list",
        "provisioning.version.list",
    ),
    "menu.task.dashboard": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.summary",
        "jobs.dashboard.health",
        "jobs.dashboard.execution_distribution",
    ),
    "menu.task.list": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.export",
        "jobs.workflow_run.create",
        "jobs.workflow_run.validate",
        "jobs.workflow_ticket.list",
        "jobs.workflow_ticket.detail",
        "jobs.workflow_ticket.create",
        "jobs.workflow_ticket.update",
        "jobs.workflow_ticket.delete",
        "jobs.workflow_ticket.run",
        "jobs.workflow_ticket.preview",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "menu.task.run_create": (
        "jobs.workflow_run.create",
        "jobs.workflow_run.validate",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "menu.task.templates": (
        "automation.workflow.list",
        "automation.workflow.detail",
        "automation.workflow.create",
        "automation.workflow.update",
        "automation.workflow.delete",
        "automation.workflow.versions",
        "automation.workflow.copy",
        "automation.workflow_version.list",
        "automation.workflow_version.detail",
        "automation.workflow_version.update",
        "automation.workflow_version.publish",
    ),
    "menu.task.flow_design": (
        "automation.workflow_version.list",
        "automation.workflow_version.detail",
        "automation.workflow_version.graph",
        "automation.workflow_version.validate",
        "automation.workflow_version.publish",
        "automation.template.list",
        "automation.node_resource.list",
        "automation.api_endpoint.list",
        "automation.jenkins_server.list",
        "automation.jenkins_server.jobs",
        "automation.jenkins_server.job_detail",
        "automation.notification_template.list",
    ),
    "menu.automation_resources.command": (
        "automation.node_resource.list",
        "automation.node_resource.create",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.create",
        "automation.command.update",
        "automation.command.delete",
        "automation.command.versions",
        "automation.command_version.list",
        "automation.command_version.detail",
        "automation.command_version.create",
        "automation.command_version.update",
        "automation.command_version.delete",
        "automation.command_version.publish",
        "automation.command_version.archive",
    ),
    "menu.automation_resources.script": (
        "automation.node_resource.list",
        "automation.node_resource.create",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.create",
        "automation.command.update",
        "automation.command.delete",
        "automation.command.versions",
        "automation.command_version.list",
        "automation.command_version.detail",
        "automation.command_version.create",
        "automation.command_version.update",
        "automation.command_version.delete",
        "automation.command_version.publish",
        "automation.command_version.archive",
    ),
    "menu.automation_resources.playbook": (
        "automation.node_resource.list",
        "automation.node_resource.create",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.create",
        "automation.command.update",
        "automation.command.delete",
        "automation.command.versions",
        "automation.command_version.list",
        "automation.command_version.detail",
        "automation.command_version.create",
        "automation.command_version.update",
        "automation.command_version.delete",
        "automation.command_version.publish",
        "automation.command_version.archive",
    ),
    "menu.automation_resources.module": (
        "automation.node_resource.list",
        "automation.node_resource.create",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.create",
        "automation.command.update",
        "automation.command.delete",
        "automation.command.versions",
        "automation.command_version.list",
        "automation.command_version.detail",
        "automation.command_version.create",
        "automation.command_version.update",
        "automation.command_version.delete",
        "automation.command_version.publish",
        "automation.command_version.archive",
    ),
    "menu.automation_resources.api": (
        "automation.node_resource.list",
        "automation.api_endpoint.list",
        "automation.api_endpoint.detail",
        "automation.api_endpoint.create",
        "automation.api_endpoint.update",
        "automation.api_endpoint.delete",
        "automation.api_endpoint.test",
    ),
    "menu.automation_resources.jenkins": (
        "automation.node_resource.list",
        "automation.jenkins_server.list",
        "automation.jenkins_server.detail",
        "automation.jenkins_server.create",
        "automation.jenkins_server.update",
        "automation.jenkins_server.delete",
        "automation.jenkins_server.jobs",
        "automation.jenkins_server.job_detail",
        "automation.jenkins_job.list",
        "automation.jenkins_job.detail",
        "automation.jenkins_job.run",
        "automation.jenkins_build.list",
        "automation.jenkins_build.detail",
        "automation.jenkins_build.stop",
        "automation.jenkins_build.refresh",
    ),
    "menu.automation_resources.git": (
        "automation.node_resource.list",
        "automation.git_repository.list",
        "automation.git_repository.detail",
        "automation.git_repository.create",
        "automation.git_repository.update",
        "automation.git_repository.delete",
        "automation.git_repository.files",
        "automation.git_repository.load",
    ),
    "menu.task.execution": (
        "automation.workflow_version.graph",
        "jobs.workflow_run.detail",
        "jobs.workflow_run.nodes",
        "jobs.workflow_run.events",
        "jobs.workflow_run.realtime_ticket",
        "jobs.workflow_run.log",
        "jobs.node_run.detail",
        "jobs.node_run.host_results",
        "jobs.node_run.attempts",
    ),
    "menu.automation_resources.notification": (
        "automation.notification_channel.list",
        "automation.notification_channel.detail",
        "automation.notification_channel.create",
        "automation.notification_channel.update",
        "automation.notification_channel.delete",
        "automation.notification_template.list",
        "automation.notification_template.detail",
        "automation.notification_template.create",
        "automation.notification_template.update",
        "automation.notification_template.delete",
        "automation.notification_template.test_send",
        "automation.notification_template.variables",
        "automation.notification_template.preview",
        "automation.notification_record.list",
        "automation.notification_record.detail",
    ),
    "menu.audit.events": (
        "audit.event.list",
        "audit.event.detail",
    ),
    "menu.audit.login": (
        "audit.login_event.list",
        "audit.login_event.detail",
    ),
    "menu.audit.operations": (
        "logs.list",
        "logs.analytics.overview",
        "logs.analytics.trend",
    ),
    "menu.system.user": (
        "template.user.list",
        "template.user.detail",
        "template.user.options",
        "template.user.form",
    ),
    "menu.system.dept": (
        "template.dept.list",
        "template.dept.detail",
        "template.dept.options",
        "template.dept.form",
    ),
    "menu.system.role": (
        "template.role.list",
        "template.role.detail",
        "template.role.options",
        "template.role.form",
        "template.role.menu_ids",
        "template.role.dept_ids",
    ),
    "menu.system.menu": (
        "template.menu.list",
        "template.menu.detail",
        "template.menu.options",
        "template.menu.form",
        "permission.permission.options",
    ),
    "menu.system.dict": (
        "template.dict.list",
        "template.dict.detail",
        "template.dict.options",
        "template.dict.form",
        "template.dict.items.list",
        "template.dict.items.options",
    ),
    "menu.system.dict_item": (
        "template.dict.items.list",
        "template.dict.items.options",
        "template.dict.items.form",
    ),
    "menu.system.config": (
        "template.config.list",
        "template.config.detail",
        "template.config.form",
        "template.config.snapshot",
    ),
    "menu.system.notification": (
        "notification.email_settings.read",
        "notification.wecom.read",
        "notification.dingtalk.read",
        "notification.feishu.read",
    ),
    "sys:notification:update": (
        "notification.email_settings.update",
        "notification.wecom.update",
        "notification.dingtalk.update",
        "notification.feishu.update",
    ),
    "sys:notification:test": (
        "notification.email_settings.test",
        "notification.email_settings.test_connection",
        "notification.wecom.test",
        "notification.dingtalk.test",
        "notification.feishu.test",
    ),
    "sys:user:create": (
        "template.user.create",
        "template.role.options",
        "template.dept.options",
    ),
    "sys:user:update": (
        "template.user.update",
        "template.user.form",
        "template.role.options",
        "template.dept.options",
    ),
    "sys:user:delete": ("template.user.delete",),
    "sys:user:reset-password": ("template.user.password_reset",),
    "sys:user:import": ("template.user.import", "template.user.template"),
    "sys:user:export": ("template.user.export",),
    "sys:dept:create": ("template.dept.create",),
    "sys:dept:update": ("template.dept.update", "template.dept.form"),
    "sys:dept:delete": ("template.dept.delete",),
    "sys:role:create": (
        "template.role.create",
        "template.dept.options",
    ),
    "sys:role:update": (
        "template.role.update",
        "template.role.form",
        "template.dept.options",
    ),
    "sys:role:delete": ("template.role.delete",),
    "sys:role:assign": (
        "template.role.menu_ids",
        "template.role.menus",
        "template.role.dept_ids",
        "template.menu.options",
    ),
    "sys:menu:create": ("template.menu.create", "permission.permission.options"),
    "sys:menu:update": (
        "template.menu.update",
        "template.menu.form",
        "permission.permission.options",
    ),
    "sys:menu:delete": ("template.menu.delete",),
    "sys:dict:create": ("template.dict.create",),
    "sys:dict:update": ("template.dict.update", "template.dict.form"),
    "sys:dict:delete": ("template.dict.delete",),
    "sys:dict:item": (
        "template.dict.items.list",
        "template.dict.items.options",
    ),
    "sys:dict-item:create": ("template.dict.items.create",),
    "sys:dict-item:update": (
        "template.dict.items.update",
        "template.dict.items.form",
    ),
    "sys:dict-item:delete": ("template.dict.items.delete",),
    "sys:config:create": ("template.config.create",),
    "sys:config:update": ("template.config.update", "template.config.form"),
    "sys:config:delete": ("template.config.delete",),
    "sys:config:refresh": ("template.config.refresh",),
    "cmdb.host:read": (
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.host_group.list",
        "cmdb.host_group.detail",
        "cmdb.tag.list",
        "cmdb.tag.detail",
        "cmdb.credential_ref.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
        "cmdb.host.relations",
        "cmdb.search.list",
    ),
    "cmdb.host:create": (
        "cmdb.host.create",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "cmdb.tag.create",
        "cmdb.credential_ref.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "cmdb.host.relations",
    ),
    "cmdb.host:update": (
        "cmdb.host.update",
        "cmdb.host.detail",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "cmdb.tag.create",
        "cmdb.credential_ref.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "cmdb.host.relations",
    ),
    "cmdb.host:delete": ("cmdb.host.delete",),
    "cmdb.host:bulk_import": (
        "cmdb.host.bulk_import",
        "cmdb.host.excel_import",
    ),
    "cmdb.group:read": (
        "cmdb.host_group.list",
        "cmdb.host_group.detail",
        "cmdb.tag.list",
        "cmdb.tag.detail",
        "cmdb.host.list",
    ),
    "cmdb.business:read": (
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
        "cmdb.asset_source.sync",
        "cmdb.asset_source.preview_sync",
        "cmdb.asset_sync_record.list",
        "cmdb.search.list",
    ),
    "cmdb.asset_source:read": (
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
        "cmdb.asset_source.preview_sync",
        "cmdb.asset_sync_record.list",
    ),
    "cmdb.asset_source:create": (
        "cmdb.asset_source.create",
        "cmdb.asset_source.test_connection",
    ),
    "cmdb.asset_source:update": (
        "cmdb.asset_source.update",
        "cmdb.asset_source.detail",
        "cmdb.asset_source.test_connection",
    ),
    "cmdb.host_group:create": ("cmdb.host_group.create",),
    "cmdb.host_group:update": (
        "cmdb.host_group.update",
        "cmdb.host_group.detail",
        "cmdb.host_group.members",
        "cmdb.host.list",
    ),
    "cmdb.host_group:delete": ("cmdb.host_group.delete",),
    "cmdb.host_group:members": (
        "cmdb.host_group.members",
        "cmdb.host.list",
    ),
    "cmdb.tag:create": ("cmdb.tag.create",),
    "cmdb.execution:read": (
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "jobs.worker_pool:create": ("jobs.worker_pool.create",),
    "jobs.worker_pool:update": (
        "jobs.worker_pool.update",
        "jobs.worker_pool.detail",
    ),
    "jobs.worker_pool:delete": ("jobs.worker_pool.delete",),
    "cmdb.credential_ref:read": (
        "cmdb.credential_ref.list",
        "cmdb.credential_ref.detail",
    ),
    "cmdb.credential_ref:create": ("cmdb.credential_ref.create",),
    "cmdb.credential_ref:update": (
        "cmdb.credential_ref.update",
        "cmdb.credential_ref.detail",
    ),
    "cmdb.credential_ref:delete": ("cmdb.credential_ref.delete",),
    "jobs.quick_command:execute": (
        "jobs.quick_command.create",
        "jobs.quick_command.preview",
        "automation.template.list",
        "automation.command_version.list",
        "automation.command_version.detail",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "jobs.playbook_run:execute": (
        "jobs.playbook_run.create",
        "jobs.playbook_run.preview",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.versions",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "jobs.module_run:execute": (
        "jobs.module_run.create",
        "jobs.module_run.preview",
        "automation.command.list",
        "automation.command.detail",
        "automation.command.versions",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "menu.ops.settings": (
        "jobs.gateway.list",
        "jobs.gateway.detail",
        "jobs.gateway.create",
        "jobs.gateway.update",
        "jobs.gateway.delete",
        "jobs.gateway.test",
    ),
    "jobs.workflow_run:create": (
        "jobs.workflow_run.create",
        "jobs.workflow_run.validate",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "jobs.workflow_run:read": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.summary",
        "jobs.workflow_run.detail",
        "jobs.workflow_run.nodes",
        "jobs.workflow_run.events",
        "jobs.workflow_run.realtime_ticket",
        "jobs.workflow_run.log",
        "jobs.node_run.list",
        "jobs.node_run.detail",
        "jobs.node_run.host_results",
        "jobs.node_run.attempts",
        "jobs.host_result.list",
    ),
    "jobs.workflow_run:cancel": ("jobs.workflow_run.cancel",),
    "jobs.workflow_run:retry": (
        "jobs.workflow_run.retry_failed",
        "jobs.workflow_run.rerun",
        "jobs.node_run.retry",
        "jobs.node_run.ignore",
    ),
    "ops.workflow_run:read": (
        "ops.workflow_run.list",
        "ops.workflow_run.summary",
        "ops.workflow_run.detail",
        "ops.workflow_run.nodes",
        "ops.workflow_run.events",
        "ops.workflow_run.realtime_ticket",
        "ops.workflow_run.log",
        "jobs.node_run.list",
        "jobs.node_run.detail",
        "jobs.node_run.host_results",
        "jobs.node_run.attempts",
        "jobs.host_result.list",
    ),
    "ops.workflow_run:cancel": ("ops.workflow_run.cancel",),
    "ops.workflow_run:retry": (
        "ops.workflow_run.retry_failed",
        "ops.workflow_run.rerun",
        "jobs.node_run.retry",
        "jobs.node_run.ignore",
    ),
    "automation.workflow_graph:manage": (
        "automation.workflow.list",
        "automation.workflow.detail",
        "automation.workflow_version.list",
        "automation.workflow_version.detail",
        "automation.workflow_version.validate",
        "automation.workflow_version.graph",
        "automation.workflow_version.publish",
        "automation.workflow_node.list",
        "automation.workflow_node.create",
        "automation.workflow_node.update",
        "automation.workflow_node.delete",
        "automation.workflow_edge.list",
        "automation.workflow_edge.create",
        "automation.workflow_edge.update",
        "automation.workflow_edge.delete",
    ),
    "jobs.scheduled_job:create": (
        "jobs.scheduled_job.create",
        "jobs.workflow_run.validate",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.list",
        "jobs.worker_pool.detail",
    ),
    "jobs.scheduled_job:update": (
        "jobs.scheduled_job.update",
        "jobs.scheduled_job.detail",
        "jobs.workflow_run.validate",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.detail",
    ),
    "jobs.scheduled_job:delete": ("jobs.scheduled_job.delete",),
    "jobs.scheduled_job:run_now": (
        "jobs.scheduled_job.run_now",
        "jobs.scheduled_job.preview",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.detail",
    ),
    "jobs.workflow_ticket:create": (
        "jobs.workflow_ticket.create",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "jobs.worker_pool.list",
    ),
    "jobs.workflow_ticket:update": (
        "jobs.workflow_ticket.update",
        "jobs.workflow_ticket.detail",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "jobs.worker_pool.list",
    ),
    "jobs.workflow_ticket:delete": ("jobs.workflow_ticket.delete",),
    "jobs.workflow_ticket:run": (
        "jobs.workflow_ticket.run",
        "jobs.workflow_ticket.preview",
        "cmdb.host.detail",
        "cmdb.credential_ref.detail",
        "jobs.worker_pool.detail",
    ),
    "menu.wiki.docs": (
        "wiki.page.list",
        "wiki.page.detail",
        "wiki.page.tree",
    ),
    "wiki.page:create": ("wiki.page.create",),
    "wiki.page:update": (
        "wiki.page.update",
        "wiki.page.detail",
    ),
    "wiki.page:delete": ("wiki.page.delete",),
}

from .observability import ADDITIONAL_MENU_API_PERMISSIONS, ADDITIONAL_PERMISSIONS

SYSTEM_PERMISSIONS.extend(ADDITIONAL_PERMISSIONS)
SYSTEM_MENU_API_PERMISSIONS.update(ADDITIONAL_MENU_API_PERMISSIONS)
