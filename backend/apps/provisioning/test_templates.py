import pytest
from .templates import template_configuration
from .contracts import ProvisioningError


@pytest.mark.parametrize("provider", ["aliyun", "tencent"])
def test_template_only_creates_private_instances_and_validates_network(provider):
    template = template_configuration(provider, "1.2.3", "1.9.8")
    assert "count" not in template["variable"]
    resources = template["resource"]
    assert len(resources) == 1
    instance = next(iter(resources.values()))["host"]
    assert instance["lifecycle"]["prevent_destroy"] is True
    assert instance["lifecycle"]["precondition"]
    assert template["data"]
    assert "provisioner" not in instance


def test_template_requires_explicit_provider_version():
    with pytest.raises(ProvisioningError):
        template_configuration("aliyun", "latest", "1.9.8")


def test_provisioning_notification_catalog_is_discoverable():
    from apps.automation.notification_preview import notification_catalog

    catalog = notification_catalog("provisioning")
    assert catalog["sampleContext"]["delivery"]["requestId"] == 1001
    assert "{{ delivery.message }}" in [
        item["expression"] for item in catalog["variables"]
    ]
