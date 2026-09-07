from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from drf_spectacular.utils import extend_schema

from common.api.filters import KeywordSearchFilter
from common.api.responses import api_error_response, api_ok_response
from common.api.schema import generate_crud_schema
from common.api.viewsets import CommaSeparatedBulkDeleteMixin, StandardModelViewSet
from ..models import DictItem, DictType
from ..serializers import DictItemSerializer, DictTypeSerializer


@generate_crud_schema(verbose_name="字典", tags=["字典管理"])
class DictTypeViewSet(CommaSeparatedBulkDeleteMixin, StandardModelViewSet):
    queryset = DictType.objects.all().order_by("-id")
    serializer_class = DictTypeSerializer

    # 显式挂载过滤器：字段精确匹配 / keywords 模糊搜索 / 排序
    # （KeywordSearchFilter 监听 keywords 参数，替代原 get_queryset 手写过滤）
    filter_backends = (DjangoFilterBackend, KeywordSearchFilter, OrderingFilter)
    filterset_fields = ("id", "dict_code", "status")
    search_fields = ("name", "dict_code")
    ordering_fields = ("id", "name", "dict_code", "status")

    @extend_schema(summary="获取字典选项", tags=["字典管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request):
        # filter_queryset 自动应用 keywords / status 等过滤
        queryset = self.filter_queryset(self.get_queryset()).order_by("name", "id")
        return api_ok_response(
            [
                {
                    "value": item.dict_code,
                    "label": item.name,
                }
                for item in queryset
            ]
        )

    @extend_schema(summary="获取字典表单", tags=["字典管理"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)


@generate_crud_schema(verbose_name="字典项", tags=["字典管理"])
class DictItemViewSet(CommaSeparatedBulkDeleteMixin, StandardModelViewSet):
    queryset = DictItem.objects.select_related("dict_type").all().order_by("sort", "id")
    serializer_class = DictItemSerializer
    lookup_url_kwarg = "item_pk"

    filter_backends = (DjangoFilterBackend, KeywordSearchFilter, OrderingFilter)
    filterset_fields = ("id", "status")
    search_fields = ("label", "value")
    ordering_fields = ("id", "sort", "label", "value", "status")

    def get_queryset(self):
        # 仅保留路由嵌套（dict_code）这一特异性逻辑，其余交给过滤器
        queryset = super().get_queryset()
        if dict_code := self.kwargs.get("dict_code"):
            queryset = queryset.filter(dict_type__dict_code=dict_code)
        return queryset

    def create(self, request, *args, **kwargs):
        if not (dict_type := self._get_dict_type()):
            return api_error_response("Dictionary not found")

        data = request.data.copy()
        data["dict_type"] = dict_type.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer, request)
        return api_ok_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        data = request.data.copy()

        if "dict_type" not in data and (dict_type := self._get_dict_type()):
            data["dict_type"] = dict_type.id

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer, request)
        return api_ok_response(serializer.data)

    @extend_schema(summary="获取字典项选项", tags=["字典管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request, dict_code=None):
        # status=1 为获取选项的固定业务规则，在此显式过滤
        queryset = (
            self.filter_queryset(self.get_queryset())
            .filter(status=1)
            .order_by("sort", "id")
        )
        return api_ok_response(
            [
                {
                    "value": item.value,
                    "label": item.label,
                    "tagType": item.tag_type,
                }
                for item in queryset
            ]
        )

    @extend_schema(summary="获取字典项表单", tags=["字典管理"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, dict_code=None, item_pk=None):
        return self.retrieve(request, item_pk=item_pk)

    def _get_dict_type(self):
        if not (dict_code := self.kwargs.get("dict_code")):
            return None
        try:
            return DictType.objects.get(dict_code=dict_code)
        except DictType.DoesNotExist:
            return None
