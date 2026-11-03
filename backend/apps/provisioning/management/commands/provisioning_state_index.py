from django.core.management.base import BaseCommand
from apps.provisioning.models import ProvisioningAttempt
from apps.provisioning.state_protection import (
    capture_state,
    parse_state,
    read_state_files,
)
from apps.provisioning.terraform import ArtifactStore


class Command(BaseCommand):
    help = "核对旧恢复制品；默认 dry-run，--execute 仅登记可验证 state，不创建云资源。"

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--repair", action="store_true", help="同时重新备份保护失败的已知 state")

    def handle(self, *args, **options):
        valid, failed = 0, 0
        for attempt in ProvisioningAttempt.objects.exclude(
            recovery_artifact_key=""
        ).iterator():
            try:
                if attempt.status in {"queued", "running"}:
                    continue
                latest = attempt.provisioningstateversion_set.order_by(
                    "-version"
                ).first()
                if latest:
                    if not options["repair"]:
                        continue
                    try:
                        files = read_state_files(latest)
                    except Exception:
                        files = read_state_files(latest, backup=True)
                    if latest.protection_status == "protected":
                        try:
                            read_state_files(latest)
                            read_state_files(latest, backup=True)
                            continue
                        except Exception:
                            pass
                else:
                    files = ArtifactStore().get(attempt.recovery_artifact_key)["files"]
                parse_state(files)
                if options["execute"]:
                    capture_state(attempt.pk, files)
                valid += 1
            except Exception:
                failed += 1
                self.stdout.write(f"执行 #{attempt.pk} 无法校验，请检查旧制品或密钥")
        self.stdout.write(
            f"可校验 {valid}，异常 {failed}；{'已登记' if options['execute'] else 'dry-run，未登记或修改文件'}"
        )
