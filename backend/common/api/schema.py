from rest_framework import serializers
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer


def api_envelope_serializer(name, data_serializer=None, data_many=False):
    if data_serializer is None:
        data_field = serializers.JSONField()
    elif isinstance(data_serializer, serializers.Field):
        data_field = data_serializer
    elif data_many:
        data_field = data_serializer(many=True)
    else:
        data_field = data_serializer()

    return inline_serializer(
        name=name,
        fields={
            "code": serializers.IntegerField(),
            "data": data_field,
            "message": serializers.CharField(allow_null=True),
        },
    )


def api_message_response(name):
    return api_envelope_serializer(name, serializers.CharField())


def generate_crud_schema(verbose_name: str, tags: list[str]):
    """动态生成 CRUD 标准动作的 Swagger Schema 装饰器。

    消除各 ViewSet 上 6 行重复的 @extend_schema_view 模板：
        @generate_crud_schema(verbose_name="字典", tags=["字典管理"])
        class DictTypeViewSet(...):
    """
    return extend_schema_view(
        list=extend_schema(summary=f"获取{verbose_name}列表", tags=tags),
        retrieve=extend_schema(summary=f"获取{verbose_name}详情", tags=tags),
        create=extend_schema(summary=f"创建{verbose_name}", tags=tags),
        update=extend_schema(summary=f"更新{verbose_name}", tags=tags),
        partial_update=extend_schema(summary=f"部分更新{verbose_name}", tags=tags),
        destroy=extend_schema(summary=f"删除{verbose_name}", tags=tags),
    )
