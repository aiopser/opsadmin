import json
import re

from django.core import signing
from django.core.cache import cache
from django.utils import timezone

from apps.cmdb.models import AssetSource
from apps.cmdb.crypto import decrypt_secret
from apps.cmdb.cloud_diagnostics import cloud_probe_error
from common.auth.rbac import verify_permission
from ..contracts import ProvisioningError, canonical_digest
from ..models import ProvisioningCredential, ResourceTemplateVersion
from .types import KINDS, CatalogQuery
from .policy import permitted, validate_selectors


def require(actor, path, method="GET"):
    if (
        not actor
        or not actor.is_active
        or not verify_permission(actor, path, method)[0]
    ):
        raise ProvisioningError("无资源目录查询权限")


def resolve_scope(actor, values, configuration):
    version = ResourceTemplateVersion.objects.select_related("template").get(
        pk=int(values["versionId"])
    )
    require(actor, f"/api/v1/provisioning/versions/{version.pk}")
    if configuration:
        require(actor, "/api/v1/provisioning/catalog/configuration")
        require(actor, f"/api/v1/provisioning/versions/{version.pk}", "PATCH")
        source = AssetSource.objects.get(pk=int(values["sourceId"]))
        require(actor, f"/api/v1/cmdb/asset-sources/{source.pk}")
    else:
        require(actor, "/api/v1/provisioning/catalog")
        credential = ProvisioningCredential.objects.select_related("source").get(
            pk=int(values["credentialId"]), is_active=True
        )
        require(actor, f"/api/v1/provisioning/credentials/{credential.pk}/use", "POST")
        source = credential.source
        if version.status != "published" or not version.template.is_active:
            raise ProvisioningError("模板未发布或已停用")
    if (
        not source.is_active
        or source.source_type != "cloud"
        or source.cloud_provider != version.template.provider
        or source.cloud_provider not in {"aliyun", "tencent"}
    ):
        raise ProvisioningError("云账号未启用或平台不一致")
    if values["region"] not in source.regions or values[
        "region"
    ] not in version.constraints.get("regions", []):
        raise ProvisioningError("地域超出授权范围")
    validate_selectors(version.constraints)
    if not configuration:
        allowed = (
            version.constraints.get("selectors", {}).get("sourceIds", [])
            if version.constraints.get("schemaVersion") == 2
            else [n.get("source_id") for n in version.constraints.get("networks", [])]
        )
        if source.pk not in allowed:
            raise ProvisioningError("云账号超出模板授权范围")
    return source, version


def parse_query(values):
    allowed = {
        "kind",
        "versionId",
        "credentialId",
        "sourceId",
        "region",
        "pageSize",
        "cursor",
        "zone",
        "vpcId",
        "instanceType",
        "imageId",
        "resourceId",
        "search",
        "refresh",
    }
    if set(values) - allowed or values.get("kind") not in KINDS:
        raise ProvisioningError("无效的资源目录查询")
    size = int(values.get("pageSize", 50))
    if not 1 <= size <= 100:
        raise ProvisioningError("每页数量必须为 1 至 100")
    fields = {
        key: str(values.get(key, ""))
        for key in ["region", "zone", "vpcId", "instanceType", "imageId", "resourceId"]
    }
    if (
        any(
            value and not re.fullmatch(r"[\w.-]{1,128}", value)
            for value in fields.values()
        )
        or not fields["region"]
    ):
        raise ProvisioningError("无效的资源标识")
    search = str(values.get("search", ""))
    if len(search) > 100:
        raise ProvisioningError("搜索内容过长")
    return CatalogQuery(
        values["kind"],
        fields["region"],
        size,
        fields["zone"],
        fields["vpcId"],
        fields["instanceType"],
        fields["imageId"],
        fields["resourceId"],
        search,
    )


def fetch_provider_page(source, query, token):
    from . import aliyun, tencent

    credentials = {}
    try:
        credentials = json.loads(decrypt_secret(source.credentials_encrypted))
        return {"aliyun": aliyun.fetch_page, "tencent": tencent.fetch_page}[
            source.cloud_provider
        ](credentials, query, token)
    except ProvisioningError:
        raise
    except Exception as exc:
        diagnostic = cloud_probe_error(exc, credentials)
        message = (
            diagnostic["message"]
            if diagnostic["category"] != "permission"
            else "资源目录查询权限不足"
        )
        raise ProvisioningError(
            f"{message}；目录 {query.kind}；错误码 {diagnostic['errorCode'] or '未返回'}；请求 ID {diagnostic['requestId'] or '未返回'}。{diagnostic['detail']}"
        ) from None


def list_catalog(actor, values, *, configuration=False, refresh=False):
    try:
        query = parse_query(values)
        source, version = resolve_scope(actor, values, configuration)
    except (
        KeyError,
        TypeError,
        ValueError,
        AssetSource.DoesNotExist,
        ResourceTemplateVersion.DoesNotExist,
        ProvisioningCredential.DoesNotExist,
    ) as exc:
        if isinstance(exc, ProvisioningError):
            raise
        raise ProvisioningError("目录参数或关联资源无效") from None
    if values.get("refresh", False) not in {False, True, "true", "false", "1", "0"}:
        raise ProvisioningError("无效的刷新参数")
    refresh = refresh or values.get("refresh") in {True, "true", "1"}
    binding = canonical_digest(
        {
            "actor": actor.pk,
            "source": source.pk,
            "credential": values.get("credentialId"),
            "revision": source.updated_at.isoformat(),
            "policy": version.constraints,
            "version": version.pk,
            "query": query.__dict__,
            "configuration": configuration,
        }
    )
    token = None
    cursor = values.get("cursor")
    if cursor:
        try:
            payload = signing.loads(cursor, salt="provisioning.catalog", max_age=600)
            if payload["binding"] != binding:
                raise signing.BadSignature()
            token = payload["next"]
        except (signing.BadSignature, KeyError, TypeError):
            raise ProvisioningError("目录游标无效或已过期，请重新读取") from None
    key = "provisioning:catalog:" + canonical_digest([binding, token])
    cached = None if refresh else cache.get(key)
    if cached is not None:
        return cached
    page = fetch_provider_page(source, query, token)
    rows = [
        row
        for row in page["items"]
        if (
            configuration
            or permitted(row, query.kind, version.constraints, source.pk, query.region)
        )
        and (
            not query.search
            or query.search.lower() in (row["id"] + row["name"]).lower()
        )
    ]
    result = {
        "items": [{k: v for k, v in row.items() if k != "_tags"} for row in rows],
        "hasMore": bool(page.get("next")),
        "nextCursor": signing.dumps(
            {"binding": binding, "next": page["next"]}, salt="provisioning.catalog"
        )
        if page.get("next")
        else None,
        "observedAt": timezone.now().isoformat(),
        "warnings": page.get("warnings", []),
    }
    cache.set(key, result, 30 if query.kind in {"availability", "quota"} else 120)
    return result
