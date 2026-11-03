"""Catalog and operational payload contracts, without exposing credentials or state."""

from rest_framework import serializers
from .catalog.types import KINDS


class CatalogQuerySerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=sorted(KINDS))
    versionId = serializers.IntegerField(min_value=1)
    region = serializers.CharField()
    pageSize = serializers.IntegerField(required=False, min_value=1, max_value=100)
    cursor = serializers.CharField(required=False)
    zone = serializers.CharField(required=False)
    vpcId = serializers.CharField(required=False)
    instanceType = serializers.CharField(required=False)
    imageId = serializers.CharField(required=False)
    resourceId = serializers.CharField(required=False)
    search = serializers.CharField(required=False, max_length=100)
    refresh = serializers.BooleanField(required=False)


class CredentialCatalogQuerySerializer(CatalogQuerySerializer):
    credentialId = serializers.IntegerField(min_value=1)


class ConfigurationCatalogQuerySerializer(CatalogQuerySerializer):
    sourceId = serializers.IntegerField(min_value=1)


class CatalogItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    available = serializers.BooleanField(allow_null=True)
    unavailableReason = serializers.CharField(allow_blank=True)
    attributes = serializers.DictField(child=serializers.JSONField())


class CatalogPageSerializer(serializers.Serializer):
    items = CatalogItemSerializer(many=True)
    hasMore = serializers.BooleanField()
    nextCursor = serializers.CharField(allow_null=True)
    observedAt = serializers.DateTimeField()
    warnings = serializers.ListField(child=serializers.CharField())


class ProvisioningWorkerSerializer(serializers.Serializer):
    id = serializers.CharField()
    online = serializers.BooleanField()
    lastSeenAt = serializers.DateTimeField()
    checks = serializers.DictField(child=serializers.BooleanField())


class ProvisioningIncidentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    kind = serializers.CharField()
    message = serializers.CharField()
    created_at = serializers.DateTimeField()


class ProvisioningStorageHealthSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    message = serializers.CharField()


class ProvisioningRetentionSerializer(serializers.Serializer):
    planDays = serializers.IntegerField()
    diagnosticDays = serializers.IntegerField()
    retiredStateDays = serializers.IntegerField()
    auditDays = serializers.IntegerField()
    activeStateProtected = serializers.BooleanField()


class ProvisioningOperationsHealthSerializer(serializers.Serializer):
    workers = ProvisioningWorkerSerializer(many=True)
    queued = serializers.IntegerField()
    uncertain = serializers.IntegerField()
    incidents = ProvisioningIncidentSerializer(many=True)
    observedAt = serializers.DateTimeField()
    storage = ProvisioningStorageHealthSerializer()
    retention = ProvisioningRetentionSerializer()


class ProvisioningAttemptSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()
    error_message = serializers.CharField(allow_blank=True)
    instance_ids = serializers.ListField(child=serializers.CharField())
    asset_ids = serializers.ListField(child=serializers.IntegerField())


class StateProtectionSummarySerializer(serializers.Serializer):
    status = serializers.CharField()
    versionId = serializers.IntegerField(allow_null=True)
    verifiedAt = serializers.DateTimeField(allow_null=True)
    message = serializers.CharField(allow_blank=True)
