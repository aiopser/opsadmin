from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from apps.cmdb.models import AssetHost, HostGroup, HostGroupMembership
from apps.consul.models import ConsulConnection
from apps.monitoring.models import EnrollmentPolicy, EnrollmentRun, MonitoringTarget
from apps.monitoring.enrollment import (
    preview_policy,
    enqueue_policy_run,
    execute_policy_run,
    dispatch_policies,
)


def test_preview_requires_asset_read_permission_before_loading_hosts(policy):
    def permission(actor, path, method):
        return (path != "/api/v1/cmdb/hosts", "denied")

    with patch(
        "apps.monitoring.enrollment.verify_permission", side_effect=permission
    ), patch(
        "apps.monitoring.enrollment.policy_snapshot", return_value={"digest": "example"}
    ) as snapshot:
        with pytest.raises(ValidationError, match="资产读取权限"):
            preview_policy(policy, policy.actor)
        snapshot.assert_not_called()


@pytest.fixture
def policy(db):
    actor = get_user_model().objects.create_superuser(
        username="policy-admin", password="test-password"
    )
    connection = ConsulConnection.objects.create(
        name="policy", endpoint="http://consul:8500"
    )
    group = HostGroup.objects.create(name="app")
    row = EnrollmentPolicy.objects.create(
        name="policy", connection=connection, group=group, scope="group", actor=actor
    )
    host = AssetHost.objects.create(
        hostname="a", internal_ip="192.168.20.1", os_family="linux"
    )
    HostGroupMembership.objects.create(host=host, group=group)
    return row


def test_group_policy_discovers_new_members_without_overwriting_existing(policy):
    preview = preview_policy(policy, policy.actor)
    run = enqueue_policy_run(policy.pk, policy.actor, preview["preview_token"])
    with patch("apps.monitoring.batch_import.publish_records"):
        execute_policy_run(run.pk)
    assert MonitoringTarget.objects.filter(enrollment_policy=policy).count() == 1
    second = AssetHost.objects.create(
        hostname="b", internal_ip="192.168.20.2", os_family="linux"
    )
    HostGroupMembership.objects.create(host=second, group=policy.group)
    preview = preview_policy(policy, policy.actor)
    assert preview["create_count"] == 1
    assert preview["existing_count"] == 1
    assert MonitoringTarget.objects.count() == 1


def test_changed_scope_invalidates_preview(policy):
    proof = preview_policy(policy, policy.actor)["preview_token"]
    HostGroupMembership.objects.all().delete()
    with pytest.raises(ValidationError):
        enqueue_policy_run(policy.pk, policy.actor, proof)


def test_revoked_policy_actor_never_creates_targets(policy):
    run = enqueue_policy_run(
        policy.pk, policy.actor, preview_policy(policy, policy.actor)["preview_token"]
    )
    actor = policy.actor
    actor.is_active = False
    actor.save()
    with patch("apps.monitoring.batch_import.publish_records") as publish:
        execute_policy_run(run.pk)
        publish.assert_not_called()
    run.refresh_from_db()
    assert run.status == "failed"
    assert not MonitoringTarget.objects.exists()


def test_rule_policy_requires_nonempty_known_rules(policy):
    policy.scope = "rule"
    policy.match_rule = {}
    with pytest.raises(ValidationError):
        preview_policy(policy, policy.actor)
    policy.match_rule = {"unknown": "anything"}
    with pytest.raises(ValidationError):
        preview_policy(policy, policy.actor)
