"""Resource delivery must fail closed before invoking a cloud writer."""
from datetime import timedelta

import pytest
from django.utils import timezone


def test_plan_accepts_only_new_managed_instances():
    from apps.provisioning.contracts import summarize_plan

    plan = {
        "resource_changes": [
            {
                "address": "alicloud_instance.host[0]",
                "mode": "managed",
                "type": "alicloud_instance",
                "change": {"actions": ["create"]},
            }
        ]
    }
    assert summarize_plan(plan, "aliyun")[0]["action"] == "create"


@pytest.mark.parametrize(
    "actions", [["delete"], ["delete", "create"], ["update"], ["no-op"]]
)
def test_plan_refuses_non_create_operations(actions):
    from apps.provisioning.contracts import summarize_plan, ProvisioningError

    with pytest.raises(ProvisioningError):
        summarize_plan(
            {
                "resource_changes": [
                    {
                        "address": "x",
                        "mode": "managed",
                        "type": "alicloud_instance",
                        "change": {"actions": actions},
                    }
                ]
            },
            "aliyun",
        )


def test_inputs_refuse_unbounded_count_and_extra_terraform_fields():
    from apps.provisioning.contracts import validate_inputs, ProvisioningError

    with pytest.raises(ProvisioningError):
        validate_inputs({"count": 21}, "aliyun")
    with pytest.raises(ProvisioningError):
        validate_inputs({"count": 1, "command": "terraform destroy"}, "aliyun")


@pytest.fixture
def request_record(db):
    from django.contrib.auth import get_user_model
    from apps.cmdb.models import AssetSource
    from apps.provisioning.models import (
        ResourceTemplate,
        ResourceTemplateVersion,
        ProvisioningCredential,
        ProvisioningRequest,
    )

    user = get_user_model().objects.create_superuser(username="provision-owner")
    source = AssetSource.objects.create(
        code="provision-cloud",
        name="Cloud",
        source_type="cloud",
        cloud_provider="aliyun",
        regions=["cn-shanghai"],
    )
    template = ResourceTemplate.objects.create(name="ECS", provider="aliyun")
    version = ResourceTemplateVersion.objects.create(
        template=template,
        number=1,
        status="published",
        constraints={"regions": ["cn-shanghai"]},
    )
    credential = ProvisioningCredential.objects.create(
        source=source, name="Writer", encrypted_secret="encrypted", revision=1
    )
    return ProvisioningRequest.objects.create(
        name="web",
        created_by=user,
        version=version,
        credential=credential,
        region="cn-shanghai",
        parameters={"count": 1},
    )


def ready_plan(record):
    from apps.provisioning.models import ProvisioningPlan

    return ProvisioningPlan.objects.create(
        request=record,
        revision=record.revision,
        status="ready",
        digest="a" * 64,
        credential_revision=1,
        source_updated_at=record.credential.source.updated_at,
        expires_at=timezone.now() + timedelta(minutes=30),
        artifact_key="test",
    )


def test_applicant_cannot_approve_own_plan(request_record):
    from apps.provisioning.services import approve_plan
    from apps.provisioning.contracts import ProvisioningError

    plan = ready_plan(request_record)
    with pytest.raises(ProvisioningError, match="本人"):
        approve_plan(request_record.pk, request_record.created_by, plan.pk, plan.digest)


def test_changed_credential_invalidates_confirmation(request_record):
    from apps.provisioning.services import confirm_plan
    from apps.provisioning.contracts import ProvisioningError

    plan = ready_plan(request_record)
    request_record.credential.revision = 2
    request_record.credential.save()
    with pytest.raises(ProvisioningError, match="凭据"):
        confirm_plan(request_record.pk, request_record.created_by, plan.pk, plan.digest)


def test_expired_plan_cannot_be_confirmed(request_record):
    from apps.provisioning.services import confirm_plan
    from apps.provisioning.contracts import ProvisioningError

    plan = ready_plan(request_record)
    plan.expires_at = timezone.now() - timedelta(seconds=1)
    plan.save()
    with pytest.raises(ProvisioningError, match="过期"):
        confirm_plan(request_record.pk, request_record.created_by, plan.pk, plan.digest)


def test_published_version_is_immutable(request_record):
    from django.core.exceptions import ValidationError

    version = request_record.version
    version.constraints = {"regions": []}
    with pytest.raises(ValidationError):
        version.save()


def test_raw_secrets_never_appear_in_api(request_record):
    from apps.provisioning.serializers import CredentialSerializer

    data = CredentialSerializer(request_record.credential).data
    assert "encrypted_secret" not in data
    assert data["has_secret"] is True
