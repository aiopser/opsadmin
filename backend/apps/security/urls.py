from rest_framework.routers import SimpleRouter
from .views import AdvisoryViewSet, CollectionViewSet, SubscriptionViewSet

router = SimpleRouter(trailing_slash=False)
router.register(
    "v1/security/subscriptions", SubscriptionViewSet, basename="security-subscription"
)
router.register("v1/security/advisories", AdvisoryViewSet, basename="security-advisory")
router.register(
    "v1/security/collections", CollectionViewSet, basename="security-collection"
)
urlpatterns = router.urls
