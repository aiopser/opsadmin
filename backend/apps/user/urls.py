"""
用户模块路由 - ViewSet + Router 与 APIView 组合使用

一、资源型接口（ViewSet + Router）：
    Router 自动生成标准 REST 路由及 @action 自定义动作：
    GET/POST /api/v1/depts, GET/PUT/PATCH/DELETE /api/v1/depts/{pk}
    GET/POST /api/v1/users, GET/PUT/PATCH/DELETE /api/v1/users/{pk}

二、非资源型认证接口（APIView + 手动注册）：
    每个 APIView 仅挂载一条 URL 路径，避免接口文档重复：
    POST /api/v1/auth/login
    POST /api/v1/auth/refresh-token
    GET  /api/v1/auth/me
    POST /api/v1/auth/logout
"""

from django.urls import path
from rest_framework.routers import SimpleRouter

from .views.auth import (
    LoginApiView,
    LogoutApiView,
    RefreshTokenApiView,
    UserInfoApiView,
)
from .views.department import DepartmentViewSet
from .views.user_profile import UserProfileViewSet

# ── ViewSet 交给 Router：资源型 CRUD，自动生成路由 ──
# basename 用于生成路由名称（如 users-list / users-detail），显式指定以保证稳定
router = SimpleRouter(trailing_slash=False)
router.register(r"v1/depts", DepartmentViewSet, basename="depts")
router.register(r"v1/users", UserProfileViewSet, basename="users")

# ── APIView 手动添加到 urlpatterns：认证端点，一条路径对应一个视图 ──
auth_urlpatterns = [
    path("v1/auth/login", LoginApiView.as_view(), name="auth-login"),
    path(
        "v1/auth/refresh-token",
        RefreshTokenApiView.as_view(),
        name="auth-refresh-token",
    ),
    path("v1/auth/me", UserInfoApiView.as_view(), name="auth-me"),
    path("v1/auth/logout", LogoutApiView.as_view(), name="auth-logout"),
]

urlpatterns = router.urls + auth_urlpatterns
