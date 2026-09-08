from common.auth.rbac import verify_permission
from apps.jobs.models import WorkflowRun


def can_view_run(user, run):
    if (
        not user
        or not user.is_authenticated
        or not user.is_active
        or not user.job_status
    ):
        return False
    if not user.is_superuser and run.triggered_by_id != user.id:
        return False
    domain = "ops" if run.run_domain == WorkflowRun.RunDomain.OPS else "tasks"
    return verify_permission(user, f"/api/v1/{domain}/runs/{run.id}/events", "GET")[0]
