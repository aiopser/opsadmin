"""Catalog is read-only: a catalog node is not an Agent write destination."""
from rest_framework import serializers


class CatalogQuerySerializer(serializers.Serializer):
    datacenter = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )


class CatalogInstanceQuerySerializer(CatalogQuerySerializer):
    service = serializers.CharField(max_length=256)
    pageNum = serializers.IntegerField(min_value=1, required=False, default=1)
    pageSize = serializers.IntegerField(
        min_value=1, max_value=100, required=False, default=20
    )


def catalog_item(item):
    node, service = item["Node"], item["Service"]
    statuses = [
        check.get("Status", "unknown")
        for check in item["Checks"]
        if isinstance(check, dict)
    ]
    health = (
        "critical"
        if "critical" in statuses
        else "warning"
        if "warning" in statuses
        else "passing"
        if statuses and all(value == "passing" for value in statuses)
        else "unknown"
    )
    return {
        "id": service.get("ID", ""),
        "node": node.get("Node", ""),
        "name": service.get("Service", ""),
        "address": service.get("Address") or node.get("Address", ""),
        "port": service.get("Port", 0),
        "tags": service.get("Tags") or [],
        "meta": service.get("Meta") or {},
        "health": health,
        "datacenter": node.get("Datacenter", ""),
        "managed": False,
    }
