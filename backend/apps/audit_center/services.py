from .models import DomainAuditEvent
from ipaddress import ip_address
from common.redaction import redact_text, redact_value


def _get_client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded_for.split(",")[0].strip() if forwarded_for else request.META.get("REMOTE_ADDR")
    try:
        return str(ip_address(candidate)) if candidate else None
    except ValueError:
        return None


def create_domain_audit_event(
    actor,
    action,
    resource_type,
    resource_id,
    before=None,
    after=None,
    request=None,
    domain=None,
    run_id=None,
    result="success",
):
    user = actor if getattr(actor, "is_authenticated", False) else None
    resolved_domain = domain or _resolve_domain(action, resource_type, resource_id)
    return DomainAuditEvent.objects.create(
        domain=resolved_domain,
        actor=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        before=redact_value(before or {}),
        after=redact_value(after or {}),
        run_id=str(run_id or (resource_id if resource_type == "workflow_run" else "") or ""),
        result=result,
        request_id=getattr(request, "id", "")
        or request.META.get("HTTP_X_REQUEST_ID", "")
        if request
        else "",
        ip_address=_get_client_ip(request),
        user_agent=redact_text(request.META.get("HTTP_USER_AGENT", ""))[:255] if request else "",
    )


def _resolve_workflow_run_domain(resource_id):
    """jobs app 未安装时优雅降级（避免 audit_center 反向依赖业务 app）。"""
    try:
        from apps.jobs.models import WorkflowRun
    except Exception:
        return None

    return (
        WorkflowRun.objects.filter(id=resource_id)
        .values_list("run_domain", flat=True)
        .first()
    )


def _resolve_domain(action, resource_type, resource_id):
    action = str(action or "")
    if action.startswith("cmdb."):
        return DomainAuditEvent.Domain.CMDB
    if action.startswith("automation."):
        return DomainAuditEvent.Domain.AUTOMATION
    if action.startswith(("quick_command_run.", "playbook_run.", "module_run.")):
        return DomainAuditEvent.Domain.OPS
    if resource_type == "workflow_run" and resource_id:
        run_domain = _resolve_workflow_run_domain(resource_id)
        if run_domain:
            # 能解析出 run_domain 说明 jobs app 已安装
            from apps.jobs.models import WorkflowRun

            if run_domain in {WorkflowRun.RunDomain.OPS, WorkflowRun.RunDomain.TASK}:
                return run_domain
    if action.startswith(("security.", "command_intercept.")):
        return DomainAuditEvent.Domain.SECURITY
    return DomainAuditEvent.Domain.SYSTEM
