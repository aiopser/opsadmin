from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import WorkerPoolViewSet

from .views import (
    CommandInterceptViewSet,
    EngineSettingsView,
    GatewayViewSet,
    HostRunResultViewSet,
    ModuleRunViewSet,
    NodeRunViewSet,
    NotifySettingsView,
    OpsWorkflowRunViewSet,
    PlaybookRunViewSet,
    QuickCommandRunViewSet,
    ScheduledJobViewSet,
    SecurityRuleViewSet,
    SecurityStatsView,
    DashboardStatsView,
    DashboardHealthView,
    DashboardRecentView,
    WorkflowRunViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register(
    r"v1/jobs/worker-pools", WorkerPoolViewSet, basename="jobs-worker-pools"
)
router.register(
    r"v1/tasks/runs",
    WorkflowRunViewSet,
    basename="task-runs",
)
router.register(
    r"v1/ops/runs",
    OpsWorkflowRunViewSet,
    basename="ops-runs",
)
router.register(
    r"v1/jobs/quick-commands/runs",
    QuickCommandRunViewSet,
    basename="jobs-quick-command-runs",
)
router.register(
    r"v1/jobs/scheduled-jobs", ScheduledJobViewSet, basename="jobs-scheduled-jobs"
)
router.register(r"v1/jobs/node-runs", NodeRunViewSet, basename="jobs-node-runs")
router.register(
    r"v1/jobs/host-results",
    HostRunResultViewSet,
    basename="jobs-host-results",
)
router.register(
    r"v1/jobs/security-rules",
    SecurityRuleViewSet,
    basename="jobs-security-rules",
)
router.register(
    r"v1/jobs/command-intercepts",
    CommandInterceptViewSet,
    basename="jobs-command-intercepts",
)
router.register(r"v1/jobs/gateways", GatewayViewSet, basename="jobs-gateways")
router.register(
    r"v1/jobs/playbook-runs",
    PlaybookRunViewSet,
    basename="jobs-playbook-runs",
)
router.register(r"v1/jobs/module-runs", ModuleRunViewSet, basename="jobs-module-runs")

urlpatterns = [
    path("v1/jobs/security/stats", SecurityStatsView.as_view()),
    path("v1/jobs/dashboard/stats", DashboardStatsView.as_view()),
    path("v1/jobs/dashboard/recent", DashboardRecentView.as_view()),
    path("v1/jobs/dashboard/health", DashboardHealthView.as_view()),
    path("v1/jobs/settings/engine", EngineSettingsView.as_view()),
    path("v1/jobs/settings/notify", NotifySettingsView.as_view()),
    *router.urls,
]
