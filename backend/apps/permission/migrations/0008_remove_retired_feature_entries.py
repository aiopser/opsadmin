"""Retire the removed game/config feature menus without touching business history."""
from django.db import migrations
from django.db.models import Q
from django.utils import timezone


def remove_entries(apps, schema_editor):
    alias = schema_editor.connection.alias
    Menu = apps.get_model("permission", "Menu")
    Permission = apps.get_model("permission", "Permission")
    MenuButton = apps.get_model("permission", "MenuButton")
    feature = Q(
        name__in=["game_ops", "game-ops", "config_center", "config-center"],
        path__in=["/game-ops", "/config-center"],
    )
    feature |= Q(component__startswith="view.game-ops_") | Q(
        component__startswith="view.config-center_"
    )
    Menu.objects.using(alias).filter(menu_group="system").filter(feature).delete()
    MenuButton.objects.using(alias).filter(
        Q(code__startswith="game_ops.") | Q(code__startswith="config_center.")
    ).delete()
    Permission.objects.using(alias).filter(is_system=True).filter(
        Q(code__startswith="game_ops.")
        | Q(code__startswith="config_center.")
        | Q(code__startswith="menu.game_ops.")
        | Q(code__startswith="menu.config_center.")
    ).delete()

    # A DatabaseScheduler may have persisted the former static heartbeat.
    # Fresh installations may not have reached django-celery-beat migrations yet.
    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
        PeriodicTasks = apps.get_model("django_celery_beat", "PeriodicTasks")
    except LookupError:
        return
    tables = schema_editor.connection.introspection.table_names()
    if PeriodicTask._meta.db_table in tables:
        changed = (
            PeriodicTask.objects.using(alias)
            .filter(
                Q(task__startswith="game_ops.") | Q(task__startswith="config_center.")
            )
            .update(enabled=False)
        )
        if changed and PeriodicTasks._meta.db_table in tables:
            PeriodicTasks.objects.using(alias).update_or_create(
                ident=1, defaults={"last_update": timezone.now()}
            )


class Migration(migrations.Migration):
    dependencies = [("permission", "0007_rename_game_ops_config_center_route_names")]
    operations = [migrations.RunPython(remove_entries, migrations.RunPython.noop)]
