from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema

from common.api.responses import api_error_response, api_ok_response
from common.api.schema import generate_crud_schema
from common.api.viewsets import StandardModelViewSet
from ..models import Permission
from ..serializers import PermissionSerializer


@generate_crud_schema(verbose_name="权限", tags=["权限管理"])
class PermissionViewSet(StandardModelViewSet):
    queryset = (
        Permission.objects.select_related("pid")
        .prefetch_related("role")
        .filter()
        .order_by("id")
    )
    serializer_class = PermissionSerializer
    ordering_fields = ("id", "code", "type")
    filterset_fields = ("id", "name", "type", "pid", "is_active")
    search_fields = ("name", "code", "path", "method")

    @extend_schema(summary="获取权限树", tags=["权限管理"])
    @action(methods=["GET"], detail=False)
    def tree(self, request, *args, **kwargs):
        t_l = []
        parent_queryset = self.get_queryset().filter(pid=None)
        for inc in parent_queryset:
            parent_ser = self.get_serializer(inc, many=False)
            children_inc = self.get_queryset().filter(pid=inc)
            parent_dic = parent_ser.data
            parent_dic["children"] = self.get_serializer(children_inc, many=True).data
            t_l.append(parent_dic)
        return api_ok_response(t_l)

    @extend_schema(summary="获取顶级权限", tags=["权限管理"])
    @action(methods=["GET"], detail=False)
    def parent(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_queryset().filter(pid=None), many=True
        )
        return api_ok_response(serializer.data)

    @extend_schema(summary="获取权限选项", tags=["权限管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request, *args, **kwargs):
        permission_type = request.query_params.get("type")
        queryset = self.get_queryset().filter(is_active=True)
        if permission_type:
            queryset = queryset.filter(type=permission_type)
        return api_ok_response(
            [
                {
                    "value": str(permission.id),
                    "label": f"{permission.name}({permission.code})",
                    "code": permission.code,
                    "type": permission.type,
                    "path": permission.path,
                    "method": permission.method,
                }
                for permission in queryset.order_by("type", "code", "id")
            ]
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if getattr(instance, "is_system", False):
            immutable_fields = ("code", "type", "path", "method", "name")
            changed_fields = [
                field
                for field in immutable_fields
                if field in request.data
                and request.data.get(field) != getattr(instance, field)
            ]
            if changed_fields:
                return api_error_response(
                    "Built-in permission core fields cannot be changed"
                )
            if not getattr(request.user, "is_superuser", False):
                return api_error_response(
                    "Built-in permission can only be maintained by superuser"
                )
        return super(PermissionViewSet, self).update(request, *args, **kwargs)
