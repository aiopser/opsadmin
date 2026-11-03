"""DatabaseScheduler with per-job timezones and immutable occurrence payloads."""

from zoneinfo import ZoneInfo

from celery.beat import ScheduleEntry
from celery.utils.time import maybe_make_aware
from django_celery_beat.schedulers import DatabaseScheduler, ModelEntry
from django_celery_beat.tzcrontab import TzAwareCrontab

from .cron import celery_instant, next_cron_time, utc_instant
from .schedule_sync import EXECUTE_TASK_NAME


class ScheduledJobEntry(ModelEntry):
    def __init__(self, model, app=None):
        super().__init__(model, app=app)
        self.scheduled_for = None
        if self.task != EXECUTE_TASK_NAME:
            return
        if model.clocked_id:
            # One-off jobs: the clocked moment itself is the occurrence, stored
            # in beat's naive-UTC convention.
            self.scheduled_for = celery_instant(model.clocked.clocked_time)
            return
        if not model.crontab_id:
            return
        cron = model.crontab
        self.schedule = TzAwareCrontab(
            minute=cron.minute,
            hour=cron.hour,
            day_of_week=cron.day_of_week,
            day_of_month=cron.day_of_month,
            month_of_year=cron.month_of_year,
            tz=ZoneInfo(str(cron.timezone)),
            app=self.app,
        )
        expression = f"{cron.minute} {cron.hour} {cron.day_of_month} {cron.month_of_year} {cron.day_of_week}"
        # Beat's naive cursor is UTC, unlike application database timestamps.
        self.scheduled_for = utc_instant(
            next_cron_time(
                expression,
                str(cron.timezone),
                maybe_make_aware(self.last_run_at),
            )
        )


class ScheduledJobScheduler(DatabaseScheduler):
    Entry = ScheduledJobEntry

    def apply_async(self, entry, producer=None, advance=True, **kwargs):
        if entry.task != EXECUTE_TASK_NAME:
            return super().apply_async(
                entry, producer=producer, advance=advance, **kwargs
            )
        if advance:
            self.reserve(entry)
        # ``scheduled_for`` pins the occurrence so a retried message cannot be
        # mistaken for a fresh slot; a clocked entry without one falls back to
        # the plain payload rather than failing the dispatch.
        delivery_kwargs = {**entry.kwargs}
        if entry.scheduled_for is not None:
            delivery_kwargs["scheduled_for"] = entry.scheduled_for.isoformat()
        delivery = ScheduleEntry(
            name=entry.name,
            task=entry.task,
            args=entry.args,
            kwargs=delivery_kwargs,
            options=entry.options,
            app=entry.app,
            schedule=entry.schedule,
            last_run_at=entry.last_run_at,
        )
        return super().apply_async(delivery, producer=producer, advance=False, **kwargs)
