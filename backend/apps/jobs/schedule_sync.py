"""Keep one django-celery-beat PeriodicTask in sync per ScheduledJob.

Scheduling of user-defined jobs is owned by the DatabaseScheduler: every
``ScheduledJob`` row is mirrored by a ``PeriodicTask`` named
``jobs.scheduled_job:<pk>`` that fires ``jobs.execute_scheduled_job`` with the
row's primary key.  Policy decisions (misfire/overlap/auto-disable) stay in
the task function; this module only maintains the trigger definition.

Callers must invoke these helpers inside the same transaction that writes the
``ScheduledJob`` so both sides commit atomically.
"""

import json
from datetime import datetime, timezone as dt_timezone
from uuid import uuid4

from django.conf import settings
from django.db import transaction

from django_celery_beat.models import ClockedSchedule, CrontabSchedule, PeriodicTask

from .cron import CronExpressionError, celery_datetime, parse_cron

PERIODIC_TASK_NAME_PREFIX = "jobs.scheduled_job:"
EXECUTE_TASK_NAME = "jobs.execute_scheduled_job"


def _beat_cursor() -> datetime:
    """Naive-UTC "now" matching beat's own naive-UTC cursor columns.

    Beat reads ``last_run_at`` through ``maybe_make_aware`` when
    ``DJANGO_CELERY_BEAT_TZ_AWARE`` is off, which interprets naive values as
    UTC; anchoring the cursor here avoids its ``date_changed`` fallback, whose
    local wall-clock value would be misread as UTC.
    """
    cursor = datetime.now(dt_timezone.utc)
    return cursor if settings.USE_TZ else cursor.replace(tzinfo=None)


def periodic_task_name(scheduled_job_id) -> str:
    return f"{PERIODIC_TASK_NAME_PREFIX}{scheduled_job_id}"


def _crontab_fields(cron_expression: str) -> dict:
    fields = str(cron_expression or "").split()
    if len(fields) != 5:
        raise CronExpressionError("Cron 表达式必须包含 5 个字段：分 时 日 月 周")
    minute, hour, day_of_month, month_of_year, day_of_week = fields
    return {
        "minute": minute,
        "hour": hour,
        "day_of_month": day_of_month,
        "month_of_year": month_of_year,
        "day_of_week": "*"
        if day_of_week == "*"
        else ",".join(
            str(value) for value in sorted(parse_cron(cron_expression)["weekday"])
        ),
    }


@transaction.atomic
def upsert_periodic_task(schedule) -> None:
    """Create or refresh the PeriodicTask mirror for ``schedule``.

    Must run inside the caller's transaction.  Periodic jobs reuse a
    CrontabSchedule row via get_or_create so tweaking an expression does not
    pile up orphan schedules; one-off jobs use a ClockedSchedule plus
    ``one_off=True``, which makes beat disable the trigger after it fires once.
    """
    from .models import ScheduledJob

    is_once = schedule.schedule_type == ScheduledJob.ScheduleType.ONCE
    crontab = None
    clocked = None
    if is_once:
        if schedule.run_at is None:
            # A one-off job without an execution moment has nothing to trigger.
            remove_periodic_task(schedule.pk)
            return
        clocked, _ = ClockedSchedule.objects.get_or_create(
            clocked_time=celery_datetime(schedule.run_at)
        )
    else:
        crontab, _ = CrontabSchedule.objects.get_or_create(
            **_crontab_fields(schedule.cron_expression),
            timezone=schedule.timezone,
        )
    cursor = _beat_cursor()
    defaults = {
        "task": EXECUTE_TASK_NAME,
        "args": "[]",
        "crontab": crontab,
        "clocked": clocked,
        "interval": None,
        "solar": None,
        "one_off": is_once,
        "enabled": schedule.enabled,
        "description": schedule.name,
        "start_time": None,
        "expires": celery_datetime(schedule.expires_at),
        "expire_seconds": None,
    }
    task, created = PeriodicTask.objects.select_for_update().get_or_create(
        name=periodic_task_name(schedule.pk),
        defaults={
            **defaults,
            "kwargs": json.dumps(
                {"scheduled_job_id": schedule.pk, "schedule_token": uuid4().hex}
            ),
            "last_run_at": cursor,
        },
    )
    if created:
        return
    payload = json.loads(task.kwargs or "{}")
    definition_changed = (
        task.task != EXECUTE_TASK_NAME
        or task.crontab_id != (crontab.pk if crontab else None)
        or task.clocked_id != (clocked.pk if clocked else None)
        or task.one_off != is_once
        or task.enabled != schedule.enabled
    )
    reset_token = definition_changed or not payload.get("schedule_token")
    reset_cursor = definition_changed or (task.last_run_at is None and schedule.enabled)
    changed = any(getattr(task, key) != value for key, value in defaults.items())
    if reset_token:
        task.kwargs = json.dumps(
            {"scheduled_job_id": schedule.pk, "schedule_token": uuid4().hex}
        )
    if reset_cursor:
        task.last_run_at = cursor
    # Beat disables a one-off trigger once ``total_run_count > 0``.  Re-arming a
    # rescheduled one-off therefore requires clearing that counter, otherwise it
    # would be suppressed on the next tick.
    reset_count = definition_changed and is_once and task.total_run_count
    if reset_count:
        task.total_run_count = 0
    if changed or reset_token or reset_cursor or reset_count:
        previous_clocked_id = task.clocked_id
        for key, value in defaults.items():
            setattr(task, key, value)
        task.save()
        if previous_clocked_id and previous_clocked_id != (clocked.pk if clocked else None):
            ClockedSchedule.objects.filter(
                pk=previous_clocked_id, periodictask__isnull=True
            ).delete()


def remove_periodic_task(scheduled_job_id) -> None:
    task = PeriodicTask.objects.filter(name=periodic_task_name(scheduled_job_id)).first()
    if task is None:
        return
    clocked_id = task.clocked_id
    task.delete()
    if clocked_id is not None:
        ClockedSchedule.objects.filter(pk=clocked_id, periodictask__isnull=True).delete()
