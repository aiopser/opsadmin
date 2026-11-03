from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.provisioning.retention import retention_candidates, purge_artifact
from apps.provisioning.models import ProvisioningArtifact
from apps.provisioning.terraform import ArtifactStore


class Command(BaseCommand):
    help = "列出符合保留规则的制品；仅 --execute 时删除登记文件，不删除 state。"

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true")

    def handle(self, *args, **options):
        candidates = list(
            retention_candidates(timezone.now()).values_list("pk", flat=True)
        )
        deleted = (
            sum(purge_artifact(pk, None) for pk in candidates)
            if options["execute"]
            else 0
        )
        self.stdout.write(
            f"候选 {len(candidates)} 个；已删除 {deleted} 个；{'执行模式' if options['execute'] else 'dry-run，未删除文件'}"
        )
        for storage in ["main", "backup"]:
            try:
                root = ArtifactStore(backup=storage == "backup").root
                known = set(
                    ProvisioningArtifact.objects.filter(storage=storage).values_list(
                        "key", flat=True
                    )
                )
                count, size = 0, 0
                for index, path in enumerate(root.iterdir()):
                    if index >= 10000:
                        self.stdout.write(f"{storage} 文件超过扫描上限，需分批人工核实")
                        break
                    if (
                        path.is_file()
                        and not path.is_symlink()
                        and path.name not in known
                    ):
                        count += 1
                        size += path.stat().st_size
                self.stdout.write(f"{storage} 未登记文件 {count} 个，{size} 字节；仅报告，不删除")
            except Exception:
                self.stdout.write(f"{storage} 存储无法核对，请检查私有目录配置")
