from django.test import SimpleTestCase

from .adapters import CredentialProvider
from .workflow.inventory import build_inventory


class WorkflowInventoryTests(SimpleTestCase):
    @staticmethod
    def _host(**overrides):
        host = {
            "host_id": 7,
            "hostname": "web 01",
            "address": "192.0.2.10",
            "port": 22,
            "connection_type": "ssh",
            "os_family": "linux",
            "credential_ref_id": None,
            "variables": {"ansible_user": "ops"},
        }
        host.update(overrides)
        return host

    def test_builds_unique_safe_inventory_hostname(self):
        inventory = build_inventory(
            [self._host()],
            credential_provider=CredentialProvider(),
        )
        self.assertIn("web_01__7 ansible_host=192.0.2.10", inventory)
        self.assertIn('ansible_user="ops"', inventory)

    def test_credential_variables_come_from_the_injected_provider(self):
        class StaticProvider(CredentialProvider):
            def resolve(self, credential_id):
                assert credential_id == 42
                return {"ansible_user": "cred-user", "ansible_password": "s3cret"}

        inventory = build_inventory(
            [self._host(credential_ref_id=42)],
            credential_provider=StaticProvider(),
        )
        self.assertIn('ansible_user="cred-user"', inventory)
        self.assertIn('ansible_password="s3cret"', inventory)
