"""删除已废弃的"作业中心"菜单树（被作业系统/任务系统替代）。

仅删除 Menu 记录，不影响 Permission 记录（M2M 关系，不级联）。
角色已分配的按钮权限（jobs.quick_command:execute、jobs.scheduled_job:* 等）
仍保留在 permission 表中，由 SYSTEM_PERMISSIONS 独立维护。
"""

from django.db import migrations


def remove_job_center_menu(apps, schema_editor):
    """递归删除 JobCenter 目录及其所有子孙菜单。"""
    Menu = apps.get_model("permission", "Menu")

    root = Menu.objects.filter(name="JobCenter").first()
    if root is None:
        return

    # 递归收集所有子孙 ID
    to_delete = [root.pk]
    queue = [root.pk]
    while queue:
        parent_ids = queue
        queue = list(
            Menu.objects.filter(pid_id__in=parent_ids).values_list("pk", flat=True)
        )
        to_delete.extend(queue)

    Menu.objects.filter(pk__in=to_delete).delete()


def restore_job_center_menu(apps, schema_editor):
    """反向操作：提示通过 seed 命令恢复。"""
    # 作业中心菜单已废弃，不再恢复。
    # 如需恢复，请运行 python manage.py seed_system_settings。
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0017_add_ops_task_menus"),
    ]

    operations = [
        migrations.RunPython(remove_job_center_menu, restore_job_center_menu),
    ]
