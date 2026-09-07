import time

from django.db import OperationalError, ProgrammingError, connection

from apps.permission.audit import clear_audit_actor, set_audit_actor


class PermissionAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_audit_actor(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            clear_audit_actor()


class OperationLogMiddleware:
    EXCLUDED_PREFIXES = (
        "/api/schema",
        "/api/v1/logs",
        "/admin",
        "/media",
        "/static",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started_at = time.perf_counter()
        response = None
        error = None
        try:
            response = self.get_response(request)
            return response
        except Exception as exc:
            error = exc
            raise
        finally:
            execution_time = int((time.perf_counter() - started_at) * 1000)
            self._write_log(request, response, error, execution_time)

    def _write_log(self, request, response, error, execution_time):
        if self._should_skip(request):
            return
        try:
            from apps.permission.models import OperationLog

            if (
                OperationLog._meta.db_table
                not in connection.introspection.table_names()
            ):
                return
            status_code = getattr(response, "status_code", 500 if error else 200)
            user = getattr(request, "user", None)
            is_authenticated = getattr(user, "is_authenticated", False)
            OperationLog.objects.create(
                module=self._infer_module(request.path),
                action_type=request.method.upper(),
                title=self._build_title(request),
                content="",
                operator=user if is_authenticated else None,
                operator_name=getattr(user, "username", "") if is_authenticated else "",
                request_uri=request.path[:255],
                request_method=request.method.upper(),
                ip=self._get_client_ip(request),
                region="",
                device="Web",
                browser=self._get_browser(request),
                os=self._get_os(request),
                status=1 if status_code < 400 and error is None else 0,
                execution_time=execution_time,
                error_msg=self._get_error_message(response, error),
            )
        except (OperationalError, ProgrammingError):
            return

    def _should_skip(self, request):
        path = request.path or ""
        if request.method.upper() == "OPTIONS":
            return True
        if any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES):
            return True
        if not self._get_config_bool("log.operation.enabled", True):
            return True
        if request.method.upper() == "GET" and not self._get_config_bool(
            "log.operation.record_get", True
        ):
            return True
        return False

    def _get_config_bool(self, key, default):
        try:
            from apps.permission.views.config import get_system_config_snapshot

            value = get_system_config_snapshot().get(key)
        except Exception:
            return default
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _get_client_ip(self, request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.META.get("HTTP_X_REAL_IP")
        if real_ip:
            return real_ip
        return request.META.get("REMOTE_ADDR", "")

    def _get_browser(self, request):
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        if "Edg/" in user_agent:
            return "Edge"
        if "Chrome/" in user_agent:
            return "Chrome"
        if "Firefox/" in user_agent:
            return "Firefox"
        if "Safari/" in user_agent:
            return "Safari"
        return "Unknown"

    def _get_os(self, request):
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        if "Windows" in user_agent:
            return "Windows"
        if "Mac OS X" in user_agent:
            return "macOS"
        if "Android" in user_agent:
            return "Android"
        if "iPhone" in user_agent or "iPad" in user_agent:
            return "iOS"
        if "Linux" in user_agent:
            return "Linux"
        return "Unknown"

    def _infer_module(self, path):
        module_map = {
            "/api/v1/users": "用户管理",
            "/api/v1/depts": "部门管理",
            "/api/v1/roles": "角色管理",
            "/api/v1/menus": "菜单管理",
            "/api/v1/dicts": "字典管理",
            "/api/v1/configs": "系统配置",
            "/api/v1/auth": "认证中心",
        }
        for prefix, module in module_map.items():
            if path.startswith(prefix):
                return module
        return "系统接口"

    def _build_title(self, request):
        method_map = {
            "GET": "查询",
            "POST": "新增",
            "PUT": "修改",
            "PATCH": "修改",
            "DELETE": "删除",
        }
        return f"{method_map.get(request.method.upper(), request.method.upper())}{self._infer_module(request.path)}"

    def _get_error_message(self, response, error):
        if error:
            return "Internal server error"
        if not response or getattr(response, "status_code", 200) < 400:
            return ""
        try:
            return f"HTTP {getattr(response, 'status_code', 500)}"
        except Exception:
            return f"HTTP {getattr(response, 'status_code', 500)}"
