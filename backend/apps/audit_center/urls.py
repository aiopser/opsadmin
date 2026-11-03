from rest_framework.routers import SimpleRouter

from .views import AuditEventViewSet, LoginEventViewSet


router = SimpleRouter(trailing_slash=False)
router.register(r"v1/audit/events", AuditEventViewSet, basename="audit-events")
router.register(r"v1/audit/login-events", LoginEventViewSet, basename="audit-login-events")

urlpatterns = router.urls
