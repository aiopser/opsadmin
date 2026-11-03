from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.audit import build_cmdb_audit_snapshot
from apps.cmdb.serializers import AssetHostSerializer
from apps.cmdb.services import collect_group_tree_ids, resolve_group_host_ids
from apps.cmdb.sync_preview import preview_asset_sync
from apps.cmdb.tasks import sync_asset_source
from apps.cmdb.models import (
    AssetHost,
    AssetSource,
    AssetSyncRecord,
    CredentialRef,
    HostGroup,
)
from apps.audit_center.models import DomainAuditEvent
from apps.jobs.models import Gateway


class CMDBModelTests(TestCase):
    def test_cloud_type_repair_does_not_reclassify_manual_hosts(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps

        source = AssetSource.objects.create(
            code="repair-aliyun", name="Aliyun", source_type="cloud", cloud_provider="aliyun",
        )
        cloud = AssetHost.objects.create(
            hostname="ecs", internal_ip="10.0.0.1", asset_source=source,
            source_type="cloud", source_id="i-ecs", asset_type="server",
        )
        manual = AssetHost.objects.create(hostname="physical", internal_ip="10.0.0.2", asset_type="server")
        migration = import_module("apps.cmdb.migrations.0012_fix_public_cloud_asset_types")
        editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
        migration.repair_public_cloud_types(apps, editor)
        migration.repair_public_cloud_types(apps, editor)
        cloud.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(cloud.asset_type, "cloud_instance")
        self.assertEqual(manual.asset_type, "server")

    def test_public_cloud_sync_classifies_new_and_existing_instances(self):
        for provider in ("aliyun", "tencent"):
            source = AssetSource.objects.create(
                code=f"type-{provider}", name=provider, source_type="cloud",
                cloud_provider=provider,
            )
            host = AssetHost.objects.create(
                hostname=f"old-{provider}", internal_ip="10.0.0.1", asset_source=source,
                source_id="existing", asset_type="server", owner_team="operations",
            )
            record = AssetSyncRecord.objects.create(source=source, payload=[
                {"source_id": "existing", "hostname": f"old-{provider}", "internal_ip": "10.0.0.1", "cpu_cores": 4, "memory_mb": 8192, "system_disk_gb": 40, "data_disk_gb": 100, "region": "test-region"},
                {"source_id": "new", "hostname": f"new-{provider}", "internal_ip": "10.0.0.2", "cpu_cores": 2, "memory_mb": 4096, "system_disk_gb": 50, "region": "test-region"},
            ], total_count=2)
            sync_asset_source(record.pk)
            host.refresh_from_db()
            self.assertEqual(host.asset_type, "cloud_instance")
            self.assertEqual(host.owner_team, "operations")
            self.assertEqual((host.cpu_cores, host.memory_mb, host.system_disk_gb, host.data_disk_gb, host.region), (4, 8192, 40, 100, "test-region"))
            new_host = AssetHost.objects.get(asset_source=source, source_id="new")
            self.assertEqual((new_host.cpu_cores, new_host.memory_mb, new_host.system_disk_gb, new_host.region), (2, 4096, 50, "test-region"))
            self.assertEqual(AssetHost.objects.get(asset_source=source, source_id="new").asset_type, "cloud_instance")

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
                    "internal_ip": "10.0.0.11",
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

    def test_asset_source_sync_reports_partial_success(self):
        source = AssetSource.objects.create(
            code="partial-source",
            name="Partial Source",
            source_type=AssetSource.SourceType.EXTERNAL_CMDB,
        )
        record = AssetSyncRecord.objects.create(
            source=source,
            payload=[
                {"id": "host-1", "hostname": "web01", "internal_ip": "10.0.0.11"},
                {"id": "host-2", "hostname": "missing-ip"},
            ],
            total_count=2,
        )

        sync_asset_source(record.id)
        record.refresh_from_db()
        self.assertEqual(record.status, AssetSyncRecord.Status.PARTIAL)
        self.assertEqual((record.created_count, record.skipped_count), (1, 1))

    def test_asset_sync_preview_is_read_only_and_detects_duplicates(self):
        source = AssetSource.objects.create(
            code="preview-source", name="Preview", source_type=AssetSource.SourceType.CLOUD
        )
        AssetHost.objects.create(
            hostname="existing", internal_ip="10.0.0.1",
            asset_source=source, source_id="cloud-1",
        )
        preview = preview_asset_sync(source, [
            {"id": "cloud-1", "hostname": "existing", "internal_ip": "10.0.0.1"},
            {"id": "cloud-2", "hostname": "new", "internal_ip": "10.0.0.2"},
            {"id": "cloud-2", "hostname": "duplicate", "internal_ip": "10.0.0.3"},
            {"hostname": "unidentified", "internal_ip": "10.0.0.4"},
        ])
        self.assertEqual((preview["create"], preview["update"], preview["unchanged"], preview["invalid"]), (1, 0, 1, 2))
        self.assertEqual(AssetHost.objects.count(), 1)

    def test_dynamic_group_resolves_active_hosts_from_match_rule(self):
        group = HostGroup.objects.create(
            name="Production Linux",
            group_type=HostGroup.GroupType.DYNAMIC,
            match_rule={"environment": "prod", "os_family": "linux"},
        )
        host = AssetHost.objects.create(
            hostname="web01",
            internal_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            environment="prod",
            connection_type=AssetHost.ConnectionType.SSH,
        )
        AssetHost.objects.create(
            hostname="test01",
            internal_ip="10.0.0.12",
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
            internal_ip="10.0.0.11",
            os_family=AssetHost.OSFamily.LINUX,
            asset_source=source,
            source_type=AssetHost.SourceType.MANUAL,
            source_id="legacy-web01",
            connection_type=AssetHost.ConnectionType.SSH,
        )

        self.assertEqual(host.asset_source, source)
        self.assertEqual(host.source_id, "legacy-web01")

    def test_collect_group_tree_ids_includes_all_descendants(self):
        root = HostGroup.objects.create(name="Root")
        mid = HostGroup.objects.create(name="Mid", parent=root)
        leaf = HostGroup.objects.create(name="Leaf", parent=mid)
        other = HostGroup.objects.create(name="Other")

        self.assertEqual(
            collect_group_tree_ids([root.id]), {root.id, mid.id, leaf.id}
        )
        self.assertEqual(collect_group_tree_ids([leaf.id]), {leaf.id})
        self.assertEqual(collect_group_tree_ids([other.id]), {other.id})

    def test_host_serializer_rejects_gateway_for_non_ssh_host(self):
        gateway = Gateway.objects.create(name="jump", address="10.0.0.1:22")
        serializer = AssetHostSerializer(
            data={
                "hostname": "win01",
                "internal_ip": "10.0.0.12",
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
            internal_ip="10.0.0.11",
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
            internal_ip="10.0.0.12",
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
            internal_ip="10.0.0.11",
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
                "internal_ip": "10.0.0.12",
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

    def test_vault_credential_creation_is_rejected(self):
        from apps.cmdb.views import CredentialRefViewSet

        request = APIRequestFactory().post(
            "/api/v1/cmdb/credential-refs",
            {
                "name": "vault-ref",
                "type": "vault_ref",
                "scope": "global",
                "secret_ref": "vault://secret/data/db",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = CredentialRefViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("not supported", str(response.data))
        self.assertFalse(
            CredentialRef.objects.filter(name="vault-ref").exists()
        )

    def test_env_reference_creation_is_rejected_when_disabled(self):
        from apps.cmdb.views import CredentialRefViewSet

        request = APIRequestFactory().post(
            "/api/v1/cmdb/credential-refs",
            {
                "name": "env-ref",
                "type": "password",
                "scope": "global",
                "secret_ref": "env:APP_DB_PASSWORD",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)
        response = CredentialRefViewSet.as_view({"post": "create"})(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn("disabled", str(response.data))
        self.assertFalse(
            CredentialRef.objects.filter(name="env-ref").exists()
        )
