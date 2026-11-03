from unittest.mock import patch

import pytest
from django.core.cache import cache

from .test_contract import request_record as base_request_record
from .contracts import ProvisioningError


@pytest.fixture
def request_record(base_request_record):
    from .models import ResourceTemplateVersion

    record = base_request_record
    record.version = ResourceTemplateVersion.objects.create(
        template=record.version.template,
        number=2,
        status="published",
        constraints={
            "regions": [record.region],
            "networks": [
                {
                    "source_id": record.credential.source_id,
                    "region": record.region,
                    "zone": "cn-shanghai-a",
                }
            ],
        },
    )
    record.save()
    return record


def test_catalog_checks_permission_before_cached_result(request_record):
    from .catalog.service import list_catalog

    record = request_record
    cache.clear()
    query = {
        "kind": "zones",
        "versionId": record.version_id,
        "credentialId": record.credential_id,
        "region": record.region,
    }
    with patch(
        "apps.provisioning.catalog.service.fetch_provider_page",
        return_value={"items": [], "next": None},
    ):
        assert list_catalog(record.created_by, query)["items"] == []
    with patch(
        "apps.provisioning.catalog.service.verify_permission",
        return_value=(False, "denied"),
    ):
        with pytest.raises(ProvisioningError, match="权限"):
            list_catalog(record.created_by, query)


@pytest.mark.parametrize(
    "override",
    [
        {"kind": "write"},
        {"mode": "configuration"},
        {"cursor": "forged"},
        {"pageSize": 101},
        {"region": "cn-beijing"},
    ],
)
def test_catalog_refuses_invalid_or_widened_query(request_record, override):
    from .catalog.service import list_catalog

    query = {
        "kind": "zones",
        "versionId": request_record.version_id,
        "credentialId": request_record.credential_id,
        "region": request_record.region,
        **override,
    }
    with pytest.raises(ProvisioningError):
        list_catalog(request_record.created_by, query)


def test_filtered_page_preserves_cursor(request_record):
    from .catalog.service import list_catalog

    record = request_record
    cache.clear()
    query = {
        "kind": "images",
        "versionId": record.version_id,
        "credentialId": record.credential_id,
        "region": record.region,
    }
    with patch(
        "apps.provisioning.catalog.service.fetch_provider_page",
        return_value={
            "items": [{"id": "forbidden", "name": "hidden", "attributes": {}}],
            "next": "page2",
        },
    ):
        page = list_catalog(record.created_by, query)
    assert page["items"] == []
    assert page["hasMore"] and page["nextCursor"]


def test_unknown_capacity_is_not_zero():
    from .catalog.types import item

    assert item("subnet", "name", remaining=None)["attributes"]["remaining"] is None


def test_explicit_reload_bypasses_cache(request_record):
    from .catalog.service import list_catalog

    cache.clear()
    record = request_record
    query = {
        "kind": "zones",
        "versionId": record.version_id,
        "credentialId": record.credential_id,
        "region": record.region,
    }
    with patch(
        "apps.provisioning.catalog.service.fetch_provider_page",
        return_value={"items": [], "next": None},
    ) as fetch:
        list_catalog(record.created_by, query)
        list_catalog(record.created_by, query)
        list_catalog(record.created_by, {**query, "refresh": "true"})
    assert fetch.call_count == 2


def test_cloud_diagnostic_redacts_read_credentials(request_record):
    from .catalog.service import fetch_provider_page
    from .catalog.types import CatalogQuery

    class Denied(Exception):
        code = "AccessDenied"
        requestId = "request-one"
        message = "denied secret-value"

    with patch(
        "apps.provisioning.catalog.service.decrypt_secret",
        return_value='{"access_key_id":"id-value","access_key_secret":"secret-value"}',
    ), patch("apps.provisioning.catalog.aliyun.fetch_page", side_effect=Denied()):
        with pytest.raises(ProvisioningError) as error:
            fetch_provider_page(
                request_record.credential.source,
                CatalogQuery("subnets", request_record.region),
                None,
            )
    assert "secret-value" not in str(error.value)
    assert "request-one" in str(error.value)
    assert "subnets" in str(error.value)
