"""Actor authorization shared by definitions, run creation and worker execution."""

from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied

from apps.automation.models import CommandAtom, CommandVersion
from apps.jobs.quick_commands import QUICK_WORKFLOW_CODES


HIGH_RISK_PERMISSION = "automation.command:execute_high_risk"


def _matches_quick_source(source, inputs):
    kind = inputs.get("execution_source")
    if kind == "playbook":
        return source.command_type == "playbook" and source.content == inputs.get(
            "playbook_content"
        )
    if kind == "module":
        return (
            source.command_type == "ansible_module"
            and source.content.strip() == inputs.get("module")
        )
    return source.content == inputs.get("command_content")


def authorize_execution(*, actor, graph_snapshot, input_vars=None):
    """Require the responsible actor's current permission, including quick sources.

    Wrapper commands are intentionally low risk themselves. Their executable source
    (or arbitrary inline body) determines the permission, even when invoked through
    a schedule, cloned snapshot or another application caller.
    """
    if actor is not None and getattr(actor, "pk", None):
        actor = get_user_model().objects.filter(pk=actor.pk).first()
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not actor.is_active
        or not getattr(actor, "job_status", False)
    ):
        raise PermissionDenied("Active actor required")
    inputs = input_vars or {}
    nodes = (graph_snapshot or {}).get("nodes") or []
    version_ids = {
        value
        for node in nodes
        for value in (
            node.get("commandVersionId"),
            (node.get("commandVersion") or {}).get("id"),
            (node.get("commandVersion") or {}).get("sourceVersionId"),
        )
        if value is not None
    }
    source_id = inputs.get("source_command_version_id") or inputs.get(
        "source_module_version_id"
    )
    if source_id is not None:
        version_ids.add(source_id)
    versions = list(
        CommandVersion.objects.select_related("command").filter(pk__in=version_ids)
    )
    high_risk = any(
        version.command.risk_level == CommandAtom.RiskLevel.HIGH for version in versions
    )
    # Deleted source metadata must never turn a frozen command into low risk.
    high_risk = high_risk or bool(version_ids - {version.pk for version in versions})
    high_risk = high_risk or any(
        (node.get("commandVersion") or {}).get("risk_level")
        == CommandAtom.RiskLevel.HIGH
        for node in nodes
    )
    has_wrapper = any(
        version.command.code.removesuffix("_command") in QUICK_WORKFLOW_CODES
        for version in versions
    )
    if has_wrapper:
        source = next(
            (version for version in versions if version.pk == source_id), None
        )
        if source is None or not _matches_quick_source(source, inputs):
            high_risk = True
    if high_risk and not (
        actor.is_superuser
        or actor.role.filter(
            is_active=True,
            permission__code=HIGH_RISK_PERMISSION,
            permission__is_active=True,
        ).exists()
    ):
        raise PermissionDenied("当前用户缺少高危命令执行权限")
    return actor
