"""
认证与会话管理 - 独立 APIView（手动注册路由）

登录/刷新令牌/获取当前用户/退出登录属于非资源型端点，
按「ViewSet + Router 与 APIView 组合使用」的约定，
这类端点以独立 APIView 实现，并在 urls.py 中手动添加到 urlpatterns：
    POST /api/v1/auth/login          -> LoginApiView
    POST /api/v1/auth/refresh-token  -> RefreshTokenApiView
    GET  /api/v1/auth/me             -> UserInfoApiView
    POST /api/v1/auth/logout         -> LogoutApiView

每个 APIView 只承载一个 HTTP 方法、只挂载一个 URL 路径，
避免同一视图挂载多条路径或混合多个方法导致接口文档"重复"。
"""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.settings import api_settings

from common.api.responses import (
    BAD_REQUEST,
    REFRESH_TOKEN_INVALID,
    UNAUTHORIZED,
    api_error_response,
    api_ok_response,
)
from common.api.schema import api_envelope_serializer, api_message_response
from common.api.views import StandardApiView, StandardOpenApiView
from common.auth.jwt import MyTokenSerializer
from apps.audit_center.services import create_domain_audit_event
from ..models import UserProfile
from ..serializers import UserProfileSerializer


def _is_bad_login_request(error):
    detail = getattr(error, "detail", None)
    if not isinstance(detail, dict):
        return False
    field_names = set(detail.keys())
    return bool(field_names - {"non_field_errors"})


def _format_login_error(error):
    detail = getattr(error, "detail", None)
    if isinstance(detail, dict):
        messages = []
        for value in detail.values():
            if isinstance(value, (list, tuple)):
                messages.extend(str(item) for item in value)
            else:
                messages.append(str(value))
        message = "；".join(messages)
    elif isinstance(detail, (list, tuple)):
        message = "；".join(str(item) for item in detail)
    elif detail:
        message = str(detail)
    else:
        message = str(error)

    if (
        "disabled" in message.lower()
        or "inactive" in message.lower()
        or "禁用" in message
    ):
        return "用户已被禁用，请联系管理员"
    if "username" in message.lower() or "password" in message.lower():
        return "用户名或密码错误"
    return "登录失败"


def _record_login_attempt(request, *, actor=None, result, reason):
    raw_username = request.data.get("username", "")
    username = raw_username.strip()[:150] if isinstance(raw_username, str) else ""
    create_domain_audit_event(
        actor=actor,
        action=f"auth.login.{result}",
        resource_type="login",
        resource_id=username,
        after={"reason": reason},
        request=request,
        domain="security",
        result=result,
    )


def _login_failure_reason(error, is_bad_request):
    if is_bad_request:
        return "invalid_request"
    if isinstance(error, (AuthenticationFailed, ValidationError)):
        return "authentication_failed"
    return "internal_error"


class LoginApiView(StandardOpenApiView):
    """用户登录（开放接口，无需认证）"""

    @extend_schema(
        summary="用户登录",
        tags=["认证中心"],
        auth=[],
        request=inline_serializer(
            name="AuthLoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(),
            },
        ),
        responses=inline_serializer(
            name="AuthLoginResponse",
            fields={
                "code": serializers.IntegerField(),
                "data": inline_serializer(
                    name="AuthLoginData",
                    fields={
                        "refresh": serializers.CharField(),
                        "access": serializers.CharField(),
                        "expire": serializers.IntegerField(),
                        "username": serializers.CharField(),
                        "email": serializers.EmailField(),
                    },
                ),
                "message": serializers.CharField(allow_null=True),
            },
        ),
    )
    def post(self, request, *args, **kwargs):
        # 注入 context["request"]：TokenObtainPairSerializer.validate 需要它
        # 传给 django authenticate，否则 CustomBackend 收到 request=None
        serializer = MyTokenSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            is_bad_request = _is_bad_login_request(e)
            _record_login_attempt(
                request,
                result="failure",
                reason=_login_failure_reason(e, is_bad_request),
            )
            return api_error_response(
                _format_login_error(e),
                code=BAD_REQUEST if is_bad_request else UNAUTHORIZED,
                http_status=(
                    status.HTTP_400_BAD_REQUEST
                    if is_bad_request
                    else status.HTTP_401_UNAUTHORIZED
                ),
            )
        _record_login_attempt(
            request, actor=serializer.user, result="success", reason="authenticated"
        )
        return api_ok_response(serializer.validated_data)


class RefreshTokenApiView(StandardOpenApiView):
    """刷新 Token（开放接口，无需认证）"""

    @extend_schema(
        summary="刷新 Token",
        tags=["认证中心"],
        auth=[],
        request=inline_serializer(
            name="AuthRefreshTokenRequest",
            fields={"refreshToken": serializers.CharField(required=False)},
        ),
        responses=inline_serializer(
            name="AuthRefreshTokenResponse",
            fields={
                "code": serializers.CharField(),
                "data": inline_serializer(
                    name="AuthRefreshTokenData",
                    fields={
                        "accessToken": serializers.CharField(),
                        "refreshToken": serializers.CharField(),
                        "tokenType": serializers.CharField(),
                        "expiresIn": serializers.IntegerField(),
                    },
                ),
                "msg": serializers.CharField(allow_null=True),
            },
        ),
    )
    def post(self, request, *args, **kwargs):
        raw_refresh = request.data.get("refreshToken")
        if not raw_refresh:
            return api_error_response(
                "refreshToken is required",
                code=BAD_REQUEST,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(raw_refresh)
            if not UserProfile.objects.filter(
                pk=refresh[api_settings.USER_ID_CLAIM],
                is_active=True,
                job_status=True,
                auth_version=refresh.get("auth_version", 0),
            ).exists():
                raise TokenError("User unavailable")
            access = refresh.access_token
        except (TokenError, KeyError, TypeError, ValueError):
            return api_error_response(
                "Refresh token is invalid or expired",
                code=REFRESH_TOKEN_INVALID,
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        return api_ok_response(
            {
                "accessToken": str(access),
                "refreshToken": str(refresh),
                "tokenType": "Bearer",
                "expiresIn": int(access.lifetime.total_seconds()),
            }
        )


class UserInfoApiView(StandardApiView):
    """获取当前登录用户信息（需登录，不做 RBAC 校验）"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="获取当前登录用户信息",
        tags=["认证中心"],
        responses=api_envelope_serializer(
            "AuthUserInfoResponse", UserProfileSerializer
        ),
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        try:
            u = UserProfile.objects.get(id=user.id)
        except UserProfile.DoesNotExist:
            return api_error_response(message="not found")
        s = UserProfileSerializer(u)
        return api_ok_response(data=s.data)


class LogoutApiView(StandardApiView):
    """退出登录（需登录）"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="退出登录",
        tags=["认证中心"],
        request=inline_serializer(
            name="AuthLogoutRequest",
            fields={"refreshToken": serializers.CharField()},
        ),
        responses=api_message_response("AuthLogoutResponse"),
    )
    def post(self, request, *args, **kwargs):
        raw_refresh = request.data.get("refreshToken")
        try:
            if not isinstance(raw_refresh, str) or not raw_refresh:
                raise TokenError("Missing refresh token")
            refresh = RefreshToken(raw_refresh)
            if str(refresh[api_settings.USER_ID_CLAIM]) != str(request.user.pk):
                raise TokenError("Token owner mismatch")
            refresh.blacklist()
        except (TokenError, KeyError, TypeError, ValueError):
            return api_error_response(
                "Invalid refresh token",
                code=BAD_REQUEST,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        return api_ok_response(data="ok")
