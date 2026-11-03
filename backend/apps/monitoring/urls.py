from rest_framework.routers import SimpleRouter
from .enrollment_views import EnrollmentPolicyViewSet, EnrollmentRunViewSet
from .views import (
    MonitoringTargetViewSet,
    SyncRecordViewSet,
    MonitoringConnectionViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register(
    "v1/monitoring/enrollment-policies",
    EnrollmentPolicyViewSet,
    basename="monitoring-enrollment-policies",
)
router.register(
    "v1/monitoring/enrollment-runs",
    EnrollmentRunViewSet,
    basename="monitoring-enrollment-runs",
)
router.register(
    "v1/monitoring/targets", MonitoringTargetViewSet, basename="monitoring-targets"
)
router.register(
    "v1/monitoring/sync-records", SyncRecordViewSet, basename="monitoring-sync-records"
)
router.register(
    "v1/monitoring/connections",
    MonitoringConnectionViewSet,
    basename="monitoring-config",
)
urlpatterns = router.urls
