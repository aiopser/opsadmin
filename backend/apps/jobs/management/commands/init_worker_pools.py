from django.core.management.base import BaseCommand
from apps.jobs.models import WorkerPool


class Command(BaseCommand):
    help = "Initialize the new jobs worker pool without resetting existing configuration."

    def handle(self, *args, **options):
        WorkerPool.objects.get_or_create(code="default", defaults={"name": "Default Worker Pool", "queue_name": "devops.ansible", "is_default": True})
        self.stdout.write(self.style.SUCCESS("Worker pool initialized."))
