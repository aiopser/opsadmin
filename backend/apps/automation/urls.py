from rest_framework.routers import SimpleRouter
from django.urls import path

from .views import (
    ApiEndpointViewSet,
    AutomationTemplateView,
    CommandAtomViewSet,
    CommandVersionViewSet,
    DingtalkConnectionTestView,
    DingtalkSettingsView,
    FeishuConnectionTestView,
    FeishuSettingsView,
    GitRepositoryViewSet,
    JenkinsServerViewSet,
    JenkinsBuildViewSet,
    JenkinsJobViewSet,
    NotificationChannelViewSet,
    NotificationEmailConnectionTestView,
    NotificationEmailSettingsView,
    NotificationEmailTestView,
    NotificationHistoryPurgeView,
    NotificationHistorySettingsView,
    NotificationRecordViewSet,
    NotificationTemplateViewSet,
    NodeResourceView,
    WecomConnectionTestView,
    WecomSettingsView,
    WorkflowEdgeViewSet,
    WorkflowNodeViewSet,
    WorkflowTemplateViewSet,
    WorkflowVersionViewSet,
)

router = SimpleRouter(trailing_slash=False)
router.register(
    r"v1/automation/commands",
    CommandAtomViewSet,
    basename="automation-commands",
)
router.register(
    r"v1/automation/command-versions",
    CommandVersionViewSet,
    basename="automation-command-versions",
)
router.register(
    r"v1/automation/workflows",
    WorkflowTemplateViewSet,
    basename="automation-workflows",
)
router.register(
    r"v1/automation/workflow-versions",
    WorkflowVersionViewSet,
    basename="automation-workflow-versions",
)
router.register(
    r"v1/automation/workflow-nodes",
    WorkflowNodeViewSet,
    basename="automation-workflow-nodes",
)
router.register(
    r"v1/automation/workflow-edges",
    WorkflowEdgeViewSet,
    basename="automation-workflow-edges",
)
router.register(
    r"v1/automation/api-endpoints",
    ApiEndpointViewSet,
    basename="automation-api-endpoints",
)
router.register(
    r"v1/automation/git-repositories",
    GitRepositoryViewSet,
    basename="automation-git-repositories",
)
router.register(
    r"v1/automation/jenkins-servers",
    JenkinsServerViewSet,
    basename="automation-jenkins-servers",
)
router.register(
    r"v1/automation/jenkins-jobs", JenkinsJobViewSet, basename="automation-jenkins-jobs"
)
router.register(
    r"v1/automation/jenkins-builds",
    JenkinsBuildViewSet,
    basename="automation-jenkins-builds",
)
router.register(
    r"v1/automation/notification-channels",
    NotificationChannelViewSet,
    basename="automation-notification-channels",
)
router.register(
    r"v1/automation/notification-templates",
    NotificationTemplateViewSet,
    basename="automation-notification-templates",
)
router.register(
    r"v1/automation/notification-records",
    NotificationRecordViewSet,
    basename="automation-notification-records",
)

urlpatterns = [
    path("v1/automation/templates", AutomationTemplateView.as_view()),
    path("v1/automation/node-resources", NodeResourceView.as_view()),
    path("v1/notifications/email-settings", NotificationEmailSettingsView.as_view()),
    path(
        "v1/notifications/email-settings/test-connection",
        NotificationEmailConnectionTestView.as_view(),
    ),
    path("v1/notifications/email-settings/test", NotificationEmailTestView.as_view()),
    path(
        "v1/notifications/history-settings",
        NotificationHistorySettingsView.as_view(),
    ),
    path(
        "v1/notifications/history-settings/purge",
        NotificationHistoryPurgeView.as_view(),
    ),
    path("v1/notifications/wecom-settings", WecomSettingsView.as_view()),
    path(
        "v1/notifications/wecom-settings/test-connection",
        WecomConnectionTestView.as_view(),
    ),
    path("v1/notifications/dingtalk-settings", DingtalkSettingsView.as_view()),
    path(
        "v1/notifications/dingtalk-settings/test-connection",
        DingtalkConnectionTestView.as_view(),
    ),
    path("v1/notifications/feishu-settings", FeishuSettingsView.as_view()),
    path(
        "v1/notifications/feishu-settings/test-connection",
        FeishuConnectionTestView.as_view(),
    ),
    *router.urls,
]
