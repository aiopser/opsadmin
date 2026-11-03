from rest_framework.routers import SimpleRouter
from django.urls import path
from .views import TemplateViewSet, VersionViewSet, CredentialViewSet, RequestViewSet

router = SimpleRouter(trailing_slash=False)
router.register(
    "v1/provisioning/templates", TemplateViewSet, basename="provisioning-templates"
)
router.register(
    "v1/provisioning/versions", VersionViewSet, basename="provisioning-versions"
)
router.register(
    "v1/provisioning/credentials",
    CredentialViewSet,
    basename="provisioning-credentials",
)
router.register(
    "v1/provisioning/requests", RequestViewSet, basename="provisioning-requests"
)
from .views import OperationsHealthView
from .catalog_views import CatalogView, ConfigurationCatalogView

urlpatterns = [
    path("v1/provisioning/operations/health", OperationsHealthView.as_view()),
    path("v1/provisioning/catalog", CatalogView.as_view()),
    path("v1/provisioning/catalog/configuration", ConfigurationCatalogView.as_view()),
] + router.urls
