from dataclasses import dataclass

KINDS = {
    "zones",
    "images",
    "instance_types",
    "vpcs",
    "subnets",
    "security_groups",
    "availability",
    "quota",
}


@dataclass(frozen=True)
class CatalogQuery:
    kind: str
    region: str
    page_size: int = 50
    zone: str = ""
    vpc_id: str = ""
    instance_type: str = ""
    image_id: str = ""
    resource_id: str = ""
    search: str = ""


def item(identity, name=None, *, available=None, reason="", tags=None, **attributes):
    return {
        "id": str(identity),
        "name": str(name or identity),
        "description": "",
        "available": available,
        "unavailableReason": reason,
        "attributes": attributes,
        "_tags": tags or {},
    }


def tags_of(value, key="Key", val="Value"):
    return {
        str(row.get(key)): str(row.get(val, "")) for row in value or [] if row.get(key)
    }
