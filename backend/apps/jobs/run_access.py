"""Single entry point for run data-scope decisions.

REST querysets and the realtime layer share these helpers so list, detail,
log, events, cancel and retry enforce the same visibility rule. Superusers
see everything; other users start from the runs they triggered and widen to
their (direct) department when any active role grants the ``department``
scope. Widening further only requires changing this module.
"""

from django.db.models import Q

NONE = "none"
OWNER = "owner"
DEPARTMENT = "department"
ALL = "all"


def run_access_state(user) -> str:
    """Classify a user's run data scope: NONE, OWNER, DEPARTMENT or ALL."""
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
        or not getattr(user, "job_status", False)
    ):
        return NONE
    if getattr(user, "is_superuser", False):
        return ALL
    role_manager = getattr(user, "role", None)
    scopes = (
        set(
            role_manager.filter(is_active=True).values_list(
                "job_data_scope", flat=True
            )
        )
        if role_manager is not None
        else set()
    )
    if ALL in scopes:
        return ALL
    if DEPARTMENT in scopes and getattr(user, "department_id", None):
        return DEPARTMENT
    return OWNER


def visible_runs(queryset, user, owner="triggered_by"):
    """Filter an owner-bearing queryset down to the rows the user may see.

    ``owner`` names the FK that identifies the run's responsible user, e.g.
    ``triggered_by`` on WorkflowRun or ``created_by`` on ScheduledJob.
    """
    state = run_access_state(user)
    if state == NONE:
        return queryset.none()
    if state == OWNER:
        return queryset.filter(**{owner: user})
    if state == DEPARTMENT:
        return queryset.filter(
            Q(**{owner: user})
            | Q(**{f"{owner}__department_id": user.department_id})
        )
    return queryset


def in_scope(user, run) -> bool:
    """Object-level check mirroring visible_runs for WorkflowRun instances."""
    state = run_access_state(user)
    if state == NONE:
        return False

    if state == ALL or run.triggered_by_id == user.id:
        return True
    if state == DEPARTMENT and getattr(user, "department_id", None):
        owner = run.triggered_by
        return owner is not None and owner.department_id == user.department_id
    return False
