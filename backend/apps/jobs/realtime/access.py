from common.auth.rbac import verify_permission
from apps.jobs.models import WorkflowRun

from ..run_access import in_scope


def can_view_run(user, run):
    if not in_scope(user, run):
        return False
    domain = "ops" if run.run_domain == WorkflowRun.RunDomain.OPS else "tasks"
    return verify_permission(user, f"/api/v1/{domain}/runs/{run.id}/events", "GET")[0]
