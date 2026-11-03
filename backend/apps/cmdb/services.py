from django.db.models import Q

from .models import AssetHost, HostGroup, HostGroupMembership


SUPPORTED_DYNAMIC_FIELDS = {
    "os_family",
    "environment",
    "status",
    "app_code",
    "asset_source",
    "connection_type",
}


def _apply_dynamic_rule(queryset, rule):
    if not isinstance(rule, dict) or not rule:
        return queryset.none()
    query = Q()
    matched_fields = 0
    for field, value in rule.items():
        if field not in SUPPORTED_DYNAMIC_FIELDS:
            return queryset.none()
        if isinstance(value, list):
            if not value:
                return queryset.none()
            query &= Q(**{f"{field}__in": value})
        elif value not in (None, ""):
            query &= Q(**{field: value})
        else:
            return queryset.none()
        matched_fields += 1
    return queryset.filter(query) if matched_fields else queryset.none()


def collect_group_tree_ids(group_ids):
    """Collect the given group IDs plus all descendant group IDs (BFS)."""
    ids = {int(gid) for gid in group_ids if str(gid).strip().isdigit()}
    frontier = list(ids)
    while frontier:
        children = HostGroup.objects.filter(
            parent_id__in=frontier
        ).values_list("id", flat=True)
        frontier = [cid for cid in children if cid not in ids]
        ids.update(frontier)
    return ids


def resolve_group_host_ids(group_ids):
    """Resolve static and dynamic groups into active host IDs for execution."""
    groups = HostGroup.objects.filter(id__in=group_ids, is_active=True)
    static_ids = set(
        HostGroupMembership.objects.filter(
            group_id__in=groups.filter(group_type=HostGroup.GroupType.STATIC).values(
                "id"
            )
        ).values_list("host_id", flat=True)
    )
    dynamic_ids = set()
    active_hosts = AssetHost.objects.filter(status=AssetHost.HostStatus.ACTIVE)
    for group in groups.filter(group_type=HostGroup.GroupType.DYNAMIC):
        dynamic_ids.update(
            _apply_dynamic_rule(active_hosts, group.match_rule).values_list(
                "id", flat=True
            )
        )
    return static_ids | dynamic_ids
