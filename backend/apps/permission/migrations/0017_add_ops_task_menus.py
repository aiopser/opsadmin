"""插入作业系统、任务系统顶级菜单及子菜单，并更新旧 jobs/ 组件路径。"""

from django.db import migrations


OPS_MENUS = [
    {
        "path": "dashboard",
        "name": "OpsDashboard",
        "title": "工作台",
        "icon": "dashboard",
        "component": "ops/dashboard/index",
        "order": 1,
    },
    {
        "path": "quick-execute",
        "name": "OpsQuickExecute",
        "title": "快速执行",
        "icon": "el-icon-Promotion",
        "component": "ops/quick-execute/index",
        "order": 2,
    },
    {
        "path": "playbook",
        "name": "OpsPlaybook",
        "title": "Playbook执行",
        "icon": "notebook",
        "component": "ops/playbook/index",
        "order": 3,
    },
    {
        "path": "module",
        "name": "OpsModule",
        "title": "Module执行",
        "icon": "module",
        "component": "ops/module/index",
        "order": 4,
    },
    {
        "path": "history",
        "name": "OpsHistory",
        "title": "作业历史",
        "icon": "history",
        "component": "ops/history/index",
        "order": 5,
    },
    {
        "path": "audit",
        "name": "OpsAudit",
        "title": "审计日志",
        "icon": "audit",
        "component": "ops/audit/index",
        "order": 6,
    },
    {
        "path": "security",
        "name": "OpsSecurity",
        "title": "安全管控",
        "icon": "shield",
        "component": "ops/security/index",
        "order": 7,
    },
    {
        "path": "settings",
        "name": "OpsSettings",
        "title": "系统设置",
        "icon": "setting",
        "component": "ops/settings/index",
        "order": 8,
    },
]

TASK_MENUS = [
    {
        "path": "dashboard",
        "name": "TaskDashboard",
        "title": "工作台",
        "icon": "dashboard",
        "component": "task/dashboard/index",
        "order": 1,
    },
    {
        "path": "list",
        "name": "TaskList",
        "title": "任务管理",
        "icon": "list",
        "component": "task/list/index",
        "order": 2,
    },
    {
        "path": "templates",
        "name": "TaskTemplates",
        "title": "模板管理",
        "icon": "template",
        "component": "task/templates/index",
        "order": 3,
    },
    {
        "path": "flow-design",
        "name": "TaskFlowDesign",
        "title": "流程编排",
        "icon": "flow",
        "component": "task/flow-design/index",
        "order": 4,
    },
    {
        "path": "subtasks",
        "name": "TaskSubtasks",
        "title": "子任务管理",
        "icon": "subtask",
        "component": "task/subtasks/index",
        "order": 5,
    },
    {
        "path": "api-manage",
        "name": "TaskApiManage",
        "title": "API管理",
        "icon": "api",
        "component": "task/api-manage/index",
        "order": 6,
    },
    {
        "path": "jenkins",
        "name": "TaskJenkins",
        "title": "Jenkins集成",
        "icon": "jenkins",
        "component": "task/jenkins/index",
        "order": 7,
    },
    {
        "path": "execution/:id",
        "name": "TaskExecution",
        "title": "执行详情",
        "icon": "",
        "component": "task/execution/index",
        "order": 8,
        "hidden": True,
    },
    {
        "path": "schedule",
        "name": "TaskSchedule",
        "title": "定时任务",
        "icon": "el-icon-Timer",
        "component": "task/schedule/index",
        "order": 9,
    },
    {
        "path": "approval",
        "name": "TaskApproval",
        "title": "审批中心",
        "icon": "approval",
        "component": "task/approval/index",
        "order": 10,
    },
    {
        "path": "notify",
        "name": "TaskNotify",
        "title": "通知管理",
        "icon": "notify",
        "component": "task/notify/index",
        "order": 11,
    },
]

# 旧组件路径 -> 新组件路径
COMPONENT_PATH_UPDATES = {
    "jobs/quick-command/index": "ops/quick-execute/index",
    "jobs/workflow-run/index": "ops/history/index",
    "jobs/execution-detail/index": "ops/execution-detail/index",
    "jobs/templates/index": "task/templates/index",
    "jobs/schedule/index": "task/schedule/index",
}


def add_ops_task_menus(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")

    def create_catalog(path, name, title, icon, redirect, order, children):
        catalog, _ = Menu.objects.update_or_create(
            path=path,
            pid__isnull=True,
            defaults={
                "name": name,
                "title": title,
                "menu_type": "C",
                "icon": icon,
                "component": "Layout",
                "redirect": redirect,
                "order": order,
                "hidden": False,
                "always_show": True,
                "no_cache": False,
                "breadcrumb": False,
                "affix": False,
                "show_icon": True,
                "menu_group": "system",
            },
        )
        for child in children:
            Menu.objects.update_or_create(
                path=child["path"],
                pid=catalog,
                defaults={
                    "name": child["name"],
                    "title": child["title"],
                    "menu_type": "M",
                    "icon": child.get("icon", ""),
                    "component": child["component"],
                    "order": child["order"],
                    "hidden": child.get("hidden", False),
                    "always_show": True,
                    "no_cache": False,
                    "breadcrumb": False,
                    "affix": False,
                    "show_icon": True,
                    "menu_group": "system",
                },
            )
        return catalog

    create_catalog("/ops", "Ops", "作业系统", "ops", "/ops/dashboard", 10, OPS_MENUS)
    create_catalog("/task", "Task", "任务系统", "task", "/task/dashboard", 11, TASK_MENUS)

    # 更新旧路径引用
    for old_path, new_path in COMPONENT_PATH_UPDATES.items():
        Menu.objects.filter(component=old_path).update(component=new_path)


def remove_ops_task_menus(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    ops_catalog = Menu.objects.filter(path="/ops", pid__isnull=True).first()
    task_catalog = Menu.objects.filter(path="/task", pid__isnull=True).first()
    if ops_catalog:
        Menu.objects.filter(pid=ops_catalog).delete()
        ops_catalog.delete()
    if task_catalog:
        Menu.objects.filter(pid=task_catalog).delete()
        task_catalog.delete()
    # 还原组件路径
    for old_path, new_path in COMPONENT_PATH_UPDATES.items():
        Menu.objects.filter(component=new_path).update(component=old_path)


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0016_menu_show_icon"),
    ]

    operations = [
        migrations.RunPython(add_ops_task_menus, remove_ops_task_menus),
    ]
