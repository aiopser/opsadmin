from django.test import SimpleTestCase

from .services import _resolve_domain
from .views import AuditEventViewSet


class AuditCenterTests(SimpleTestCase):
    def test_audit_api_is_read_only(self):
        self.assertEqual(
            AuditEventViewSet.http_method_names,
            ["get", "head", "options"],
        )

    def test_domain_is_resolved_from_action_prefix(self):
        self.assertEqual(_resolve_domain("cmdb.host.update", "host", 1), "cmdb")
        self.assertEqual(
            _resolve_domain("automation.command.create", "command", 1),
            "automation",
        )
        self.assertEqual(
            _resolve_domain("module_run.create", "workflow_run", None),
            "ops",
        )
