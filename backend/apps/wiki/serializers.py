from rest_framework import serializers

from common.api.serializers import StandardModelSerializer

from .models import WikiPage


class WikiPageTreeSerializer(serializers.ModelSerializer):
    """目录树节点：不含正文，保证树接口轻量。"""

    class Meta:
        model = WikiPage
        fields = ("id", "title", "parent", "is_folder", "sort", "is_active")


class WikiPageSerializer(StandardModelSerializer):
    """文档详情：含 Markdown 正文与审计字段。"""

    class Meta:
        model = WikiPage
        fields = (
            "id",
            "title",
            "parent",
            "is_folder",
            "content",
            "sort",
            "is_active",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        parent = attrs.get("parent")
        if parent is None or self.instance is None:
            return attrs
        if parent.pk in self.instance.collect_self_and_descendant_ids():
            raise serializers.ValidationError(
                {"parent": "父节点不能是自身或其子孙节点"}
            )
        return attrs
