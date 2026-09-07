from django.db import migrations, models


def move_all_menus_to_system(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    Menu.objects.exclude(menu_group="system").update(menu_group="system")


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0008_access_log_and_system_flags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="menu",
            name="menu_group",
            field=models.CharField(
                choices=[("system", "系统设置")],
                db_index=True,
                default="system",
                max_length=32,
                verbose_name="菜单分组",
            ),
        ),
        migrations.RunPython(move_all_menus_to_system, migrations.RunPython.noop),
    ]
