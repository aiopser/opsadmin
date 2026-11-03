"""One-off reconcile between ScheduledJob rows and django-celery-beat.

Run once after deploying the django-celery-beat migration:
  1. every ScheduledJob gets its mirrored PeriodicTask (enabled state kept);
  2. PeriodicTasks named ``jobs.scheduled_job:<pk>`` without a matching
     ScheduledJob are removed;
  3. the legacy static beat entry ``jobs.dispatch-scheduled-jobs`` is removed
     from the database so the retired scanner task stops firing.
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask

from apps.jobs.models import ScheduledJob
from apps.jobs.schedule_sync import (
    PERIODIC_TASK_NAME_PREFIX,
    periodic_task_name,
    upsert_periodic_task,
)

# Static CELERY_BEAT_SCHEDULE entries that existed before the
# django-celery-beat migration.  They are synced into the database by beat's
# update_from_dict and would keep triggering the removed scanner task.
LEGACY_STATIC_ENTRIES = ["jobs.dispatch-scheduled-jobs"]


class Command(BaseCommand):
    help = "Sync ScheduledJob rows into django-celery-beat PeriodicTasks and clean stale entries."

    def handle(self, *args, **options):
        synced = 0
        for schedule in ScheduledJob.objects.iterator():
            upsert_periodic_task(schedule)
            synced += 1

        existing_ids = {
            str(pk) for pk in ScheduledJob.objects.values_list("pk", flat=True)
        }
        orphan_ids = [
            name[len(PERIODIC_TASK_NAME_PREFIX) :]
            for name in PeriodicTask.objects.filter(
                name__startswith=PERIODIC_TASK_NAME_PREFIX
            ).values_list("name", flat=True)
            if name[len(PERIODIC_TASK_NAME_PREFIX) :] not in existing_ids
        ]
        removed_orphans = PeriodicTask.objects.filter(
            name__in=[
                periodic_task_name(pk_text) for pk_text in orphan_ids
            ]
        ).delete()[0]

        removed_legacy = PeriodicTask.objects.filter(
            name__in=LEGACY_STATIC_ENTRIES
        ).delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {synced} scheduled jobs, "
                f"removed {removed_orphans} orphan PeriodicTasks, "
                f"removed {removed_legacy} legacy static entries."
            )
        )
