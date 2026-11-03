from rest_framework import serializers
from django.conf import settings
from urllib.parse import urlparse

from common.api.serializers import StandardModelSerializer
from .models import Department, UserProfile


class UserProfileSerializer(StandardModelSerializer):
    class Meta:
        model = UserProfile
        fields = (
            "id",
            "username",
            "name",
            "phone",
            "email",
            "icon",
            "gender",
            "position",
            "department",
            "staff_id",
            "job_status",
            "remarks",
            "role",
            "is_active",
            "first_name",
            "last_name",
            "last_login",
            "date_joined",
            "must_change_password",
        )
        read_only_fields = ("last_login", "date_joined", "must_change_password")
        extra_kwargs = {
            "name": {"required": False, "allow_blank": True},
            "phone": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "icon": {"required": False, "allow_null": True},
            "gender": {"required": False},
        }

    def to_internal_value(self, data):
        forbidden = {
            "is_superuser",
            "is_staff",
            "groups",
            "user_permissions",
            "auth_version",
            "must_change_password",
            "login_failure_count",
            "login_locked_until",
        } & set(data)
        if forbidden:
            raise serializers.ValidationError(
                {field: "用户管理不能修改此安全字段" for field in sorted(forbidden)}
            )
        self._avatar_path = None
        mutable = data.copy()
        if "nickname" in mutable:
            mutable["name"] = mutable.get("nickname") or ""
        if "mobile" in mutable:
            mutable["phone"] = mutable.get("mobile") or ""
        if "avatar" in mutable:
            avatar = mutable.get("avatar")
            if hasattr(avatar, "read"):
                mutable["icon"] = avatar
            elif avatar:
                normalized_avatar = self._normalize_avatar_path(str(avatar))
                if normalized_avatar:
                    self._avatar_path = normalized_avatar
                mutable.pop("icon", None)
            else:
                mutable.pop("icon", None)
            mutable.pop("avatar", None)
        elif "icon" in mutable and isinstance(mutable.get("icon"), str):
            mutable.pop("icon")
        if "icon" in mutable and not mutable.get("icon"):
            mutable.pop("icon")
        if "deptId" in mutable:
            dept_id = mutable.get("deptId")
            mutable["department"] = None if dept_id in (None, "", "0", 0) else dept_id
        if "roleIds" in mutable:
            mutable["role"] = mutable.get("roleIds") or []
        if "status" in mutable:
            enabled = mutable.get("status") == 1
            mutable["job_status"] = enabled
            mutable["is_active"] = enabled
        return super().to_internal_value(mutable)

    def validate_role(self, roles):
        actor = getattr(self.context.get("request"), "user", None)
        if getattr(actor, "is_superuser", False):
            return roles
        from rest_framework.exceptions import PermissionDenied

        if actor is None:
            raise PermissionDenied("角色分配需要明确操作者")
        active_roles = actor.role.filter(is_active=True)
        allowed = set(active_roles.values_list("permission__id", flat=True))
        scope_order = {"own": 0, "department": 1, "all": 2}
        maximum_scope = max(
            (
                scope_order.get(value, 0)
                for value in active_roles.values_list("job_data_scope", flat=True)
            ),
            default=0,
        )
        for role in roles:
            if (
                role.code == "admin"
                or role.name == "admin"
                or not set(role.permission.values_list("id", flat=True)).issubset(
                    allowed
                )
            ):
                raise PermissionDenied("不能授予超出当前操作者权限的角色")
            if scope_order.get(role.job_data_scope, 0) > maximum_scope:
                raise PermissionDenied("不能授予超出当前操作者数据范围的角色")
        return roles

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._save_avatar_path(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._save_avatar_path(instance)
        return instance

    def _save_avatar_path(self, instance):
        avatar_path = getattr(self, "_avatar_path", None)
        if avatar_path:
            instance.icon.name = avatar_path
            instance.save(update_fields=["icon"])

    def _normalize_avatar_path(self, avatar):
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        parsed_path = urlparse(avatar).path or avatar
        if parsed_path.startswith(media_url):
            return parsed_path[len(media_url) :].lstrip("/")
        if parsed_path.startswith("/"):
            return parsed_path.lstrip("/")
        return parsed_path

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        role_list = instance.role.all()
        representation["roles"] = [role.name for role in role_list]
        representation["role_codes"] = [role.code or role.name for role in role_list]
        representation["perms"] = sorted(
            {
                permission.code
                for role in role_list
                for permission in role.permission.filter(is_active=True)
            }
        )
        representation["dep"] = (
            instance.department.name if instance.department else None
        )
        representation["userId"] = str(instance.id)
        representation["nickname"] = instance.name
        representation["avatar"] = instance.icon.url if instance.icon else ""
        representation["mobile"] = instance.phone
        representation["gender"] = instance.gender
        representation["status"] = (
            1 if instance.is_active and instance.job_status else 0
        )
        representation["deptId"] = (
            str(instance.department_id) if instance.department_id else None
        )
        representation["deptName"] = (
            instance.department.name if instance.department else None
        )
        representation["roleIds"] = [role.id for role in role_list]
        representation["roleNames"] = ",".join(role.name for role in role_list)
        representation["createTime"] = (
            getattr(instance, "created_at", None) or instance.date_joined
        )
        representation["updateTime"] = getattr(instance, "updated_at", None)
        return representation


class UserProfileUpdateSerializer(UserProfileSerializer):
    """Allow users to maintain contact details without changing access."""

    class Meta(UserProfileSerializer.Meta):
        fields = ("name", "phone", "email", "icon", "gender")
        exclude = None

    def to_internal_value(self, data):
        allowed_fields = {*self.Meta.fields, "nickname", "mobile", "avatar"}
        forbidden_fields = set(data) - allowed_fields
        if forbidden_fields:
            raise serializers.ValidationError(
                {field: "个人资料不能修改此字段" for field in sorted(forbidden_fields)}
            )
        return super().to_internal_value(data)


class DepartmentSerializer(StandardModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"

    def to_internal_value(self, data):
        mutable = data.copy()
        if "parentId" in mutable:
            parent_id = mutable.get("parentId")
            mutable["parent"] = None if parent_id in (None, "", "0", 0) else parent_id
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        parent = attrs.get("parent")
        instance = getattr(self, "instance", None)
        if instance and parent:
            if parent.id == instance.id:
                raise serializers.ValidationError({"parentId": "上级部门不能是当前部门"})
            current_parent = parent.parent
            while current_parent:
                if current_parent.id == instance.id:
                    raise serializers.ValidationError({"parentId": "上级部门不能是当前部门的子部门"})
                current_parent = current_parent.parent
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        user_list = instance.user.all()
        representation["user"] = [
            UserProfileSerializer(user).data for user in user_list
        ]
        representation["parentId"] = (
            str(instance.parent_id) if instance.parent_id else "0"
        )
        representation["sort"] = instance.sort
        representation["status"] = instance.status
        representation["treePath"] = self._get_tree_path(instance)
        representation["createTime"] = instance.created_at
        representation["updateTime"] = instance.updated_at
        return representation

    def _get_tree_path(self, instance):
        ids = [str(instance.id)]
        parent = instance.parent
        while parent:
            ids.append(str(parent.id))
            parent = parent.parent
        return ",".join(reversed(ids))
