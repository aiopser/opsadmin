"""Private-cloud connectors are verified with mocked API responses only."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from apps.cmdb.cloud import _openstack, _pve, _vmware, collect_cloud_assets
from apps.cmdb.crypto import encrypt_secret
from apps.cmdb.models import AssetSource
from apps.cmdb.serializers import AssetSourceSerializer


@pytest.mark.django_db
@pytest.mark.parametrize("provider,extra", [
    ("vmware", {}),
    ("openstack", {"regions": ["RegionOne"], "metadata": {"project_name": "ops"}}),
    ("pve", {}),
])
def test_private_cloud_credentials_are_encrypted(provider, extra):
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        serializer = AssetSourceSerializer(data={
            "code": f"{provider}-test", "name": provider, "source_type": "cloud",
            "cloud_provider": provider, "endpoint": "https://cloud.internal",
            "access_key_id": "read-only", "access_key_secret": "private-secret",
            **extra,
        })
        assert serializer.is_valid(), serializer.errors
        source = serializer.save()
        rendered = json.dumps(AssetSourceSerializer(source).data)
        assert source.credentials_encrypted
        assert "private-secret" not in rendered
        assert "read-only" not in rendered


@pytest.mark.django_db
@pytest.mark.parametrize("endpoint", ["http://pve.internal:8006", "https://[broken", "https://pve.internal:bad"])
def test_private_cloud_rejects_invalid_endpoint(endpoint):
    serializer = AssetSourceSerializer(data={
        "code": "pve-http", "name": "PVE", "source_type": "cloud",
        "cloud_provider": "pve", "endpoint": endpoint,
        "access_key_id": "user@pve!reader", "access_key_secret": "secret",
    })
    assert not serializer.is_valid()


def test_vmware_maps_guest_ip_and_closes_session():
    source = SimpleNamespace(endpoint="https://vcenter.internal")
    responses = [
        ("session-id", {}),
        ([{"vm": "vm-1", "name": "web", "guest_OS": "RHEL_9_64"}], {}),
        ([{"ip": {"ip_addresses": [{"ip_address": "127.0.0.1"}, {"ip_address": "10.0.0.4"}]}}], {}),
        (None, {}),
    ]
    with patch("apps.cmdb.cloud._request_json", side_effect=responses) as request:
        assets = list(_vmware(source, {"access_key_id": "user", "access_key_secret": "secret"}))
    assert assets[0]["internal_ip"] == "10.0.0.4"
    assert assets[0]["source_id"] == "vm-1"
    assert request.call_args.kwargs["method"] == "DELETE"


def test_openstack_uses_catalog_and_maps_fixed_and_floating_ip():
    source = SimpleNamespace(
        endpoint="https://keystone.internal/v3",
        metadata={"project_name": "ops", "user_domain_name": "Default"},
    )
    auth = ({"token": {"catalog": [{"type": "compute", "endpoints": [
        {"interface": "internal", "region": "RegionOne", "url": "https://nova.internal/v2.1"}
    ]}]}}, {"X-Subject-Token": "token"})
    servers = ({"servers": [{
        "id": "vm-1", "name": "api", "addresses": {"net": [
            {"addr": "10.0.0.5", "OS-EXT-IPS:type": "fixed"},
            {"addr": "198.51.100.5", "OS-EXT-IPS:type": "floating"},
        ]},
    }]}, {})
    with patch("apps.cmdb.cloud._request_json", side_effect=[auth, servers]) as request:
        assets = list(_openstack(source, {"access_key_id": "user", "access_key_secret": "secret"}, "RegionOne"))
    assert assets[0]["internal_ip"] == "10.0.0.5"
    assert assets[0]["external_ip"] == "198.51.100.5"
    assert request.call_args.args[0].startswith("https://nova.internal/")


def test_pve_maps_qemu_guest_and_lxc_static_ip():
    source = SimpleNamespace(endpoint="https://pve.internal:8006")
    cluster = ({"data": [
        {"type": "qemu", "node": "n1", "vmid": 100, "name": "web"},
        {"type": "lxc", "node": "n1", "vmid": 101, "name": "cache"},
    ]}, {})
    qemu = ({"data": {"result": [{"ip-addresses": [{"ip-address": "10.0.0.6"}]}]}}, {})
    lxc = ({"data": {"net0": "name=eth0,bridge=vmbr0,ip=10.0.0.7/24"}}, {})
    with patch("apps.cmdb.cloud._request_json", side_effect=[cluster, qemu, lxc]):
        assets = list(_pve(source, {"access_key_id": "user@pve!reader", "access_key_secret": "secret"}))
    assert [item["internal_ip"] for item in assets] == ["10.0.0.6", "10.0.0.7"]
    assert [item["source_id"] for item in assets] == ["qemu:100", "lxc:101"]


@pytest.mark.django_db
def test_private_cloud_collection_uses_single_endpoint_not_regions():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        source = AssetSource.objects.create(
            code="vmware-collect", name="VMware", source_type="cloud",
            cloud_provider="vmware", endpoint="https://vcenter.internal",
            credentials_encrypted=encrypt_secret(json.dumps({
                "access_key_id": "user", "access_key_secret": "secret",
            })),
        )
        with patch("apps.cmdb.cloud._vmware", return_value=iter([{"source_id": "vm-1"}])) as collect:
            assert collect_cloud_assets(source) == [{"source_id": "vm-1"}]
        collect.assert_called_once()
