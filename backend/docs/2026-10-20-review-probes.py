"""Review regression probes: use --ds=devops.test_full_settings only.

All cloud calls are mocked. The assertions describe the expected safe behavior
and currently fail to demonstrate the reviewed defects.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.cmdb.models import AssetHost, HostGroup, HostGroupMembership, HostTag, HostTagBinding
from apps.cmdb.views import AssetHostViewSet, HostGroupViewSet
from apps.permission.models import Permission, Role
from apps.permission.services import CasbinEnforcerService, sync_casbin_rules
from common.auth.rbac import verify_permission


@pytest.mark.django_db(transaction=True)
def test_disabled_role_should_revoke_api_permissions():
    user = get_user_model().objects.create_user(username="review-disabled-role")
    role = Role.objects.create(name="review-disabled", code="review-disabled")
    permission = Permission.objects.create(
        name="Review delete", code="review.host.delete", type="api",
        path="/api/v1/cmdb/hosts/:id", method="DELETE",
    )
    role.permission.add(permission)
    user.role.add(role)
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    assert verify_permission(user, "/api/v1/cmdb/hosts/123", "DELETE")[0]
    role.is_active = False
    role.save(update_fields=["is_active"])
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    assert not verify_permission(user, "/api/v1/cmdb/hosts/123", "DELETE")[0]


@pytest.mark.django_db(transaction=True)
def test_invalid_relations_should_preserve_existing_groups_and_tags():
    admin = get_user_model().objects.create_superuser(username="review-relations-admin")
    host = AssetHost.objects.create(hostname="review-host", internal_ip="10.30.1.1")
    group = HostGroup.objects.create(name="review-group")
    tag = HostTag.objects.create(key="review", value="old")
    HostGroupMembership.objects.create(host=host, group=group)
    HostTagBinding.objects.create(host=host, tag=tag)
    request = APIRequestFactory().post(
        "/relations", {"groupIds": ["not-an-id"], "tagIds": []}, format="json"
    )
    force_authenticate(request, user=admin)
    response = AssetHostViewSet.as_view({"post": "relations"})(request, pk=host.pk)
    assert response.status_code >= 400
    assert HostGroupMembership.objects.filter(host=host, group=group).exists()
    assert HostTagBinding.objects.filter(host=host, tag=tag).exists()


@pytest.mark.django_db(transaction=True)
def test_duplicate_members_should_preserve_existing_group_members():
    admin = get_user_model().objects.create_superuser(username="review-members-admin")
    old = AssetHost.objects.create(hostname="review-old", internal_ip="10.30.1.2")
    new = AssetHost.objects.create(hostname="review-new", internal_ip="10.30.1.3")
    group = HostGroup.objects.create(name="review-member-group")
    HostGroupMembership.objects.create(host=old, group=group)
    request = APIRequestFactory().post(
        "/members", {"hostIds": [new.pk, new.pk]}, format="json"
    )
    force_authenticate(request, user=admin)
    response = HostGroupViewSet.as_view({"post": "members"})(request, pk=group.pk)
    assert response.status_code >= 400
    remaining = list(
        HostGroupMembership.objects.filter(group=group).values_list("host_id", flat=True)
    )
    assert remaining == [old.pk]


def test_aliyun_eip_should_be_imported_as_external_ip():
    from apps.cmdb.cloud import _aliyun_region

    item = SimpleNamespace(
        instance_id="i-review", instance_name="review", host_name="review",
        vpc_attributes=SimpleNamespace(
            private_ip_address=SimpleNamespace(ip_address=["10.30.1.4"])
        ),
        inner_ip_address=None, public_ip_address=SimpleNamespace(ip_address=[]),
        eip_address=SimpleNamespace(ip_address="203.0.113.51"),
        osname="Linux", ostype="linux", instance_type="ecs.test",
    )
    body = SimpleNamespace(instances=SimpleNamespace(instance=[item]), next_token=None)
    with patch("apps.cmdb.cloud._aliyun_disks", return_value={}), patch(
        "alibabacloud_ecs20140526.client.Client"
    ) as client:
        client.return_value.describe_instances.return_value = SimpleNamespace(body=body)
        row = list(_aliyun_region(
            "cn-shanghai", {"access_key_id": "id", "access_key_secret": "secret"}
        ))[0]
    assert row["external_ip"] == "203.0.113.51"
