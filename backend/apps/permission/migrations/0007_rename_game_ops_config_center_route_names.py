from django.db import migrations

# 目录路由 name 含下划线会被前端 elegant-router transform 误判为多级路由，
# 导致子页面脱离 layout.base 全屏渲染。连字符目录（game-ops/config-center）
# 的路由 name 必须保留连字符，与前端 routeMap 命名一致。
OLD_TO_NEW = {
    "game_ops": "game-ops",
    "game_ops_projects": "game-ops_projects",
    "game_ops_profiles": "game-ops_profiles",
    "game_ops_tasks": "game-ops_tasks",
    "config_center": "config-center",
    "config_center_configs": "config-center_configs",
    "config_center_releases": "config-center_releases",
}


def rename_route_names(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    for old, new in OLD_TO_NEW.items():
        renamed = Menu.objects.filter(name=old, menu_group="system").update(name=new)
        if not renamed:
            Menu.objects.filter(name=old).update(name=new)


def revert_route_names(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    for old, new in OLD_TO_NEW.items():
        Menu.objects.filter(name=new, menu_group="system").update(name=old)


class Migration(migrations.Migration):
    dependencies = [
        ("permission", "0006_alter_systemconfig_config_group"),
    ]

    operations = [
        migrations.RunPython(rename_route_names, revert_route_names),
    ]
