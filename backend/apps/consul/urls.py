from rest_framework.routers import SimpleRouter
from .views import ConsulConnectionViewSet, ConsulTemplateFileViewSet

router = SimpleRouter(trailing_slash=False)
router.register(
    "v1/consul/connections", ConsulConnectionViewSet, basename="consul-connections"
)
router.register(
    "v1/consul/templates", ConsulTemplateFileViewSet, basename="consul-templates"
)
urlpatterns = router.urls
