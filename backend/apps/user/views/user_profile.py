from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from django.utils.dateparse import parse_date
from rest_framework.decorators import action
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, inline_serializer
from common.api.schema import api_message_response, generate_crud_schema
from common.api.viewsets import CommaSeparatedBulkDeleteMixin, StandardModelViewSet
from common.api.responses import api_error_response, api_ok_response
from ..models import UserProfile
from ..serializers import UserProfileSerializer


@generate_crud_schema(verbose_name="用户", tags=["用户中心"])
class UserProfileViewSet(CommaSeparatedBulkDeleteMixin, StandardModelViewSet):
    queryset = UserProfile.objects.filter().order_by("-id")
    serializer_class = UserProfileSerializer

    ordering_fields = ("id",)
    filterset_fields = ("id",)
    search_fields = ("name",)

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        keywords = (params.get("keywords") or "").strip()
        status = params.get("status")
        username = (params.get("username") or "").strip()
        nickname = (params.get("nickname") or "").strip()
        phone = (params.get("phone") or "").strip()
        email = (params.get("email") or "").strip()
        gender = params.get("gender")
        dept_id = params.get("deptId")
        create_time = self._get_date_range(params, "createTime")

        if keywords:
            queryset = queryset.filter(
                Q(username__icontains=keywords)
                | Q(name__icontains=keywords)
                | Q(phone__icontains=keywords)
            )
        if status not in (None, ""):
            enabled = str(status) == "1"
            queryset = queryset.filter(is_active=enabled, job_status=enabled)
        if username:
            queryset = queryset.filter(username__icontains=username)
        if nickname:
            queryset = queryset.filter(name__icontains=nickname)
        if phone:
            queryset = queryset.filter(phone__icontains=phone)
        if email:
            queryset = queryset.filter(email__icontains=email)
        if gender not in (None, ""):
            queryset = queryset.filter(gender=gender)
        if dept_id not in (None, "", "0"):
            queryset = queryset.filter(department_id=dept_id)
        if len(create_time) >= 2:
            start_date = parse_date(create_time[0])
            end_date = parse_date(create_time[1])
            if start_date:
                queryset = queryset.filter(date_joined__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(date_joined__date__lte=end_date)
        return queryset

    def _get_date_range(self, params, key):
        values = []
        values.extend(params.getlist(key))
        values.extend(params.getlist(f"{key}[]"))
        if len(values) == 1 and "," in values[0]:
            values = [item.strip() for item in values[0].split(",", 1)]
        return [item for item in values if item]

    def get_permissions(self):
        if getattr(self, "action", None) in {"profile", "password"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        try:
            serializer = UserProfileSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user_obj = serializer.save()
            user_obj.set_password(self._get_initial_password(request))
            user_obj.save()
            return api_ok_response(data=serializer.data)
        except Exception as e:
            return api_error_response(message=str(e))

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data.copy()
        if "icon" in data and data.get("icon"):
            if not isinstance(data.get("icon"), InMemoryUploadedFile):
                del data["icon"]
        elif "icon" in data:
            del data["icon"]
        if "avatar" in data and not data.get("avatar"):
            del data["avatar"]
        if self._is_super_admin(instance) and self._wants_disable(data):
            return api_error_response(message="默认超管用户不能禁用")
        serializer = self.get_serializer(
            instance, data=data, partial=kwargs.pop("partial", False)
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}
        return api_ok_response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        raw_pk = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""))
        ids = [item for item in raw_pk.split(",") if item]

        if len(ids) > 1:
            protected_count = self.get_queryset().filter(
                Q(pk__in=ids, is_superuser=True) | Q(pk__in=ids, username="admin")
            ).count()
            if protected_count:
                return api_error_response(message="默认超管用户不能删除")
            deleted, _ = self.get_queryset().filter(pk__in=ids).delete()
            return api_ok_response({"deleted": deleted})

        instance = self.get_object()
        if self._is_super_admin(instance):
            return api_error_response(message="默认超管用户不能删除")
        return super().destroy(request, *args, **kwargs)

    def _get_initial_password(self, request):
        password = request.data.get("password")
        if password:
            return str(password).strip()
        try:
            from apps.permission.models import SystemConfig

            config = SystemConfig.objects.filter(
                config_key="security.user.default_password"
            ).first()
            if config and config.config_value:
                return config.config_value.strip()
        except Exception:
            pass
        return "123456"

    def _is_super_admin(self, user):
        return bool(
            getattr(user, "is_superuser", False)
            or getattr(user, "username", "") == "admin"
        )

    def _wants_disable(self, data):
        if "status" in data:
            return str(data.get("status")) in ("0", "False", "false")
        if "job_status" in data:
            return str(data.get("job_status")) in ("0", "False", "false")
        if "is_active" in data:
            return str(data.get("is_active")) in ("0", "False", "false")
        return False

    @extend_schema(
        summary="重置用户密码",
        tags=["用户中心"],
        request=inline_serializer(
            name="TemplateResetPasswordRequest",
            fields={"password": serializers.CharField(required=False)},
        ),
        responses=api_message_response("TemplateResetPasswordResponse"),
    )
    @action(methods=["put"], detail=True, url_path="password/reset")
    def password_reset(self, request, pk):
        """Reset password, 兼容 <new_password>/<password> 与 query password."""
        instance = self.get_object()
        new_pwd = (
            request.data.get("new_password")
            or request.data.get("password")
            or request.query_params.get("password")
        )
        if new_pwd:
            instance.set_password(new_pwd.strip())
            instance.save()
            return api_ok_response(data=f"{instance.name} 账户密码修改成功!")
        return api_error_response(message="<name>,<new_password> 为必传参数")

    @extend_schema(summary="获取用户表单数据", tags=["用户中心"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)

    @extend_schema(summary="获取当前用户资料", tags=["用户中心"])
    @action(methods=["GET"], detail=False, url_path="profile")
    def profile(self, request):
        serializer = self.get_serializer(request.user)
        return api_ok_response(serializer.data)

    @extend_schema(summary="更新当前用户资料", tags=["用户中心"])
    @action(methods=["PUT"], detail=False, url_path="profile")
    def update_profile(self, request):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(request=request)
        return api_ok_response(serializer.data)

    @extend_schema(summary="修改当前用户密码", tags=["用户中心"])
    @action(methods=["PUT"], detail=False, url_path="password")
    def password(self, request):
        user = request.user
        old_pwd = request.data.get("oldPassword") or request.data.get("old_password")
        new_pwd = request.data.get("newPassword") or request.data.get("new_password")
        if not old_pwd or not new_pwd:
            return api_error_response("原密码和新密码不能为空")
        if not user.check_password(old_pwd):
            return api_error_response("原密码错误")
        user.set_password(str(new_pwd).strip())
        user.save(update_fields=["password"])
        return api_ok_response("密码修改成功")

    @extend_schema(summary="获取用户选项", tags=["用户中心"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request):
        users = self.get_queryset().order_by("username")
        return api_ok_response(
            [
                {
                    "value": user.id,
                    "label": user.name or user.username,
                }
                for user in users
            ]
        )

