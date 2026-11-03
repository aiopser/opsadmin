from types import SimpleNamespace
import pytest

from apps.security.collector import parse_avd
from apps.automation.models import NotificationRecord
from apps.automation.views import NotificationRecordViewSet
from unittest.mock import patch


def test_unrated_official_avd_rows_are_not_invented_high_risk():
    html = '<table><tr><td><a href="/detail?id=AVD-2026-1">AVD-2026-1</a></td><td>Example</td><td>CWE-1</td><td>2026-10-27</td><td><button title="CVE">CVE</button><button title="PoC已公开">PoC</button></td></tr></table>'
    assert parse_avd(html)[0]["severity"] == "unknown"


@pytest.mark.django_db
def test_non_workflow_notification_records_are_scoped_to_their_actor(django_user_model):
    user = django_user_model.objects.create_user(
        username="notice-reader", password="test-password"
    )
    other = django_user_model.objects.create_user(
        username="notice-other", password="test-password"
    )
    mine = NotificationRecord.objects.create(
        alert_key="security:mine", context={"delivery": {"actorId": user.pk}}
    )
    theirs = NotificationRecord.objects.create(
        alert_key="security:other", context={"delivery": {"actorId": other.pk}}
    )
    view = NotificationRecordViewSet()
    view.request = SimpleNamespace(user=user)
    assert mine.pk in set(view.get_queryset().values_list("pk", flat=True))
    assert theirs.pk not in set(view.get_queryset().values_list("pk", flat=True))


@pytest.mark.django_db
def test_jumpserver_automatic_changes_require_execution_permission(django_user_model):
    from apps.integrations.models import JumpServerConnection
    from apps.integrations.serializers import JumpServerConnectionSerializer

    owner = django_user_model.objects.create_user(username="jms-owner")
    editor = django_user_model.objects.create_user(username="jms-editor")
    row = JumpServerConnection.objects.create(
        name="managed",
        endpoint="https://jms.example.com",
        node_id="00000000-0000-0000-0000-000000000001",
        sync_interval_minutes=5,
        sync_actor=owner,
        selected_host_ids=[1],
    )
    serializer = JumpServerConnectionSerializer(
        row,
        data={"linux_platform": 2},
        partial=True,
        context={"request": SimpleNamespace(user=editor)},
    )
    with patch("common.auth.rbac.verify_permission", return_value=(False, "denied")):
        assert not serializer.is_valid()


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["automatic", "enrollment", "jumpserver"])
def test_offboarded_accounts_cannot_execute_background_work(django_user_model, kind):
    from rest_framework.exceptions import ValidationError
    from apps.consul.models import ConsulConnection
    from apps.monitoring.models import EnrollmentPolicy, MonitoringTarget
    from apps.monitoring.enrollment import actor_allowed
    from apps.monitoring.automatic import check_auto_actor
    from apps.integrations.models import JumpServerConnection
    from apps.integrations.services import authorized

    actor = django_user_model.objects.create_user(
        username="offboarded", is_superuser=True, job_status=False
    )
    if kind == "jumpserver":
        row = JumpServerConnection.objects.create(
            name="jms",
            endpoint="https://jms.example.com",
            node_id="00000000-0000-0000-0000-000000000001",
        )
        assert not authorized(actor, row)
    else:
        connection = ConsulConnection.objects.create(
            name="consul", endpoint="http://consul:8500"
        )
        row = (
            EnrollmentPolicy.objects.create(name="policy", connection=connection)
            if kind == "enrollment"
            else MonitoringTarget.objects.create(
                name="target", connection=connection, address="192.168.1.1"
            )
        )
        with pytest.raises(ValidationError):
            (actor_allowed if kind == "enrollment" else check_auto_actor)(row, actor)


def test_rbac_does_not_allow_offboarded_superusers_via_non_jwt_auth():
    from common.auth.rbac import verify_permission

    actor = SimpleNamespace(
        username="offboarded-reader",
        is_active=True,
        job_status=False,
        is_superuser=True,
    )
    assert verify_permission(actor, "/api/v1/monitoring/targets", "GET")[0] is False
