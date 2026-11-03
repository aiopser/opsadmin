from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import HTTP_HEADER_ENCODING, authentication, serializers, status
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework.exceptions import PermissionDenied


def request_path_requires_password_change(path):
    allowed = {
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/users/profile",
        "/api/v1/users/password",
        "/api/v1/menus/routes",
        "/api/v1/configs/public",
    }
    return bool(path) and path.rstrip("/") not in allowed


AUTH_HEADER_TYPES = api_settings.AUTH_HEADER_TYPES

if not isinstance(api_settings.AUTH_HEADER_TYPES, (list, tuple)):
    AUTH_HEADER_TYPES = (AUTH_HEADER_TYPES,)

AUTH_HEADER_TYPE_BYTES = {h.encode(HTTP_HEADER_ENCODING) for h in AUTH_HEADER_TYPES}


class CustomBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, ldap=None, **kwargs):
        # serializer 未注入 context["request"] 时，django authenticate 会以 request=None 调用
        ldap = request.data.get("ldap") if request is not None else None
        if ldap:
            return None
        from common.system_policy import positive_config

        maximum = positive_config("security.login.max_failures", 5)
        error = None
        with transaction.atomic():
            try:
                user = (
                    get_user_model()
                    .objects.select_for_update()
                    .get(Q(username=username) | Q(email=username))
                )
            except get_user_model().DoesNotExist as exc:
                raise serializers.ValidationError("用户名或密码错误") from exc
            now = timezone.now()
            if user.login_locked_until and user.login_locked_until > now:
                error = "登录失败次数过多，请稍后重试"
            elif user.check_password(password):
                user.login_failure_count = 0
                user.login_locked_until = None
                user.save(update_fields=["login_failure_count", "login_locked_until"])
                if not user.is_active or not getattr(user, "job_status", True):
                    error = "用户已被禁用，请联系管理员"
            else:
                if user.login_locked_until and user.login_locked_until <= now:
                    user.login_failure_count = 0
                user.login_failure_count += 1
                if user.login_failure_count >= maximum:
                    user.login_locked_until = now + timezone.timedelta(minutes=15)
                user.save(update_fields=["login_failure_count", "login_locked_until"])
                error = "用户名或密码错误"
        if error:
            raise serializers.ValidationError(error)
        return user


class InvalidToken(AuthenticationFailed):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Token is invalid or expired")
    default_code = "token_not_valid"


class JWTAuthentication(authentication.BaseAuthentication):
    www_authenticate_realm = "api"
    media_type = "application/json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_model = get_user_model()

    def authenticate(self, request):
        self.request_path = request.path
        header = self.get_header(request)
        if header is None:
            return None
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token

    def authenticate_header(self, request):
        return '{} realm="{}"'.format(AUTH_HEADER_TYPES[0], self.www_authenticate_realm)

    def get_header(self, request):
        header = request.META.get(api_settings.AUTH_HEADER_NAME)
        if isinstance(header, str):
            header = header.encode(HTTP_HEADER_ENCODING)
        return header

    def get_raw_token(self, header):
        parts = header.split()
        if len(parts) == 0:
            raise InvalidToken(
                {
                    "data": {},
                    "message": "Authentication credentials were not provided",
                    "code": 10401,
                    "detail": "missing token",
                }
            )
        if parts[0] not in AUTH_HEADER_TYPE_BYTES:
            raise InvalidToken(
                {
                    "data": {},
                    "message": "Invalid token header type",
                    "code": 10401,
                    "detail": "invalid token",
                }
            )
        if len(parts) != 2:
            raise InvalidToken(
                {
                    "data": {},
                    "message": "Authorization header must contain two space-delimited values",
                    "code": 10401,
                    "detail": "invalid token",
                }
            )
        return parts[1]

    def get_validated_token(self, raw_token):
        message = ""
        for auth_token in api_settings.AUTH_TOKEN_CLASSES:
            try:
                return auth_token(raw_token)
            except TokenError as exc:
                message = exc.args[0]
        raise InvalidToken({"data": {}, "message": message, "code": 10402})

    def get_user(self, validated_token):
        try:
            user_id = validated_token[api_settings.USER_ID_CLAIM]
        except KeyError as exc:
            raise InvalidToken(
                _("Token contained no recognizable user identification")
            ) from exc

        try:
            user = self.user_model.objects.get(**{api_settings.USER_ID_FIELD: user_id})
        except self.user_model.DoesNotExist as exc:
            raise AuthenticationFailed(
                _("User not found"), code="user_not_found"
            ) from exc

        if not user.is_active or not getattr(user, "job_status", True):
            raise AuthenticationFailed(_("用户已被禁用，请联系管理员"), code="user_inactive")
        if validated_token.get("auth_version", 0) != user.auth_version:
            raise AuthenticationFailed(_("密码已变更，请重新登录"), code="session_revoked")
        if user.must_change_password and request_path_requires_password_change(
            getattr(self, "request_path", "")
        ):
            raise PermissionDenied(_("请先修改初始密码"), code="password_change_required")
        return user


class MyTokenSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["name"] = user.username
        token["auth_version"] = user.auth_version
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_active or not getattr(self.user, "job_status", True):
            raise AuthenticationFailed(_("用户已被禁用，请联系管理员"), code="user_inactive")
        refresh = self.get_token(self.user)
        expires_in = api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()
        data["accessToken"] = data["access"]
        data["refreshToken"] = data["refresh"]
        data["tokenType"] = "Bearer"
        data["expiresIn"] = int(expires_in)
        data["expire"] = refresh.access_token.payload["exp"]
        data["username"] = self.user.username
        data["email"] = self.user.email
        return data
