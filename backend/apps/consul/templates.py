"""consul-template 托管模板：路径校验、下发脚本构造与执行提交。

下发复用作业系统执行链路。配置可能包含执行动作，按高危权限校验。
"""

import base64
import re
from posixpath import dirname

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.automation.models import CommandAtom, CommandVersion
from apps.jobs.application.dispatch import enqueue_workflow_run
from apps.jobs.application.runs import create_quick_command_run

PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_./-]{1,500}$")

# reload 命令：仅允许空白分隔的安全 token（禁止引号、$、; | & > < 等元字符），
# 首个 token（二进制）必须在白名单内。
RELOAD_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_@%+=:,./-]{1,256}$")
RELOAD_BIN_ALLOWLIST = frozenset(
    {
        "systemctl",
        "service",
        "killall",
        "pkill",
        "consul-template",
        "/bin/systemctl",
        "/usr/bin/systemctl",
        "/sbin/service",
        "/usr/sbin/service",
        "/usr/bin/pkill",
        "/usr/bin/killall",
        "/usr/bin/consul-template",
        "/usr/local/bin/consul-template",
    }
)

DEPLOY_COMMAND_CODE = "consul_template_deploy_command"


def validate_template_path(value):
    path = value.strip()
    if not PATH_PATTERN.fullmatch(path):
        raise ValidationError("路径必须是以 / 开头的绝对路径，仅支持字母、数字与 _ - . / 字符")
    if ".." in path or path.endswith("/"):
        raise ValidationError("路径不允许包含 .. 或以 / 结尾")
    return path


def validate_reload_command(value):
    command = " ".join(value.split())
    if not command:
        return ""
    tokens = command.split(" ")
    if any(not RELOAD_TOKEN_PATTERN.fullmatch(token) for token in tokens):
        raise ValidationError("reload 命令包含不允许的字符（禁止引号、$、; | & > < 等）")
    binary = tokens[0].rsplit("/", 1)[-1]
    allowed = (
        (
            binary == "systemctl"
            and len(tokens) == 3
            and tokens[1] in {"reload", "restart"}
            and tokens[2] in {"consul-template", "consul-template.service"}
        )
        or (
            binary == "service"
            and tokens[1:]
            in (["consul-template", "reload"], ["consul-template", "restart"])
        )
        or (binary == "pkill" and tokens[1:] == ["-HUP", "-x", "consul-template"])
        or (binary == "killall" and tokens[1:] == ["-HUP", "consul-template"])
    )
    if tokens[0] not in RELOAD_BIN_ALLOWLIST or not allowed:
        raise ValidationError("仅允许重载或重启 consul-template 服务，或向 consul-template 发送 HUP")
    return command


def build_deploy_script(content, path, reload_command, expected_checksum=None):
    validate_template_path(path)
    reload_command = validate_reload_command(reload_command)
    if (
        expected_checksum is not None
        and expected_checksum != "missing"
        and not re.fullmatch(r"[a-f0-9]{64}", expected_checksum)
    ):
        raise ValidationError("远端校验值无效")
    encoded = base64.b64encode(content.encode()).decode()
    lines = [
        "set -eu",
        "umask 077",
        f"target='{path}'",
        f"mkdir -p '{dirname(path)}'",
        '[ ! -L "$target" ] || { echo "拒绝覆盖符号链接" >&2; exit 1; }',
        'lock="$target.devops-lock"',
        'mkdir "$lock" 2>/dev/null || { echo "同一文件已有下发任务或遗留锁，请检查" >&2; exit 1; }',
        "tmp=''; backup=''; replaced=0; had_original=0",
        f"reload_service() {{ {reload_command or ':'}; }}",
        'restore() { if [ "$had_original" = 1 ]; then cp -p "$backup" "$target"; else rm -f "$target"; fi; }',
        'cleanup() { code=$?; trap - EXIT; keep_backup=0; if [ "$code" != 0 ] && [ "$replaced" = 1 ]; then if ! restore; then keep_backup=1; echo "恢复失败，已保留备份，请人工检查" >&2; elif ! reload_service; then keep_backup=1; echo "文件已恢复，但服务恢复失败，请人工检查" >&2; else echo "原文件与服务已恢复" >&2; fi; fi; [ -z "$tmp" ] || rm -f "$tmp"; if [ "$keep_backup" = 0 ] && [ -n "$backup" ]; then rm -f "$backup"; fi; rmdir "$lock" 2>/dev/null || true; exit "$code"; }',
        "trap cleanup EXIT",
        "trap 'exit 1' HUP INT TERM",
        'current_checksum() { if [ -L "$target" ]; then return 1; elif [ -e "$target" ]; then [ -f "$target" ] || return 1; sha256sum "$target" | cut -d " " -f 1; else printf missing; fi; }',
        f"expected='{expected_checksum or ''}'",
        'verify_checksum() { [ -z "$expected" ] || [ "$(current_checksum)" = "$expected" ] || { echo "远端文件已变化，请重新读取并确认差异" >&2; return 1; }; }',
        "verify_checksum",
        'tmp=$(mktemp "$target.tmp.XXXXXX")',
        "printf '%s' '" + encoded + '\' | base64 -d > "$tmp"',
        'if [ -e "$target" ]; then had_original=1; backup=$(mktemp "$target.backup.XXXXXX"); cp -p "$target" "$backup"; chmod --reference="$target" "$tmp"; chown --reference="$target" "$tmp"; fi',
        "verify_checksum",
        "replaced=1",
        'mv -f "$tmp" "$target"',
    ]
    if reload_command:
        lines.append(reload_command)
    return "\n".join(lines)


def ensure_deploy_source_version(script):
    """绑定不可变脚本版本，并保留运行引用的风险元数据。"""
    atom, _ = CommandAtom.objects.update_or_create(
        code=DEPLOY_COMMAND_CODE,
        defaults={
            "name": "Consul 模板下发",
            "category": "system",
            "description": "Protected command used by consul template deploy runs.",
            "status": CommandAtom.Status.PUBLISHED,
            "risk_level": CommandAtom.RiskLevel.HIGH,
        },
    )
    version = CommandVersion.objects.filter(
        command=atom, status=CommandVersion.Status.PUBLISHED, content=script
    ).first()
    if version is not None:
        return version
    next_version = (
        CommandVersion.objects.filter(command=atom)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    version = CommandVersion.objects.create(
        command=atom,
        version=next_version,
        status=CommandVersion.Status.PUBLISHED,
        command_type=CommandVersion.CommandType.LINUX_SHELL,
        content=script,
    )
    return version


@transaction.atomic
def submit_template_deploy(row, actor, read_id):
    from .models import ConsulTemplateFile
    from .remote_files import deploy_baseline

    row = ConsulTemplateFile.objects.select_for_update().get(pk=row.pk)
    if row.last_deploy_run_id and row.last_deploy_run.status in {
        "pending",
        "queued",
        "running",
        "waiting",
        "cancel_requested",
    }:
        raise ValidationError("已有下发任务进行中，请等待结束")
    checksum = deploy_baseline(row, actor, read_id)
    host = row.host
    if host.os_family != "linux":
        raise ValidationError("模板下发仅支持 Linux 主机")
    if host.status != "active":
        raise ValidationError("目标主机已停用，无法下发")
    script = build_deploy_script(
        row.content, row.path, row.reload_command, expected_checksum=checksum
    )
    run = create_quick_command_run(
        command_type=CommandVersion.CommandType.LINUX_SHELL,
        command_content=script,
        host_ids=[row.host_id],
        worker_pool=None,
        triggered_by=actor,
        resource_version=ensure_deploy_source_version(script),
        name=f"模板下发-{row.name}",
    )
    row.last_deploy_run = run
    row.save(update_fields=["last_deploy_run"])
    transaction.on_commit(lambda: enqueue_workflow_run(run.id))
    return run
