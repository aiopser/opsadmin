"""Bounded, explicit history retention; identities and delivery records are retained."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.integrations.models import JumpServerSync
from apps.monitoring.models import EnrollmentRun, SyncRecord
from apps.security.models import SecurityCollection


class Command(BaseCommand):
    help = "预览或清理已结束的监控集成历史；默认保留90天，不清理资产、映射、公告观察和通知记录"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--limit", type=int, default=1000)
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        if options["days"] < 1 or not 1 <= options["limit"] <= 10000:
            raise CommandError("days 至少为1，limit 必须为1至10000")
        cutoff = timezone.now() - timedelta(days=options["days"])
        models = (
            (SyncRecord, ["succeeded", "failed"]),
            (EnrollmentRun, ["succeeded", "failed"]),
            (SecurityCollection, ["success", "failed"]),
            (JumpServerSync, ["succeeded", "failed", "preview"]),
        )
        for model, statuses in models:
            query = model.objects.filter(status__in=statuses, updated_at__lt=cutoff)
            with transaction.atomic():
                batch = query.order_by("pk")
                if options["execute"]:
                    batch = batch.select_for_update()
                ids = list(batch.values_list("pk", flat=True)[: options["limit"]])
                if options["execute"]:
                    query.filter(pk__in=ids).delete()
            mode = "已清理" if options["execute"] else "预览（未修改）"
            self.stdout.write(
                f"{mode} {model._meta.label}: {len(ids)}，每类上限 {options['limit']}"
            )
