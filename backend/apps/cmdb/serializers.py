import json
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .schema_serializers import AssetSourceCapabilitiesSerializer

from common.api.serializers import StandardModelSerializer

from .credentials import check_secret_ref
from .crypto import decrypt_secret, encrypt_secret, mask_secret
from .models import (
    AssetHost,
    AssetProbe,
    AssetSource,
    AssetSyncRecord,
    CredentialRef,
    HostGroup,
    HostTag,
)


class AssetSourceSerializer(StandardModelSerializer):
    capabilities = serializers.SerializerMethodField()
    access_key_id = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    access_key_secret = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    has_credentials = serializers.SerializerMethodField()
    masked_access_key_id = serializers.SerializerMethodField()

    class Meta:
        model = AssetSource
        fields = (
            "id",
            "code",
            "name",
            "source_type",
            "endpoint",
            "description",
            "is_active",
            "metadata",
            "cloud_provider",
            "regions",
            "has_credentials",
            "masked_access_key_id",
            "access_key_id",
            "access_key_secret",
            "last_synced_at",
            "created_at",
            "updated_at",
            "sync_interval_minutes",
            "last_sync_attempt_at",
            "sync_failure_alert",
            "capabilities",
            "sync_actor",
        )
        read_only_fields = ("last_synced_at", "last_sync_attempt_at", "sync_actor")

    @extend_schema_field(AssetSourceCapabilitiesSerializer)
    def get_capabilities(self, instance):
        from .cloud_capabilities import CAPABILITIES

        return {
            "fields": CAPABILITIES.get(instance.cloud_provider, []),
            "maxAssets": 1000,
            "scope": "仅配置区域及当前凭据可见范围；未返回的主机不会删除或停用",
        }

    def validate_sync_interval_minutes(self, value):
        if value != 0 and not 5 <= value <= 10080:
            raise serializers.ValidationError("周期同步间隔须为 5 至 10080 分钟，0 表示关闭")
        return value

    def validate_sync_failure_alert(self, value):
        from apps.automation.failure_alerts import validate_failure_alert

        return validate_failure_alert(value) or {}

    def get_has_credentials(self, instance) -> bool:
        return bool(instance.credentials_encrypted)

    def get_masked_access_key_id(self, instance) -> str:
        if not instance.credentials_encrypted:
            return ""
        try:
            key_id = json.loads(decrypt_secret(instance.credentials_encrypted))[
                "access_key_id"
            ]
            return f"****{key_id[-4:]}" if len(key_id) > 8 else "****"
        except Exception:
            return "已配置（无法读取，请重新配置凭据）"

    def validate_regions(self, value):
        provider = self.initial_data.get(
            "cloud_provider", getattr(self.instance, "cloud_provider", "")
        )
        pattern = (
            r"[A-Za-z0-9_.-]{1,64}"
            if provider == AssetSource.CloudProvider.OPENSTACK
            else r"[a-z0-9-]{2,40}"
        )
        if not isinstance(value, list) or not all(
            isinstance(region, str) and re.fullmatch(pattern, region)
            for region in value
        ):
            raise serializers.ValidationError("区域必须是有效区域 ID 列表")
        if len(value) != len(set(value)) or len(value) > 30:
            raise serializers.ValidationError("区域不可重复，且最多 30 个")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        source_type = attrs.get(
            "source_type", getattr(self.instance, "source_type", None)
        )
        if self.instance and self.instance.hosts.exists():
            if (
                source_type != self.instance.source_type
                or attrs.get("cloud_provider", self.instance.cloud_provider)
                != self.instance.cloud_provider
            ):
                raise serializers.ValidationError("已有资产的来源不可更换类型或云平台，请新建云账号")
        interval = attrs.get(
            "sync_interval_minutes", getattr(self.instance, "sync_interval_minutes", 0)
        )
        if interval and source_type != "cloud":
            raise serializers.ValidationError("仅云账号支持周期同步")
        request = self.context.get("request")
        if interval and request is not None:
            from common.auth.rbac import verify_permission

            allowed, _ = verify_permission(
                request.user,
                f"/api/v1/cmdb/asset-sources/{getattr(self.instance, 'pk', 0)}/sync-cloud",
                "POST",
            )
            if not allowed:
                raise serializers.ValidationError("开启或修改周期同步需要资产同步权限")
            attrs["sync_actor"] = request.user
        key_id = attrs.get("access_key_id", "")
        key_secret = attrs.get("access_key_secret", "")
        if bool(key_id) != bool(key_secret):
            raise serializers.ValidationError("AccessKey ID 和 Secret 必须同时填写")
        if source_type == AssetSource.SourceType.CLOUD:
            provider = attrs.get(
                "cloud_provider", getattr(self.instance, "cloud_provider", "")
            )
            regions = attrs.get("regions", getattr(self.instance, "regions", []))
            endpoint = attrs.get("endpoint", getattr(self.instance, "endpoint", ""))
            metadata = attrs.get("metadata", getattr(self.instance, "metadata", {}))
            has_stored = bool(getattr(self.instance, "credentials_encrypted", ""))
            public = {
                AssetSource.CloudProvider.ALIYUN,
                AssetSource.CloudProvider.TENCENT,
            }
            private = {
                AssetSource.CloudProvider.VMWARE,
                AssetSource.CloudProvider.OPENSTACK,
                AssetSource.CloudProvider.PVE,
            }
            if provider not in public | private:
                raise serializers.ValidationError("不支持的云平台")
            if provider in public and not regions:
                raise serializers.ValidationError("公有云账号必须填写区域")
            if provider in private:
                try:
                    parsed = urlsplit(endpoint)
                    valid_port = parsed.port is None or 1 <= parsed.port <= 65535
                    valid_host = bool(parsed.hostname)
                except ValueError:
                    valid_port, valid_host = False, False
                    parsed = None
                allowed_paths = (
                    ("", "/", "/v3", "/identity/v3")
                    if provider == AssetSource.CloudProvider.OPENSTACK
                    else ("", "/")
                )
                if (
                    not parsed
                    or parsed.scheme != "https"
                    or not valid_host
                    or not valid_port
                    or parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                    or parsed.path not in allowed_paths
                ):
                    raise serializers.ValidationError(
                        "私有云接入地址必须是 HTTPS 根地址或 OpenStack Keystone v3 地址"
                    )
            if provider == AssetSource.CloudProvider.OPENSTACK:
                if not isinstance(metadata, dict) or not metadata.get("project_name"):
                    raise serializers.ValidationError("OpenStack 必须填写项目名称")
            if not (has_stored or key_id):
                raise serializers.ValidationError("云账号必须填写完整的只读凭据")
            if (
                self.instance
                and provider != self.instance.cloud_provider
                and not key_id
            ):
                raise serializers.ValidationError("更换云厂商时必须重新填写 AccessKey")
            if key_id and not getattr(settings, "CREDENTIAL_ENCRYPTION_KEY", ""):
                raise serializers.ValidationError(
                    "未配置 DEVOPS_CREDENTIAL_ENCRYPTION_KEY，无法保存云凭据"
                )
        return attrs

    def _set_credentials(self, attrs):
        key_id = attrs.pop("access_key_id", "")
        key_secret = attrs.pop("access_key_secret", "")
        if key_id and key_secret:
            attrs["credentials_encrypted"] = encrypt_secret(
                json.dumps({"access_key_id": key_id, "access_key_secret": key_secret})
            )
        if (
            attrs.get("source_type")
            and attrs["source_type"] != AssetSource.SourceType.CLOUD
        ):
            attrs.update(cloud_provider="", regions=[], credentials_encrypted="")
        return attrs

    def create(self, validated_data):
        return super().create(self._set_credentials(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._set_credentials(validated_data))


class AssetSyncRecordSerializer(StandardModelSerializer):
    sourceName = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = AssetSyncRecord
        exclude = ("payload", "failure_alert")


class CredentialRefSerializer(StandardModelSerializer):
    secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Plaintext password or SSH private key. Encrypted before storage.",
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        credential_type = attrs.get("type", getattr(self.instance, "type", None))
        secret_ref = attrs.get(
            "secret_ref",
            getattr(self.instance, "secret_ref", ""),
        )
        has_encrypted = bool(
            attrs.get("secret") or getattr(self.instance, "encrypted_secret", "")
        )

        connection_type = attrs.get(
            "connection_type",
            getattr(self.instance, "connection_type", None),
        )
        if connection_type == CredentialRef.ConnectionProtocol.LOCAL:
            # The model keeps "local" only for historical rows; it never
            # affected execution (transport is decided by the host's own
            # connection_type), so reject it on create/update.
            raise serializers.ValidationError(
                {
                    "connection_type": "The Local protocol is not supported for credentials."
                }
            )

        if credential_type == CredentialRef.CredentialType.VAULT_REF:
            # No Vault provider is configured in this deployment; refuse to
            # create credentials that could never be executed.
            raise serializers.ValidationError(
                {"type": "Vault credentials are not supported in this deployment."}
            )
        elif credential_type in {
            CredentialRef.CredentialType.PASSWORD,
            CredentialRef.CredentialType.SSH_KEY,
        }:
            # Allow either external ref (env:/file:) or encrypted inline secret
            has_external = secret_ref.startswith(("env:", "file:"))
            if has_external:
                try:
                    check_secret_ref(secret_ref)
                except ValueError as exc:
                    raise serializers.ValidationError({"secret_ref": str(exc)}) from exc
            elif not has_encrypted:
                raise serializers.ValidationError(
                    {
                        "secret": (
                            "Provide a password/key directly, or an external "
                            "reference (env:/file:) in secret_ref."
                        )
                    }
                )
            # Inline secret requires the platform encryption key; fail as a
            # readable 400 instead of a Fernet ValueError -> 500 on save.
            if attrs.get("secret") and not getattr(
                settings, "CREDENTIAL_ENCRYPTION_KEY", ""
            ):
                raise serializers.ValidationError(
                    {
                        "secret": (
                            "Platform credential encryption key is not "
                            "configured (DEVOPS_CREDENTIAL_ENCRYPTION_KEY); "
                            "cannot store secrets inline."
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        secret = validated_data.pop("secret", "")
        if secret:
            validated_data["encrypted_secret"] = encrypt_secret(secret)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        secret = validated_data.pop("secret", "")
        if secret:
            validated_data["encrypted_secret"] = encrypt_secret(secret)
        elif secret == "":
            # Explicitly sent empty string — do not overwrite existing secret
            pass
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["hostCount"] = getattr(instance, "host_count", 0)
        representation["effectivePort"] = instance.effective_port
        # Never expose encrypted token; show placeholder only
        representation["encrypted_secret"] = mask_secret(instance.encrypted_secret)
        return representation

    class Meta:
        model = CredentialRef
        fields = "__all__"


class AssetHostSerializer(StandardModelSerializer):
    class Meta:
        model = AssetHost
        # Explicit whitelist: new model fields must be added here deliberately.
        fields = [
            "id",
            "hostname",
            "internal_ip",
            "external_ip",
            "asset_type",
            "os_family",
            "os_type",
            "image_name",
            "cpu_cores",
            "memory_mb",
            "system_disk_gb",
            "data_disk_gb",
            "disk_summary",
            "environment",
            "region",
            "status",
            "asset_source",
            "owner_team",
            "app_code",
            "connection_type",
            "connection_port",
            "credential_ref",
            "ansible_connection_vars",
            "metadata",
            "source_type",
            "source_id",
            "last_synced_at",
            "last_discovered_at",
            "cloud_state",
            "last_observed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("cloud_state", "last_observed_at", "last_synced_at")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        source = attrs.get("asset_source", getattr(instance, "asset_source", None))
        source_id = attrs.get("source_id", getattr(instance, "source_id", ""))
        if not (source and str(source_id or "").strip()):
            hostname = attrs.get("hostname", getattr(instance, "hostname", ""))
            address = attrs.get("internal_ip", getattr(instance, "internal_ip", ""))
            duplicate = AssetHost.objects.filter(
                hostname=hostname, internal_ip=address, source_identity__isnull=True
            )
            if instance:
                duplicate = duplicate.exclude(pk=instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError("相同主机名称和内网 IP 的人工资产已存在")
        if "default_gateway" in self.initial_data:
            raise serializers.ValidationError(
                {"default_gateway": "主机不再配置默认网关，请在运行时显式选择连接网关"}
            )
        connection_type = attrs.get(
            "connection_type",
            getattr(self.instance, "connection_type", AssetHost.ConnectionType.SSH),
        )
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation = {
            self._camel(key): value for key, value in representation.items()
        }
        representation["configSummary"] = instance.config_summary()
        representation["credentialRefName"] = (
            instance.credential_ref.name if instance.credential_ref else ""
        )
        representation["assetSourceName"] = (
            instance.asset_source.name if instance.asset_source else ""
        )
        representation["groupIds"] = [
            str(membership.group_id) for membership in instance.group_memberships.all()
        ]
        return representation

    @staticmethod
    def _camel(value):
        head, *tail = value.split("_")
        return head + "".join(part[:1].upper() + part[1:] for part in tail)


class HostGroupSerializer(StandardModelSerializer):
    class Meta:
        model = HostGroup
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        group_type = attrs.get(
            "group_type",
            getattr(self.instance, "group_type", HostGroup.GroupType.STATIC),
        )
        match_rule = attrs.get("match_rule", getattr(self.instance, "match_rule", {}))
        if group_type == HostGroup.GroupType.DYNAMIC:
            if not isinstance(match_rule, dict) or not match_rule:
                raise serializers.ValidationError(
                    {"match_rule": "Dynamic groups require a non-empty match rule."}
                )
        elif match_rule:
            attrs["match_rule"] = {}
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["parentId"] = (
            str(instance.parent_id) if instance.parent_id else "0"
        )
        representation["hostCount"] = (
            instance.memberships.count() if hasattr(instance, "memberships") else 0
        )
        return representation


class HostTagSerializer(StandardModelSerializer):
    class Meta:
        model = HostTag
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["label"] = str(instance)
        return representation


class AssetProbeSerializer(StandardModelSerializer):
    hostname = serializers.CharField(source="host.hostname", read_only=True)
    workerPoolName = serializers.CharField(
        source="worker_pool.name", read_only=True, default=""
    )

    class Meta:
        model = AssetProbe
        fields = [
            "id",
            "hostname",
            "kind",
            "module",
            "status",
            "worker_pool",
            "workerPoolName",
            "attempt",
            "result",
            "error",
            "created_at",
            "updated_at",
        ]
