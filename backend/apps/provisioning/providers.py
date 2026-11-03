"""Read back only instance identities produced by this request."""
import json

from apps.cmdb.cloud import _aliyun_region, _tencent_region
from apps.cmdb.crypto import decrypt_secret
from .contracts import ProvisioningError


def read_instances(source, region, instance_ids):
    if (
        not source.is_active
        or region not in source.regions
        or not 1 <= len(instance_ids) <= 20
    ):
        raise ProvisioningError("云账号、地域或资源 ID 范围无效")
    credentials = json.loads(decrypt_secret(source.credentials_encrypted))
    collector = {"aliyun": _aliyun_region, "tencent": _tencent_region}.get(
        source.cloud_provider
    )
    if collector is None:
        raise ProvisioningError("当前云平台暂不支持资源交付")
    return list(collector(region, credentials, instance_ids=instance_ids))
