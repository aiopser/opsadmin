import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from apps.provisioning.templates import template_configuration
from apps.provisioning.contracts import canonical_digest, ProvisioningError


class Command(BaseCommand):
    help = "生成供管理员审核的资源模板配置，或计算已锁定模板包摘要；不执行云资源创建。"

    def add_arguments(self, parser):
        parser.add_argument("--provider", choices=["aliyun", "tencent"], required=True)
        parser.add_argument("--directory", required=True)
        parser.add_argument("--provider-version")
        parser.add_argument("--terraform-version")
        parser.add_argument("--digest", action="store_true")

    def handle(self, *args, **options):
        directory = Path(options["directory"]).resolve() / options["provider"]
        if options["digest"]:
            names = ["main.tf.json", ".terraform.lock.hcl"]
            if any(not (directory / name).is_file() for name in names):
                raise CommandError("请先审核配置并使用固定版本 Terraform 生成 .terraform.lock.hcl")
            self.stdout.write(
                canonical_digest(
                    {
                        name: (directory / name).read_text(encoding="utf-8")
                        for name in names
                    }
                )
            )
            return
        try:
            content = template_configuration(
                options["provider"],
                options["provider_version"] or "",
                options["terraform_version"] or "",
            )
        except ProvisioningError as exc:
            raise CommandError(str(exc)) from exc
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "main.tf.json"
        if path.exists():
            raise CommandError("配置文件已存在，不覆盖已审核的模板")
        path.write_text(
            json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.stdout.write(f"已生成 {path}；请审核并生成 Provider 锁文件，再计算包摘要。")
