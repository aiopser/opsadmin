from django.db import migrations
from django.db.models import F


def repair_menu_data(apps, schema_editor):
    Menu = apps.get_model("permission", "Menu")
    menus = Menu.objects.using(schema_editor.connection.alias)
    # Only clear the identifiable icon-copy corruption; preserve real links.
    menus.exclude(icon="").exclude(icon__isnull=True).filter(
        href=F("icon"), href__contains=":"
    ).exclude(href__startswith="http://").exclude(href__startswith="https://").update(href=None)
    # Older editors generated /User and /Role from route names. These are
    # built-in child paths, not custom absolute routes. Keep IDs and permissions.
    for name, segment in (("User", "user"), ("Role", "role")):
        menus.filter(
            name=name, path=f"/{name}", pid__path="/system",
            component__in=[f"system/{segment}/index", f"view.system/{segment}/index", f"view.{name}", f"view.manage_{segment}"],
        ).update(path=segment)


class Migration(migrations.Migration):
    dependencies = [("permission", "0004_role_job_data_scope")]
    operations = [migrations.RunPython(repair_menu_data, migrations.RunPython.noop)]
