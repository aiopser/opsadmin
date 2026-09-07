from django.db import migrations, models
import django.db.models.deletion


def convert_button_menus_to_menu_buttons(apps, schema_editor):
    """将 menu_type='B' 的按钮菜单行迁转为 MenuButton 记录。

    - 按钮权限标识取自行内 M2M 的 type='button' 权限，缺省回退到 path/title
    - 按钮描述取自原菜单 title
    - 原 M2M 权限（按钮权限标识 + API 权限）整体搬到 MenuButton.permission
    - 无父菜单的孤儿按钮行直接丢弃
    """
    Menu = apps.get_model("permission", "Menu")
    MenuButton = apps.get_model("permission", "MenuButton")

    button_menus = (
        Menu.objects.filter(menu_type="B")
        .select_related("pid")
        .prefetch_related("permission")
    )
    for button_menu in button_menus:
        parent = button_menu.pid
        if parent is None:
            continue
        permissions = list(button_menu.permission.all())
        button_permission = next(
            (item for item in permissions if item.type == "button"), None
        )
        code = (
            (button_permission.code if button_permission else None)
            or button_menu.path
            or button_menu.title
            or f"button:{button_menu.id}"
        )[:128]
        if button_permission and button_permission.name:
            desc = button_permission.name
        else:
            desc = button_menu.title or code
        desc = desc[:64]
        button, _ = MenuButton.objects.get_or_create(
            menu=parent,
            code=code,
            defaults={"desc": desc},
        )
        existing_ids = set(button.permission.values_list("id", flat=True))
        new_ids = [item.id for item in permissions if item.id not in existing_ids]
        if new_ids:
            button.permission.add(*new_ids)
    Menu.objects.filter(menu_type="B").delete()


def restore_button_menus_from_menu_buttons(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    MenuButton = apps.get_model("permission", "MenuButton")

    for button in MenuButton.objects.select_related("menu").prefetch_related(
        "permission"
    ):
        menu = Menu.objects.create(
            order=0,
            menu_type="B",
            path=button.code[:64],
            component=None,
            name=None,
            title=button.desc[:32],
            show_icon=False,
            pid=button.menu,
        )
        menu.permission.set(button.permission.all())


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0021_add_task_run_create_menu"),
    ]

    operations = [
        migrations.CreateModel(
            name="MenuButton",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "code",
                    models.CharField(
                        db_index=True, max_length=128, verbose_name="Button code"
                    ),
                ),
                (
                    "desc",
                    models.CharField(
                        max_length=64, verbose_name="Button description"
                    ),
                ),
                (
                    "menu",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="buttons",
                        to="permission.menu",
                        verbose_name="Menu",
                    ),
                ),
            ],
            options={
                "verbose_name": "Menu button",
                "verbose_name_plural": "Menu button",
                "db_table": "permission_menu_button",
                "unique_together": {("menu", "code")},
            },
        ),
        migrations.AddField(
            model_name="menubutton",
            name="permission",
            field=models.ManyToManyField(
                blank=True,
                related_name="menu_button",
                to="permission.Permission",
                verbose_name="Permission",
            ),
        ),
        migrations.RunPython(
            convert_button_menus_to_menu_buttons,
            restore_button_menus_from_menu_buttons,
        ),
        migrations.AlterField(
            model_name="menu",
            name="menu_type",
            field=models.CharField(
                choices=[("C", "Catalog"), ("M", "Menu")],
                db_index=True,
                default="M",
                max_length=1,
                verbose_name="Menu type",
            ),
        ),
    ]
