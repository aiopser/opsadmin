from rest_framework.routers import SimpleRouter

from .views import AuditEventViewSet


router = SimpleRouter(trailing_slash=False)
router.register(r"v1/audit/events", AuditEventViewSet, basename="audit-events")

urlpatterns = router.urls
