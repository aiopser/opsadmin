from django.db import migrations, models


def infer_menu_types(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    for menu in Menu.objects.all():
        has_children = Menu.objects.filter(pid_id=menu.id).exists()
        component = menu.component or ""
        if has_children or component in ("Layout", "ParentView"):
            menu.menu_type = "C"
        elif component:
            menu.menu_type = "M"
        else:
            menu.menu_type = "M"
        menu.save(update_fields=["menu_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0014_auto_20260622_1123"),
    ]

    operations = [
        migrations.AddField(
            model_name="menu",
            name="menu_type",
            field=models.CharField(
                choices=[("C", "Catalog"), ("M", "Menu"), ("B", "Button")],
                db_index=True,
                default="M",
                max_length=1,
                verbose_name="Menu type",
            ),
        ),
        migrations.RunPython(infer_menu_types, migrations.RunPython.noop),
    ]
