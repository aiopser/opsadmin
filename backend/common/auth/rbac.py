from rest_framework.permissions import BasePermission

from apps.permission.audit import create_access_log
from apps.permission.services import CasbinEnforcerService


def verify_permission(user, path, method):
    if not getattr(user, "is_active", True) or not getattr(user, "job_status", True):
        return False, "account_disabled"
    if getattr(user, "is_superuser", False):
        return True, ""
    username = getattr(user, "username", None)
    if not username:
        return False, "missing_authenticated_user"
    allowed = CasbinEnforcerService.get_enforcer().enforce(username, path, method)
    return allowed, "" if allowed else "casbin_policy_denied"


class ApiRBACPermission(BasePermission):
    def has_permission(self, request, view):
        path = request.META["PATH_INFO"]
        method = request.method
        allowed, reason = verify_permission(request.user, path, method)
        if not allowed:
            create_access_log(
                user=request.user,
                path=path,
                method=method,
                reason=reason,
            )
            self.message = "Permission denied"
        return allowed
