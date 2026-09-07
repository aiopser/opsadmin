from django.core.management.base import BaseCommand

from apps.cmdb.models import WorkerPool


class Command(BaseCommand):
    help = "Initialize the default central Ansible worker pool."

    def handle(self, *args, **options):
        default_pool, _ = WorkerPool.objects.update_or_create(
            code="default",
            defaults={
                "name": "Default Worker Pool",
                "queue_name": "ansible",
                "is_default": True,
                "is_active": True,
                "concurrency_limit": 5,
            },
        )
        WorkerPool.objects.exclude(pk=default_pool.pk).update(is_default=False)
        self.stdout.write(self.style.SUCCESS("CMDB defaults initialized."))
