from rest_framework.routers import SimpleRouter
from .views import JumpServerConnectionViewSet

router = SimpleRouter(trailing_slash=False)
router.register(
    "v1/integrations/jumpserver/connections",
    JumpServerConnectionViewSet,
    basename="jumpserver-connections",
)
urlpatterns = router.urls
