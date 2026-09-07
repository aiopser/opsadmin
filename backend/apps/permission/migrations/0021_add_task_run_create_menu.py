"""新增「发起任务」菜单（task 目录下，隐藏路由）。

作为独立执行入口，由工作台/任务管理跳转进入，不占侧边栏。
code 与 seed_data.SYSTEM_MENUS 中 menu.task.run_create 保持一致。
"""

from django.db import migrations


def add_run_create_menu(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    task_catalog = Menu.objects.filter(path="/task", pid__isnull=True).first()
    if task_catalog is None:
        return
    Menu.objects.update_or_create(
        path="run-create",
        pid=task_catalog,
        defaults={
            "name": "TaskRunCreate",
            "title": "发起任务",
            "menu_type": "M",
            "icon": "promotion",
            "component": "task/run-create/index",
            "order": 2,
            "hidden": True,
            "always_show": True,
            "no_cache": False,
            "breadcrumb": False,
            "affix": False,
            "show_icon": True,
            "menu_group": "system",
        },
    )


def remove_run_create_menu(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    task_catalog = Menu.objects.filter(path="/task", pid__isnull=True).first()
    if task_catalog is None:
        return
    Menu.objects.filter(path="run-create", pid=task_catalog).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0020_remove_playbook_module_menus"),
    ]

    operations = [
        migrations.RunPython(add_run_create_menu, remove_run_create_menu),
    ]