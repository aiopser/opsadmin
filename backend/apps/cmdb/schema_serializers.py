"""Custom CMDB query payloads independent from writable model serializers."""

from rest_framework import serializers


class HostSearchItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    hostname = serializers.CharField()
    internal_ip = serializers.CharField(allow_blank=True, allow_null=True)
    external_ip = serializers.CharField(allow_blank=True, allow_null=True)
    asset_type = serializers.CharField()
    status = serializers.CharField()


class HostGroupSearchItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    group_type = serializers.CharField()


class AssetSourceSearchItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()
    source_type = serializers.CharField()


class CMDBSearchSerializer(serializers.Serializer):
    hosts = HostSearchItemSerializer(many=True)
    hostGroups = HostGroupSearchItemSerializer(many=True)
    assetSources = AssetSourceSearchItemSerializer(many=True)


class AssetSourceCapabilitiesSerializer(serializers.Serializer):
    fields = serializers.ListField(child=serializers.CharField())
    maxAssets = serializers.IntegerField()
    scope = serializers.CharField()
