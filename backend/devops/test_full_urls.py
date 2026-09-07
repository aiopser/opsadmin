"""Exercise the existing business routes without changing deployment settings."""

from django.urls import include, path

from .urls import urlpatterns as base_urlpatterns

urlpatterns = [
    *base_urlpatterns,
    path("api/", include("apps.cmdb.urls")),
    path("api/", include("apps.automation.urls")),
    path("api/", include("apps.jobs.urls")),
]
