from apps.jobs.models import WorkflowRun

from .models import DomainAuditEvent


def _get_client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def create_domain_audit_event(
    actor,
    action,
    resource_type,
    resource_id,
    before=None,
    after=None,
    request=None,
    domain=None,
):
    user = actor if getattr(actor, "is_authenticated", False) else None
    resolved_domain = domain or _resolve_domain(action, resource_type, resource_id)
    return DomainAuditEvent.objects.create(
        domain=resolved_domain,
        actor=user,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        before=before or {},
        after=after or {},
        request_id=getattr(request, "id", "")
        or request.META.get("HTTP_X_REQUEST_ID", "")
        if request
        else "",
        ip_address=_get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255] if request else "",
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
        run_domain = (
            WorkflowRun.objects.filter(id=resource_id)
            .values_list("run_domain", flat=True)
            .first()
        )
        if run_domain in {WorkflowRun.RunDomain.OPS, WorkflowRun.RunDomain.TASK}:
            return run_domain
    if action.startswith(("security.", "command_intercept.")):
        return DomainAuditEvent.Domain.SECURITY
    return DomainAuditEvent.Domain.SYSTEM
