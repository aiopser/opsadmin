from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.jobs.models import ExecutionRequestKey


class Command(BaseCommand):
    help = (
        "Compact old replay responses, retaining keys to prevent duplicate execution."
    )

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        if options["days"] < 1:
            raise CommandError("days must be at least 1")
        records = ExecutionRequestKey.objects.filter(
            created_at__lt=timezone.now() - timedelta(days=options["days"]),
            status_code__gte=200,
            status_code__lt=300,
        )
        if options["execute"]:
            count = records.update(response_encrypted="", status_code=410)
            self.stdout.write(
                f"Compacted responses: {count}; idempotency keys retained"
            )
        else:
            self.stdout.write(
                f"Dry run: {records.count()} responses eligible; no changes"
            )
