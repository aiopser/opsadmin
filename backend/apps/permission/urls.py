"""
权限模块路由 - ViewSet + Router 单一注册

所有资源型接口统一交给一个 Router 自动生成路由，每个 ViewSet 只注册一次：
    /api/v1/roles                    角色管理（含 options/form/menu-ids/menus/dept-ids）
    /api/v1/permissions              权限管理（含 tree/parent/options）
    /api/v1/menus                    菜单管理（含 tree/routes/mine/options/form 等）
    /api/v1/dicts                    字典管理（含 options/form）
    /api/v1/dicts/{dict_code}/items  字典项管理（含 options/form）
    /api/v1/configs                  系统配置（含 form/refresh/snapshot）

注册约定：
- 显式指定 basename，生成稳定的路由名称（如 roles-list / roles-detail）；
  注册前缀不含模型资源名的视图（如嵌套的字典项）时 basename 尤其必要。
- 同一 ViewSet 不重复挂载多个 URL 前缀，避免 Swagger UI 出现"重复"接口。
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.permission.views.config import PublicConfigApiView, SystemConfigViewSet
from apps.permission.views.dict import DictItemViewSet, DictTypeViewSet
from apps.permission.views.menu import MenuViewSet
from apps.permission.views.permission import PermissionViewSet
from apps.permission.views.role import RoleViewSet

router = SimpleRouter(trailing_slash=False)
router.register(r"v1/roles", RoleViewSet, basename="roles")
router.register(r"v1/permissions", PermissionViewSet, basename="permissions")
router.register(r"v1/menus", MenuViewSet, basename="menus")
router.register(r"v1/dicts", DictTypeViewSet, basename="dicts")
router.register(
    r"v1/dicts/(?P<dict_code>[^/.]+)/items",
    DictItemViewSet,
    basename="dict-items",
)
router.register(r"v1/configs", SystemConfigViewSet, basename="configs")

# 公开配置端点必须排在 router.urls 之前：Django 按顺序匹配，
# 否则 "public" 会先被 Router 的 detail 路由捕获为配置 pk，导致 401
urlpatterns = [
    path("v1/configs/public", PublicConfigApiView.as_view(), name="public-configs"),
] + router.urls
