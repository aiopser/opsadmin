import logging
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.cmdb.models import CredentialRef

from .adapters import DatabaseCredentialProvider
from .workflow.inventory import build_inventory


class WorkflowInventoryTests(SimpleTestCase):
    def test_builds_unique_safe_inventory_hostname(self):
        inventory = build_inventory(
            [
                {
                    "host_id": 7,
                    "hostname": "web 01",
                    "address": "192.0.2.10",
                    "port": 22,
                    "connection_type": "ssh",
                    "os_family": "linux",
                    "credential_ref_id": None,
                    "variables": {"ansible_user": "ops"},
                }
            ]
        )
        self.assertIn("web_01__7 ansible_host=192.0.2.10", inventory)
        self.assertIn('ansible_user="ops"', inventory)

    @patch("apps.ops.adapters.CredentialRef.objects.get")
    @patch.dict("apps.ops.adapters.os.environ", {}, clear=True)
    def test_missing_credential_environment_variable_is_explicit(self, get_credential):
        get_credential.return_value = CredentialRef(
            metadata={},
            secret_ref="env:MISSING_PASSWORD",
            type=CredentialRef.CredentialType.PASSWORD,
        )
        with self.assertRaisesRegex(ValueError, "is not configured"):
            DatabaseCredentialProvider().resolve(1)
