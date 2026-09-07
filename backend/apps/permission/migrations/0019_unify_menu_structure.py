"""统一菜单结构：删除旧的 Ops/Task/OpsAutomation 菜单树。

这些菜单将被 seed_system_settings 命令以新的 SYSTEM_MENUS 定义重建：
- OpsAutomation(/ops) → 拆分为 Ops(/ops) + Cmdb(/cmdb)
- Ops(/ops, migration 0017) → 由 SYSTEM_MENUS 管理
- Task(/task, migration 0017) → 由 SYSTEM_MENUS 管理

仅删除 Menu 记录，Permission 记录保留（M2M 不级联）。
"""

from django.db import migrations


def remove_legacy_menu_tree(Menu, root_name):
    """递归删除指定名称的顶级菜单及其所有子孙。"""
    root = Menu.objects.filter(name=root_name, pid__isnull=True).first()
    if root is None:
        return

    to_delete = [root.pk]
    queue = [root.pk]
    while queue:
        parent_ids = queue
        queue = list(
            Menu.objects.filter(pid_id__in=parent_ids).values_list("pk", flat=True)
        )
        to_delete.extend(queue)

    Menu.objects.filter(pk__in=to_delete).delete()


def unify_menu_structure(apps, schema_editor):
    """删除三棵旧菜单树，为 seed 重建做准备。"""
    Menu = apps.get_model("permission", "Menu")

    # migration 0017 创建的作业系统/任务系统
    remove_legacy_menu_tree(Menu, "Ops")
    remove_legacy_menu_tree(Menu, "Task")
    # 旧"自动化运维"目录（seed 历史创建）
    remove_legacy_menu_tree(Menu, "OpsAutomation")


def restore_legacy_menus(apps, schema_editor):
    """反向操作：重跑 seed 可恢复。"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0018_remove_job_center_menu"),
    ]

    operations = [
        migrations.RunPython(unify_menu_structure, restore_legacy_menus),
    ]
