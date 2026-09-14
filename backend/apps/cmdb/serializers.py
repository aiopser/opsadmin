from django.db import transaction
from rest_framework import serializers

from common.api.serializers import StandardModelSerializer

from .crypto import encrypt_secret, mask_secret
from .models import (
    AssetHost,
    AssetSource,
    AssetSyncRecord,
    Business,
    CredentialRef,
    HostGroup,
    HostTag,
    ServiceTreeNode,
)


class BusinessSerializer(StandardModelSerializer):
    class Meta:
        model = Business
        fields = "__all__"

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["hostCount"] = getattr(instance, "host_count", 0)
        return representation


class AssetSourceSerializer(StandardModelSerializer):
    class Meta:
        model = AssetSource
        fields = "__all__"


class AssetSyncRecordSerializer(StandardModelSerializer):
    sourceName = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = AssetSyncRecord
        fields = "__all__"


class ServiceTreeNodeSerializer(StandardModelSerializer):
    class Meta:
        model = ServiceTreeNode
        fields = "__all__"

    def validate(self, attrs):
        attrs = super().validate(attrs)
        business = attrs.get("business", getattr(self.instance, "business", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        node_type = attrs.get(
            "node_type",
            getattr(self.instance, "node_type", None),
        )

        if parent and self.instance and parent.pk == self.instance.pk:
            raise serializers.ValidationError(
                {"parent": "A node cannot be its own parent."}
            )
        if parent and business and parent.business_id != business.id:
            raise serializers.ValidationError(
                {"parent": "Parent node must belong to the same business."}
            )

        expected_parent_type = {
            ServiceTreeNode.NodeType.ENVIRONMENT: None,
            ServiceTreeNode.NodeType.REGION: ServiceTreeNode.NodeType.ENVIRONMENT,
            ServiceTreeNode.NodeType.MODULE: ServiceTreeNode.NodeType.REGION,
        }.get(node_type)
        if expected_parent_type is None and parent:
            raise serializers.ValidationError(
                {"parent": "Environment nodes must be top-level nodes."}
            )
        if expected_parent_type and (
            not parent or parent.node_type != expected_parent_type
        ):
            raise serializers.ValidationError(
                {
                    "parent": f"{node_type} nodes must be children of {expected_parent_type} nodes."
                }
            )
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["businessName"] = instance.business.name
        representation["parentName"] = instance.parent.name if instance.parent else ""
        representation["hostCount"] = getattr(instance, "host_count", 0)
        return representation




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

        if credential_type == CredentialRef.CredentialType.VAULT_REF:
            if not secret_ref.startswith("vault://"):
                raise serializers.ValidationError(
                    {"secret_ref": "Vault credentials require a vault:// reference."}
                )
        elif credential_type in {
            CredentialRef.CredentialType.PASSWORD,
            CredentialRef.CredentialType.SSH_KEY,
        }:
            # Allow either external ref (env:/file:) or encrypted inline secret
            has_external = secret_ref.startswith(("env:", "file:"))
            if not has_external and not has_encrypted:
                raise serializers.ValidationError(
                    {
                        "secret": (
                            "Provide a password/key directly, or an external "
                            "reference (env:/file:) in secret_ref."
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
            "primary_ip",
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
            "service_node",
            "asset_source",
            "owner_team",
            "app_code",
            "connection_type",
            "connection_port",
            "credential_ref",
            "default_gateway",
            "ansible_connection_vars",
            "metadata",
            "source_type",
            "source_id",
            "last_synced_at",
            "last_discovered_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        service_node = attrs.get(
            "service_node",
            getattr(self.instance, "service_node", None),
        )
        is_new_assignment = service_node and (
            not self.instance or self.instance.service_node_id != service_node.id
        )
        if is_new_assignment and not service_node.is_active:
            raise serializers.ValidationError(
                {
                    "service_node": "Hosts can only be assigned to an active service-tree node."
                }
            )
        connection_type = attrs.get(
            "connection_type",
            getattr(self.instance, "connection_type", AssetHost.ConnectionType.SSH),
        )
        default_gateway = attrs.get(
            "default_gateway",
            getattr(self.instance, "default_gateway", None),
        )
        if default_gateway and connection_type != AssetHost.ConnectionType.SSH:
            raise serializers.ValidationError(
                {"default_gateway": "Gateway proxy is only supported for SSH hosts."}
            )
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation = {self._camel(key): value for key, value in representation.items()}
        representation["configSummary"] = instance.config_summary()
        representation["credentialRefName"] = (
            instance.credential_ref.name if instance.credential_ref else ""
        )
        representation["defaultGatewayName"] = (
            instance.default_gateway.name if instance.default_gateway else ""
        )
        representation["serviceNodeName"] = (
            instance.service_node.name if instance.service_node else ""
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
