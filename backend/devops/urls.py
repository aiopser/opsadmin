from django.conf import settings
from django.views import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

from common.api.log_views import LogBatchDeleteApiView, LogListApiView, VisitOverviewApiView, VisitTrendApiView
from common.api.file_views import FileUploadApiView


urlpatterns = [
    re_path(r"media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    path("admin/", admin.site.urls),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(
            url_name="schema", permission_classes=[AllowAny]
        ),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema", permission_classes=[AllowAny]),
        name="redoc",
    ),
    path("api/v1/logs", LogListApiView.as_view()),
    path("api/v1/logs/delete/<path:ids>", LogBatchDeleteApiView.as_view()),
    path("api/v1/logs/analytics/overview", VisitOverviewApiView.as_view()),
    path("api/v1/logs/analytics/trend", VisitTrendApiView.as_view()),
    # path("api/v1/files", FileUploadApiView.as_view()),
    path("api/", include("apps.user.urls")),
    path("api/", include("apps.permission.urls")),
    # path("api/", include("apps.cmdb.urls")),
    # path("api/", include("apps.automation.urls")),
    # path("api/", include("apps.jobs.urls")),
    path("api/", include("apps.audit_center.urls")),
]

if not settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^static/(?P<path>.*)$",
            static.serve,
            {"document_root": settings.STATIC_ROOT},
            name="static",
        ),
    ]
