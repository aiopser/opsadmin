from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from drf_spectacular.utils import extend_schema

from common.api.filters import KeywordSearchFilter
from common.api.responses import api_error_response, api_ok_response
from common.api.schema import generate_crud_schema
from common.api.viewsets import CommaSeparatedBulkDeleteMixin, StandardModelViewSet
from ..models import Department
from ..serializers import DepartmentSerializer


@generate_crud_schema(verbose_name="部门", tags=["部门管理"])
class DepartmentViewSet(CommaSeparatedBulkDeleteMixin, StandardModelViewSet):
    queryset = Department.objects.filter().order_by("-id")
    serializer_class = DepartmentSerializer

    # 声明式过滤：keywords 模糊搜索 / 字段精确匹配 / 排序
    filter_backends = (DjangoFilterBackend, KeywordSearchFilter, OrderingFilter)
    filterset_fields = ("id", "status")
    search_fields = ("name", "code")
    ordering_fields = ("id",)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset()).order_by("sort", "id")
        serializer = self.get_serializer(queryset, many=True)
        return api_ok_response(self._build_tree(serializer.data))

    def update(self, request, *args, **kwargs):
        parent_id = request.data.get("parentId") or request.data.get("parent")
        current_id = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""))
        if parent_id and str(parent_id) == current_id:
            return api_error_response("Parent department cannot be itself")
        return super().update(request, *args, **kwargs)

    @extend_schema(summary="获取部门选项", tags=["部门管理"])
    @action(methods=["GET"], detail=False, url_path="options")
    def options(self, request):
        # filter_queryset 自动应用 keywords / status 等过滤
        departments = (
            self.filter_queryset(self.get_queryset()).order_by("sort", "id")
        )
        nodes = [
            {
                "value": str(department.id),
                "label": department.name,
                "parentId": str(department.parent_id) if department.parent_id else "0",
                "children": [],
            }
            for department in departments
        ]
        return api_ok_response(self._build_tree(nodes))

    @extend_schema(summary="获取部门表单数据", tags=["部门管理"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)

    def _build_tree(self, items):
        lookup = {
            str(item["id"] if "id" in item else item["value"]): item for item in items
        }
        roots = []
        for item in items:
            item.setdefault("children", [])
        for item in items:
            parent_id = str(item.get("parentId") or "0")
            if parent_id != "0" and parent_id in lookup:
                lookup[parent_id].setdefault("children", []).append(item)
            else:
                roots.append(item)
        return roots
