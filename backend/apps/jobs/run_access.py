"""Single entry point for run data-scope decisions.

REST querysets and the realtime layer share these helpers so list, detail,
log, events, cancel and retry enforce the same visibility rule. The current
policy restricts every non-superuser to the runs they triggered; widening
this to team or department scopes only requires changing this module.
"""

NONE = "none"
OWNER = "owner"
ALL = "all"


def run_access_state(user) -> str:
    """Classify a user's run data scope: NONE, OWNER or ALL."""
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
        or not getattr(user, "job_status", False)
    ):
        return NONE
    if getattr(user, "is_superuser", False):
        return ALL
    return OWNER


def visible_runs(queryset, user):
    """Filter a WorkflowRun queryset down to the runs the user may see."""
    state = run_access_state(user)
    if state == NONE:
        return queryset.none()
    if state == OWNER:
        return queryset.filter(triggered_by=user)
    return queryset


def in_scope(user, run) -> bool:
    """Object-level check mirroring visible_runs."""
    state = run_access_state(user)
    if state == NONE:
        return False
    if state == OWNER:
        return run.triggered_by_id == user.id
    return True
