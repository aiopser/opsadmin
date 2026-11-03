import importlib
from types import SimpleNamespace
import pytest
from django.apps import apps
from django.db import connection
from apps.permission.models import Menu, MenuButton, Permission

pytestmark = pytest.mark.django_db


def test_retired_feature_cleanup_preserves_other_menus_and_permissions():
    retire = importlib.import_module(
        "apps.permission.migrations.0008_remove_retired_feature_entries"
    )
    normal = Menu.objects.create(name="system", path="/system", title="System", order=1)
    game = Menu.objects.create(name="game-ops", path="/game-ops", title="Game", order=8)
    config = Menu.objects.create(
        name="config-center", path="/config-center", title="Config", order=9
    )
    Menu.objects.create(
        name="game-ops_projects",
        path="projects",
        pid=game,
        component="view.game-ops_projects",
        order=1,
    )
    old = Permission.objects.create(
        code="game_ops.task.create", name="Retired", type="api", is_system=True
    )
    Permission.objects.create(
        code="config_center.release.create",
        name="Retired config",
        type="api",
        is_system=True,
    )
    keep = Permission.objects.create(
        code="jobs.workflow_run.create", name="Create task", type="api", is_system=True
    )
    MenuButton.objects.create(menu=game, code="game_ops.task:create", desc="Create")
    normal.permission.add(keep)
    retire.remove_entries(apps, SimpleNamespace(connection=connection))
    retire.remove_entries(apps, SimpleNamespace(connection=connection))
    assert not Menu.objects.filter(pk__in=[game.pk, config.pk]).exists()
    assert not Permission.objects.filter(pk=old.pk).exists()
    assert Menu.objects.filter(pk=normal.pk).exists()
    assert normal.permission.filter(pk=keep.pk).exists()


def test_retired_heartbeat_is_disabled_without_changing_job_schedules():
    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    retire = importlib.import_module(
        "apps.permission.migrations.0008_remove_retired_feature_entries"
    )
    interval = IntervalSchedule.objects.create(every=15, period="seconds")
    old = PeriodicTask.objects.create(
        name="retired-feature-heartbeat",
        task="game_ops.recover_maintenance",
        interval=interval,
        enabled=True,
    )
    normal = PeriodicTask.objects.create(
        name="normal-job-heartbeat",
        task="jobs.recover_stale_workflow_runs",
        interval=interval,
        enabled=True,
    )
    retire.remove_entries(apps, SimpleNamespace(connection=connection))
    old.refresh_from_db()
    normal.refresh_from_db()
    assert not old.enabled
    assert normal.enabled
