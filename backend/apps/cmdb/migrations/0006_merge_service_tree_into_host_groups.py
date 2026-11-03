from django.db import migrations


def migrate_service_tree_to_host_groups(apps, schema_editor):
    """服务树节点 → 同名静态分组（保持父子层级），主机归属 → 分组成员。

    - 每个服务树节点对应一个同名静态分组；同名分组已存在时复用，不覆盖用户已有配置。
    - 节点父子关系映射为分组 parent。
    - 主机 service_node 归属转换为该分组的一条 HostGroupMembership。
    """

    ServiceTreeNode = apps.get_model("cmdb", "ServiceTreeNode")
    HostGroup = apps.get_model("cmdb", "HostGroup")
    AssetHost = apps.get_model("cmdb", "AssetHost")
    HostGroupMembership = apps.get_model("cmdb", "HostGroupMembership")

    node_to_group = {}

    def ensure_group_for_node(node):
        if node.id in node_to_group:
            return node_to_group[node.id]
        parent_group_id = None
        if node.parent_id:
            parent_node = ServiceTreeNode.objects.get(pk=node.parent_id)
            parent_group_id = ensure_group_for_node(parent_node)
        group, _ = HostGroup.objects.get_or_create(
            name=node.name,
            group_type="static",
            defaults={
                "parent_id": parent_group_id,
                "is_active": node.is_active,
                "description": node.description or "",
            },
        )
        # 复用已有同名分组时仅补齐父级，避免层级断裂
        if parent_group_id and not group.parent_id:
            group.parent_id = parent_group_id
            group.save(update_fields=["parent_id", "updated_at"])
        node_to_group[node.id] = group.id
        return group.id

    for node in ServiceTreeNode.objects.all().order_by("id"):
        ensure_group_for_node(node)

    memberships = [
        HostGroupMembership(host_id=host.id, group_id=node_to_group[host.service_node_id])
        for host in AssetHost.objects.filter(service_node__isnull=False).iterator()
        if host.service_node_id in node_to_group
    ]
    HostGroupMembership.objects.bulk_create(memberships, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("cmdb", "0005_assethost_split_ip"),
    ]

    operations = [
        migrations.RunPython(
            migrate_service_tree_to_host_groups,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="assethost",
            name="service_node",
        ),
        migrations.DeleteModel(name="ServiceTreeNode"),
        migrations.DeleteModel(name="Business"),
    ]
