"""Regression coverage for permission changes and association replacement."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.cmdb.models import (
    AssetHost,
    HostGroup,
    HostGroupMembership,
    HostTag,
    HostTagBinding,
)
from apps.permission.models import Permission, Role
from apps.permission.services import CasbinEnforcerService, sync_casbin_rules
from common.auth.rbac import verify_permission


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def admin_client():
    admin = get_user_model().objects.create_superuser(username="relations-admin")
    client = APIClient()
    client.force_authenticate(admin)
    return client


@pytest.fixture
def existing_relations():
    host = AssetHost.objects.create(hostname="existing", internal_ip="10.30.1.1")
    other = AssetHost.objects.create(hostname="replacement", internal_ip="10.30.1.2")
    group = HostGroup.objects.create(name="existing")
    replacement_group = HostGroup.objects.create(name="replacement")
    tag = HostTag.objects.create(key="environment", value="existing")
    replacement_tag = HostTag.objects.create(key="environment", value="replacement")
    HostGroupMembership.objects.create(host=host, group=group)
    HostTagBinding.objects.create(host=host, tag=tag)
    return host, other, group, replacement_group, tag, replacement_tag


def test_disabling_role_revokes_api_access_after_policy_reload():
    user = get_user_model().objects.create_user(username="disabled-role-user")
    role = Role.objects.create(name="operator", code="review-operator")
    permission = Permission.objects.create(
        name="Delete host", code="review.host.delete", type="api",
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

    role.is_active = True
    role.save(update_fields=["is_active"])
    sync_casbin_rules()
    CasbinEnforcerService.reload()
    assert verify_permission(user, "/api/v1/cmdb/hosts/123", "DELETE")[0]


def test_another_process_policy_change_invalidates_cached_permissions():
    user = get_user_model().objects.create_user(username="stale-policy-user")
    role = Role.objects.create(name="stale-operator")
    permission = Permission.objects.create(name="Read", code="review.stale.read", type="api", path="/api/v1/review-stale", method="GET")
    role.permission.add(permission)
    user.role.add(role)
    sync_casbin_rules()
    assert verify_permission(user, "/api/v1/review-stale", "GET")[0]
    old_enforcer = CasbinEnforcerService._enforcer
    old_revision = CasbinEnforcerService._policy_revision
    role.is_active = False
    role.save(update_fields=["is_active"])
    # Emulate a second web process, which did not receive the local reload.
    CasbinEnforcerService._enforcer = old_enforcer
    CasbinEnforcerService._policy_revision = old_revision
    assert not verify_permission(user, "/api/v1/review-stale", "GET")[0]

def test_profile_put_updates_contact_fields_through_real_route():
    user = get_user_model().objects.create_user(username="self-profile")
    client = APIClient()
    client.force_authenticate(user)
    response = client.put("/api/v1/users/profile", {
        "nickname": "Updated", "mobile": "13800000000", "email": "updated@example.com",
    }, format="json")
    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert (user.name, user.phone, user.email) == (
        "Updated", "13800000000", "updated@example.com",
    )
    assert response.data["data"]["username"] == "self-profile"
    assert client.get("/api/v1/users/profile").status_code == 200


@pytest.mark.parametrize("field,value", [
    ("is_superuser", True), ("is_staff", True), ("role", []), ("roleIds", []),
    ("groups", []), ("user_permissions", []), ("username", "renamed"),
    ("department", None), ("deptId", None), ("is_active", False),
    ("job_status", False), ("status", 0), ("password", "new-password"),
])
def test_profile_put_rejects_non_profile_fields(field, value):
    user = get_user_model().objects.create_user(username="profile-boundary", name="Original")
    client = APIClient()
    client.force_authenticate(user)
    response = client.put("/api/v1/users/profile", {
        "nickname": "Must not save", field: value,
    }, format="json")
    assert response.status_code == 400, response.data
    user.refresh_from_db()
    assert user.name == "Original"
    assert user.username == "profile-boundary"
    assert not user.is_superuser and not user.is_staff
    assert user.is_active and user.job_status
    assert not user.role.exists()


def test_profile_put_requires_authentication():
    assert APIClient().put("/api/v1/users/profile", {}, format="json").status_code in (401, 403)


@pytest.mark.parametrize("field,bad_ids", [
    ("groupIds", ["invalid"]), ("groupIds", [999999]),
    ("groupIds", "1"), ("groupIds", [True]), ("groupIds", [0]),
    ("tagIds", ["invalid"]), ("tagIds", [999999]), ("tagIds", None),
])
def test_invalid_host_relations_preserve_groups_and_tags(admin_client, existing_relations, field, bad_ids):
    host, _, group, replacement_group, tag, replacement_tag = existing_relations
    payload = {"groupIds": [replacement_group.pk], "tagIds": [replacement_tag.pk], field: bad_ids}
    response = admin_client.post(f"/api/v1/cmdb/hosts/{host.pk}/relations", payload, format="json")
    assert response.status_code == 400, response.data
    assert list(host.group_memberships.values_list("group_id", flat=True)) == [group.pk]
    assert list(host.tag_bindings.values_list("tag_id", flat=True)) == [tag.pk]


@pytest.mark.parametrize("field", ["groupIds", "tagIds"])
def test_duplicate_host_relations_are_rejected_before_replacing(admin_client, existing_relations, field):
    host, _, group, replacement_group, tag, replacement_tag = existing_relations
    payload = {"groupIds": [replacement_group.pk], "tagIds": [replacement_tag.pk]}
    target_id = payload[field][0]
    payload[field] = [target_id, str(target_id)]
    response = admin_client.post(f"/api/v1/cmdb/hosts/{host.pk}/relations", payload, format="json")
    assert response.status_code == 400, response.data
    assert list(host.group_memberships.values_list("group_id", flat=True)) == [group.pk]
    assert list(host.tag_bindings.values_list("tag_id", flat=True)) == [tag.pk]


def test_host_relation_replacement_rolls_back_if_tag_write_fails(admin_client, existing_relations):
    host, _, group, replacement_group, tag, replacement_tag = existing_relations
    with patch("apps.cmdb.views.HostTagBinding.objects.bulk_create", side_effect=IntegrityError("write failed")):
        response = admin_client.post(f"/api/v1/cmdb/hosts/{host.pk}/relations", {
            "groupIds": [replacement_group.pk], "tagIds": [replacement_tag.pk],
        }, format="json")
    assert response.status_code >= 400
    assert list(host.group_memberships.values_list("group_id", flat=True)) == [group.pk]
    assert list(host.tag_bindings.values_list("tag_id", flat=True)) == [tag.pk]


def test_host_relations_can_be_replaced_and_explicitly_cleared(admin_client, existing_relations):
    host, _, _, replacement_group, _, replacement_tag = existing_relations
    url = f"/api/v1/cmdb/hosts/{host.pk}/relations"
    response = admin_client.post(url, {
        "groupIds": [str(replacement_group.pk)], "tagIds": [replacement_tag.pk],
    }, format="json")
    assert response.status_code == 200, response.data
    assert list(host.group_memberships.values_list("group_id", flat=True)) == [replacement_group.pk]
    assert list(host.tag_bindings.values_list("tag_id", flat=True)) == [replacement_tag.pk]
    response = admin_client.post(url, {"groupIds": [], "tagIds": []}, format="json")
    assert response.status_code == 200
    assert not host.group_memberships.exists() and not host.tag_bindings.exists()


@pytest.mark.parametrize("bad_ids", [["invalid"], [999999], "1", [True], [0], None])
def test_invalid_group_members_preserve_old_members(admin_client, existing_relations, bad_ids):
    host, _, group, _, _, _ = existing_relations
    response = admin_client.post(f"/api/v1/cmdb/host-groups/{group.pk}/members", {
        "hostIds": bad_ids,
    }, format="json")
    assert response.status_code == 400, response.data
    assert list(group.memberships.values_list("host_id", flat=True)) == [host.pk]


def test_duplicate_group_members_preserve_old_members(admin_client, existing_relations):
    host, other, group, _, _, _ = existing_relations
    response = admin_client.post(f"/api/v1/cmdb/host-groups/{group.pk}/members", {
        "hostIds": [other.pk, str(other.pk)],
    }, format="json")
    assert response.status_code == 400, response.data
    assert list(group.memberships.values_list("host_id", flat=True)) == [host.pk]


def test_group_member_replacement_rolls_back_on_write_failure(admin_client, existing_relations):
    host, other, group, _, _, _ = existing_relations
    with patch("apps.cmdb.views.HostGroupMembership.objects.bulk_create", side_effect=IntegrityError("write failed")):
        response = admin_client.post(f"/api/v1/cmdb/host-groups/{group.pk}/members", {
            "hostIds": [other.pk],
        }, format="json")
    assert response.status_code >= 400
    assert list(group.memberships.values_list("host_id", flat=True)) == [host.pk]


def test_group_members_can_be_replaced_and_explicitly_cleared(admin_client, existing_relations):
    _, other, group, _, _, _ = existing_relations
    url = f"/api/v1/cmdb/host-groups/{group.pk}/members"
    response = admin_client.post(url, {"hostIds": [str(other.pk)]}, format="json")
    assert response.status_code == 200, response.data
    assert list(group.memberships.values_list("host_id", flat=True)) == [other.pk]
    assert admin_client.post(url, {"hostIds": []}, format="json").status_code == 200
    assert not group.memberships.exists()
