"""删除已合并到"快速执行"的 Playbook执行 / Module执行 菜单。

统一执行页（ops/quick-execute）已支持命令、Playbook、Module 三种执行类型，
原独立的 Playbook执行菜单、Module执行菜单不再需要。

仅删除 Menu 记录，不影响 Permission 记录（M2M 关系，不级联）。
jobs.module_catalog:* 按钮权限改为挂在"快速执行菜单"下，
由 seed_system_settings（--sync-menu-layout）重建。
"""

from django.db import migrations


def remove_menu_tree(Menu, name):
    """递归删除指定名称的菜单（可为非顶级）及其所有子孙。"""
    root = Menu.objects.filter(name=name).first()
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


def remove_playbook_module_menus(apps, schema_editor):
    """删除 Playbook执行 / Module执行 两棵子菜单树。"""
    Menu = apps.get_model("permission", "Menu")

    remove_menu_tree(Menu, "Playbook执行菜单")
    remove_menu_tree(Menu, "Module执行菜单")


def restore_playbook_module_menus(apps, schema_editor):
    """反向操作：重跑 seed 可恢复。"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0019_unify_menu_structure"),
    ]

    operations = [
        migrations.RunPython(
            remove_playbook_module_menus, restore_playbook_module_menus
        ),
    ]
