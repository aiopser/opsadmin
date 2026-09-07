from rest_framework.decorators import action
from django.db.models import Q
from drf_spectacular.utils import extend_schema

from common.api.responses import api_ok_response, api_error_response
from common.api.schema import generate_crud_schema
from common.api.viewsets import StandardModelViewSet
from ..models import Menu, MenuButton, Permission, Role
from ..seed_data import SYSTEM_ROLE_ADMIN
from ..serializers import RoleSerializer


@generate_crud_schema(verbose_name="角色", tags=["角色管理"])
class RoleViewSet(StandardModelViewSet):
    queryset = Role.objects.prefetch_related("permission").filter().order_by("-id")
    serializer_class = RoleSerializer
    ordering_fields = ("id",)
    filterset_fields = ("id",)
    search_fields = ("name",)

    def get_queryset(self):
        queryset = super().get_queryset()
        keywords = (self.request.query_params.get("keywords") or "").strip()
        if keywords:
            queryset = queryset.filter(Q(name__icontains=keywords))
        role_name = (self.request.query_params.get("roleName") or "").strip()
        if role_name:
            queryset = queryset.filter(Q(name__icontains=role_name))
        role_code = (self.request.query_params.get("roleCode") or "").strip()
        if role_code:
            queryset = queryset.filter(Q(code__icontains=role_code))
        status = (self.request.query_params.get("status") or "").strip()
        if status in ("1", "2"):
            queryset = queryset.filter(is_active=(status == "1"))
        return queryset

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if getattr(instance, "is_system", False):
            if "name" in request.data and request.data.get("name") != instance.name:
                return api_error_response("Built-in role name cannot be changed")
            if not getattr(request.user, "is_superuser", False):
                return api_error_response(
                    "Built-in role can only be maintained by superuser"
                )
        return super(RoleViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        raw_pk = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""))
        ids = [item for item in raw_pk.split(",") if item]
        if len(ids) > 1:
            protected_count = (
                self.get_queryset()
                .filter(
                    Q(pk__in=ids, is_system=True) | Q(pk__in=ids, name=SYSTEM_ROLE_ADMIN)
                )
                .count()
            )
            if protected_count:
                return api_error_response("Built-in data cannot be deleted")
            deleted, _ = self.get_queryset().filter(pk__in=ids).delete()
            return api_ok_response({"deleted": deleted})

        instance = self.get_object()
        if getattr(instance, "is_system", False) or instance.name == SYSTEM_ROLE_ADMIN:
            return api_error_response("Built-in data cannot be deleted")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(summary="获取角色选项", tags=["角色管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request):
        return api_ok_response(
            [
                {
                    "value": role.id,
                    "label": role.name,
                }
                for role in self.get_queryset().order_by("id")
            ]
        )

    @extend_schema(summary="获取角色表单数据", tags=["角色管理"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)

    @extend_schema(summary="获取角色菜单ID列表", tags=["角色管理"])
    @action(methods=["GET"], detail=True, url_path="menu-ids")
    def menu_ids(self, request, pk=None):
        role = self.get_object()
        menu_permissions = role.permission.filter(
            type=Permission.PermissionType.MENU,
            is_active=True,
        )
        button_permissions = role.permission.filter(
            type=Permission.PermissionType.BUTTON,
            is_active=True,
        )
        selected_menus = (
            Menu.objects.filter(
                permission__in=menu_permissions,
                menu_type__in=[Menu.MenuType.CATALOG, Menu.MenuType.MENU],
            )
            .distinct()
            .values_list("id", flat=True)
        )
        selected_buttons = (
            MenuButton.objects.filter(permission__in=button_permissions)
            .distinct()
            .values_list("id", flat=True)
        )
        return api_ok_response(
            {
                "menuIds": [str(menu_id) for menu_id in selected_menus],
                "buttonIds": [str(button_id) for button_id in selected_buttons],
                "homePath": role.home_path,
            }
        )

    @extend_schema(summary="分配角色菜单", tags=["角色管理"])
    @action(methods=["PUT"], detail=True, url_path="menus")
    def menus(self, request, pk=None):
        role = self.get_object()
        menu_ids = request.data.get("menuIds", [])
        button_ids = request.data.get("buttonIds", [])
        home_path = request.data.get("homePath", None)
        if home_path is None:
            home_path = request.data.get("home_path", None)
        permission_ids = []
        selected_menus = Menu.objects.filter(
            id__in=menu_ids,
            menu_type__in=[Menu.MenuType.CATALOG, Menu.MenuType.MENU],
        ).prefetch_related("permission")
        for menu in selected_menus:
            permission_ids.extend(menu.permission.values_list("id", flat=True))
        selected_buttons = MenuButton.objects.filter(id__in=button_ids).prefetch_related(
            "permission"
        )
        for button in selected_buttons:
            permission_ids.extend(button.permission.values_list("id", flat=True))
        role.permission.set(set(permission_ids))
        # 默认首页路由名，空字符串归一化为 None
        normalized_home_path = (str(home_path).strip() if home_path else "") or None
        if normalized_home_path != role.home_path:
            role.home_path = normalized_home_path
            role.save(update_fields=["home_path"])
        return api_ok_response()

    @extend_schema(summary="获取角色部门ID列表", tags=["角色管理"])
    @action(methods=["GET"], detail=True, url_path="dept-ids")
    def dept_ids(self, request, pk=None):
        return api_ok_response([])
