"""API / 菜单权限种子数据。"""

from apps.permission.models import Permission


# 作业中心菜单已废弃（被作业系统/任务系统替代），其 menu.jobs.* 菜单权限不再存在，
# 旧 API 权限码的角色迁移已历史执行完毕，故清空映射，避免重跑 seed 时因目标菜单缺失而报错。
LEGACY_MENU_PERMISSION_REPLACEMENTS = {}


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
        "cmdb.business",
        "业务",
        "/api/v1/cmdb/businesses",
    ),
    *_button_permissions(
        "cmdb.business",
        "业务",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "cmdb.asset_source",
        "资源来源",
        "/api/v1/cmdb/asset-sources",
        extra_actions=[
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
    *_rest_permissions(
        "cmdb.service_tree_node",
        "服务树节点",
        "/api/v1/cmdb/service-tree-nodes",
    ),
    *_button_permissions(
        "cmdb.service_tree_node",
        "服务树节点",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions("cmdb.tag", "主机标签", "/api/v1/cmdb/tags"),
    *_button_permissions(
        "cmdb.tag",
        "主机标签",
        [
            {"code": "create", "name": "新增"},
            {"code": "update", "name": "编辑"},
            {"code": "delete", "name": "删除"},
        ],
    ),
    *_rest_permissions(
        "cmdb.credential_ref",
        "凭据引用",
        "/api/v1/cmdb/credential-refs",
    ),
    *_button_permissions(
        "cmdb.credential_ref",
        "凭据引用",
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
        "工作流",
        "/api/v1/automation/workflows",
        extra_actions=[
            {
                "code": "versions",
                "name": "工作流版本列表和创建",
                "path": "/api/v1/automation/workflows/:id/versions",
                "method": "GET|POST",
            },
            {
                "code": "copy",
                "name": "复制工作流",
                "path": "/api/v1/automation/workflows/:id/copy",
                "method": "POST",
            },
        ],
    ),
    *_button_permissions(
        "automation.workflow",
        "工作流",
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
        "工作流版本",
        "/api/v1/automation/workflow-versions",
        extra_actions=[
            {
                "code": "publish",
                "name": "工作流版本发布",
                "path": "/api/v1/automation/workflow-versions/:id/publish",
                "method": "POST",
            },
            {
                "code": "archive",
                "name": "工作流版本归档",
                "path": "/api/v1/automation/workflow-versions/:id/archive",
                "method": "POST",
            },
            {
                "code": "validate",
                "name": "工作流版本校验",
                "path": "/api/v1/automation/workflow-versions/:id/validate",
                "method": "POST",
            },
        ],
    ),
    *_rest_permissions(
        "automation.workflow_node",
        "工作流节点",
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
                "code": "validate",
                "name": "校验任务执行参数",
                "path": "/api/v1/tasks/runs/validate",
                "method": "POST",
            },
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
        "工作流连线",
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
    {
        "code": "jobs.dashboard.health",
        "name": "任务平台健康状态",
        "type": Permission.PermissionType.API,
        "path": "/api/v1/jobs/dashboard/health",
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
        "工作流执行",
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
            {"code": "execute", "name": "执行命令"},
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
    *_read_permissions("jobs.event", "执行事件", "/api/v1/jobs/events"),
    *_read_permissions("audit.event", "平台审计", "/api/v1/audit/events"),
    {"code": "audit.event.export", "name": "导出审计事件", "type": Permission.PermissionType.API, "path": "/api/v1/audit/events/export", "method": "GET"},
    *_rest_permissions(
        "jobs.scheduled_job",
        "定时任务",
        "/api/v1/jobs/scheduled-jobs",
        extra_actions=[
            {
                "code": "run_now",
                "name": "立即执行定时任务",
                "path": "/api/v1/jobs/scheduled-jobs/:id/run-now",
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
]

SYSTEM_MENU_API_PERMISSIONS = {
    "menu.task.dashboard": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.summary",
        "jobs.dashboard.health",
    ),
    "menu.task.list": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.export",
        "jobs.workflow_run.create",
        "jobs.workflow_run.validate",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "jobs.worker_pool.list",
    ),
    "menu.task.run_create": (
        "jobs.workflow_run.create",
        "jobs.workflow_run.validate",
        "automation.workflow_version.list",
        "cmdb.host.list",
        "jobs.worker_pool.list",
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
    "menu.task.execution": (
        "automation.workflow_version.graph",
        "jobs.workflow_run.detail",
        "jobs.workflow_run.nodes",
        "jobs.workflow_run.events",
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
        "automation.notification_record.list",
        "automation.notification_record.detail",
    ),
    "menu.audit.events": (
        "audit.event.list",
        "audit.event.detail",
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
    "menu.system.log": (
        "logs.list",
        "logs.analytics.overview",
        "logs.analytics.trend",
    ),
    "menu.system.config": (
        "template.config.list",
        "template.config.detail",
        "template.config.form",
        "template.config.snapshot",
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
        "cmdb.business.list",
        "cmdb.business.detail",
        "cmdb.service_tree_node.list",
        "cmdb.service_tree_node.detail",
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
        "cmdb.asset_sync_record.list",
        "cmdb.host.relations",
        "cmdb.search.list",
    ),
    "cmdb.host:create": (
        "cmdb.host.create",
        "cmdb.host_group.list",
        "cmdb.tag.list",
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
        "cmdb.business.list",
        "cmdb.business.detail",
        "cmdb.service_tree_node.list",
        "cmdb.service_tree_node.detail",
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
        "cmdb.asset_source.sync",
        "cmdb.asset_sync_record.list",
        "cmdb.search.list",
    ),
    "cmdb.asset_source:read": (
        "cmdb.asset_source.list",
        "cmdb.asset_source.detail",
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
    "cmdb.tag:update": (
        "cmdb.tag.update",
        "cmdb.tag.detail",
    ),
    "cmdb.tag:delete": ("cmdb.tag.delete",),
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
        "automation.template.list",
        "automation.command_version.list",
        "automation.command_version.detail",
        "cmdb.host.list",
        "cmdb.host_group.list",
        "cmdb.tag.list",
        "jobs.gateway.list",
        "jobs.worker_pool.list",
    ),
    "menu.ops.settings": (
        "jobs.gateway.list",
        "jobs.gateway.detail",
        "jobs.gateway.create",
        "jobs.gateway.update",
        "jobs.gateway.delete",
        "jobs.gateway.test",
    ),
    "jobs.workflow_run:read": (
        "jobs.workflow_run.list",
        "jobs.workflow_run.summary",
        "jobs.workflow_run.detail",
        "jobs.workflow_run.nodes",
        "jobs.workflow_run.events",
        "jobs.workflow_run.log",
        "jobs.node_run.list",
        "jobs.node_run.detail",
        "jobs.node_run.host_results",
        "jobs.node_run.attempts",
        "jobs.host_result.list",
        "jobs.event.list",
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
        "ops.workflow_run.log",
        "jobs.node_run.list",
        "jobs.node_run.detail",
        "jobs.node_run.host_results",
        "jobs.node_run.attempts",
        "jobs.host_result.list",
        "jobs.event.list",
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
        "automation.workflow_version.list",
        "cmdb.host.list",
        "jobs.worker_pool.list",
    ),
    "jobs.scheduled_job:update": (
        "jobs.scheduled_job.update",
        "jobs.scheduled_job.detail",
    ),
    "jobs.scheduled_job:delete": ("jobs.scheduled_job.delete",),
    "jobs.scheduled_job:run_now": ("jobs.scheduled_job.run_now",),
}
