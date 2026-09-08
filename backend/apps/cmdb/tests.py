from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.audit import build_cmdb_audit_snapshot
from apps.cmdb.serializers import AssetHostSerializer, ServiceTreeNodeSerializer
from apps.cmdb.services import resolve_group_host_ids
from apps.cmdb.tasks import sync_asset_source
from apps.cmdb.models import (
    AssetHost,
    AssetSource,
    AssetSyncRecord,
    Business,
    CredentialRef,
    HostGroup,
    ServiceTreeNode,
)
from apps.audit_center.models import DomainAuditEvent
from apps.jobs.models import Gateway


class CMDBModelTests(TestCase):
    def test_asset_source_sync_upserts_hosts_and_records_counts(self):
        source = AssetSource.objects.create(
            code="external",
            name="External CMDB",
            source_type=AssetSource.SourceType.EXTERNAL_CMDB,
        )
        record = AssetSyncRecord.objects.create(
            source=source,
            payload=[
                {
                    "id": "ext-1",
                    "hostname": "web01",
                    "primary_ip": "10.0.0.11",
                    "os_family": "linux",
                    "connection_type": "ssh",
                }
            ],
            total_count=1,
        )

        result = sync_asset_source(record.id)
        record.refresh_from_db()

        self.assertEqual(result["created"], 1)
        self.assertEqual(record.status, AssetSyncRecord.Status.SUCCEEDED)
        self.assertTrue(
            AssetHost.objects.filter(asset_source=source, source_id="ext-1").exists()
        )

    def test_dynamic_group_resolves_active_hosts_from_match_rule(self):
        group = HostGroup.objects.create(
            name="Production Linux",
            group_type=HostGroup.GroupType.DYNAMIC,
            match_rule={"environment": "prod", "os_family": "linux"},
        )
        host = AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            environment="prod",
            connection_type=AssetHost.ConnectionType.SSH,
        )
        AssetHost.objects.create(
            hostname="test01",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            environment="test",
            connection_type=AssetHost.ConnectionType.SSH,
        )

        self.assertEqual(resolve_group_host_ids([group.id]), {host.id})

    def test_host_can_reference_asset_source_without_changing_legacy_source_fields(
        self,
    ):
        source = AssetSource.objects.create(
            code="manual",
            name="手工录入",
            source_type=AssetSource.SourceType.MANUAL,
        )
        host = AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            asset_source=source,
            source_type=AssetHost.SourceType.MANUAL,
            source_id="legacy-web01",
            connection_type=AssetHost.ConnectionType.SSH,
        )

        self.assertEqual(host.asset_source, source)
        self.assertEqual(host.source_id, "legacy-web01")

    def test_service_tree_hierarchy_can_be_attached_to_host(self):
        business = Business.objects.create(code="commerce", name="Commerce")
        environment = ServiceTreeNode.objects.create(
            business=business,
            code="prod",
            name="Production",
            node_type=ServiceTreeNode.NodeType.ENVIRONMENT,
        )
        region = ServiceTreeNode.objects.create(
            business=business,
            parent=environment,
            code="cn-east",
            name="China East",
            node_type=ServiceTreeNode.NodeType.REGION,
        )
        module = ServiceTreeNode.objects.create(
            business=business,
            parent=region,
            code="web",
            name="Web",
            node_type=ServiceTreeNode.NodeType.MODULE,
        )
        host = AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            service_node=module,
            connection_type=AssetHost.ConnectionType.SSH,
        )

        self.assertEqual(host.service_node, module)
        self.assertEqual(module.parent, region)

    def test_service_tree_serializer_rejects_invalid_parent_type(self):
        business = Business.objects.create(code="commerce", name="Commerce")
        environment = ServiceTreeNode.objects.create(
            business=business,
            code="prod",
            name="Production",
            node_type=ServiceTreeNode.NodeType.ENVIRONMENT,
        )
        serializer = ServiceTreeNodeSerializer(
            data={
                "business": business.id,
                "parent": environment.id,
                "code": "invalid",
                "name": "Invalid Environment",
                "node_type": ServiceTreeNode.NodeType.ENVIRONMENT,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("parent", serializer.errors)

    def test_host_serializer_rejects_inactive_service_tree_node(self):
        business = Business.objects.create(code="commerce", name="Commerce")
        node = ServiceTreeNode.objects.create(
            business=business,
            code="retired",
            name="Retired",
            node_type=ServiceTreeNode.NodeType.ENVIRONMENT,
            is_active=False,
        )
        serializer = AssetHostSerializer(
            data={
                "hostname": "web01",
                "primary_ip": "10.0.0.11",
                "os_family": AssetHost.OSFamily.LINUX,
                "service_node": node.id,
                "connection_type": AssetHost.ConnectionType.SSH,
                "connection_port": 22,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("service_node", serializer.errors)

    def test_host_serializer_rejects_gateway_for_non_ssh_host(self):
        gateway = Gateway.objects.create(name="jump", address="10.0.0.1:22")
        serializer = AssetHostSerializer(
            data={
                "hostname": "win01",
                "primary_ip": "10.0.0.12",
                "os_family": AssetHost.OSFamily.WINDOWS,
                "connection_type": AssetHost.ConnectionType.WINRM,
                "connection_port": 5986,
                "default_gateway": gateway.id,
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("default_gateway", serializer.errors)

    def test_host_config_summary(self):
        credential = CredentialRef.objects.create(
            name="Test Credential Ref",
            type=CredentialRef.CredentialType.PASSWORD,
            scope=CredentialRef.Scope.HOST,
            secret_ref="vault://ops/test",
        )
        host = AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            cpu_cores=2,
            memory_mb=4096,
            system_disk_gb=40,
            data_disk_gb=200,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
            credential_ref=credential,
        )

        self.assertEqual(host.config_summary(), "2C / 4G / 40G / 200G")
        self.assertEqual(credential.secret_ref, "vault://ops/test")


class CMDBAuditSnapshotTests(SimpleTestCase):
    def test_snapshot_uses_foreign_key_id_and_redacts_secret_ref(self):
        host = AssetHost(
            hostname="audit-web01",
            primary_ip="10.0.0.12",
            os_family=AssetHost.OSFamily.LINUX,
            connection_type=AssetHost.ConnectionType.SSH,
        )
        credential = CredentialRef(
            name="Audit credential",
            type=CredentialRef.CredentialType.PASSWORD,
            scope=CredentialRef.Scope.HOST,
            secret_ref="vault://ops/audit",
        )

        host_snapshot = build_cmdb_audit_snapshot(host)
        credential_snapshot = build_cmdb_audit_snapshot(credential)

        self.assertEqual(host_snapshot["hostname"], "audit-web01")
        self.assertEqual(credential_snapshot["secret_ref"], {"configured": True})


class CMDBApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            password="123456",
            email="admin@example.com",
            phone="13800000000",
        )

    def test_host_list_returns_config_summary(self):
        from apps.cmdb.views import AssetHostViewSet

        AssetHost.objects.create(
            hostname="web01",
            primary_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            cpu_cores=2,
            memory_mb=4096,
            system_disk_gb=40,
            data_disk_gb=200,
            connection_type=AssetHost.ConnectionType.SSH,
            connection_port=22,
        )
        factory = APIRequestFactory()
        request = factory.get("/api/v1/cmdb/hosts?pageNum=1&pageSize=10")
        force_authenticate(request, user=self.user)
        response = AssetHostViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"]["list"][0]["configSummary"],
            "2C / 4G / 40G / 200G",
        )

    def test_create_host_creates_domain_audit_event(self):
        from apps.cmdb.views import AssetHostViewSet

        request = APIRequestFactory().post(
            "/api/v1/cmdb/hosts",
            {
                "hostname": "audit-web01",
                "primary_ip": "10.0.0.12",
                "os_family": AssetHost.OSFamily.LINUX,
                "connection_type": AssetHost.ConnectionType.SSH,
                "connection_port": 22,
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = AssetHostViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 200)
        audit = DomainAuditEvent.objects.get(
            action="cmdb.host.create",
            resource_type="cmdb_host",
        )
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.after["hostname"], "audit-web01")
