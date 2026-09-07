from rest_framework.viewsets import ModelViewSet

from common.api.responses import api_error_response, api_ok_response


class CommaSeparatedBulkDeleteMixin:
    """支持逗号分隔主键批量删除的 Mixin。

    DELETE /api/v1/xxx/1,2,3 时批量删除并返回 {"deleted": n}，
    单个主键时回退到 StandardModelViewSet.destroy（保留 is_system 保护）。

    用法（显式继承，勿混入基类——否则会被基类自身的 destroy 覆盖）：
        class DictTypeViewSet(CommaSeparatedBulkDeleteMixin, StandardModelViewSet):
            ...

    注意：仅适用于无 is_system 批量保护需求的资源；
    角色等内置数据资源保留自身重写的 destroy，不应套用此 Mixin。
    """

    def destroy(self, request, *args, **kwargs):
        raw_pk = str(kwargs.get(self.lookup_url_kwarg or self.lookup_field, ""))
        ids = [item for item in raw_pk.split(",") if item]

        if len(ids) > 1:
            deleted, _ = self.get_queryset().filter(pk__in=ids).delete()
            return api_ok_response({"deleted": deleted})

        return super().destroy(request, *args, **kwargs)


class StandardModelViewSet(ModelViewSet):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer, request)
        return api_ok_response(serializer.data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer, request)

        if getattr(instance, "_prefetched_objects_cache", None):
            instance._prefetched_objects_cache = {}

        return api_ok_response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if getattr(instance, "is_system", False):
            return api_error_response("Built-in data cannot be deleted")
        instance.delete()
        return api_ok_response()

    def list(self, request, *args, **kwargs):
        try:
            sort_by = request.query_params.get("sortBy", "").strip()
            order = request.query_params.get("order", "").strip().lower()
            ordering = request.query_params.get("ordering", "").replace("+", "").strip()
            if sort_by:
                ordering = f"-{sort_by}" if order == "desc" else sort_by
            # 始终基于 get_queryset()（含视图自定义过滤）再叠加排序，
            # 避免排序分支直接重建 queryset 绕过 get_queryset() 中的领域或租户过滤。
            queryset = self.filter_queryset(self.get_queryset())
            if ordering:
                queryset = queryset.order_by(ordering)
            page = request.query_params.get("pageNum", "") or request.query_params.get(
                "page", ""
            )
            size = request.query_params.get("pageSize", "") or request.query_params.get(
                "size", ""
            )
            if page or size:
                page_queryset = self.paginate_queryset(queryset)
                if page is not None:
                    serializer = self.get_serializer(page_queryset, many=True)
                    return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return api_ok_response(data=serializer.data)
        except Exception as exc:
            return api_error_response(message=str(exc))

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        return api_ok_response(response.data)

    def perform_update(self, serializer, request=None):
        serializer.save(request=request)

    def perform_create(self, serializer, request=None):
        serializer.save(request=request)


class StandardOpenModelViewSet(ModelViewSet):
    authentication_classes = []
    permission_classes = []

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return api_ok_response(response.data)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        return api_ok_response(response.data)

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        return api_ok_response(response.data)

    def list(self, request, *args, **kwargs):
        try:
            sort_by = request.query_params.get("sortBy", "").strip()
            order = request.query_params.get("order", "").strip().lower()
            ordering = request.query_params.get("ordering", "").replace("+", "").strip()
            if sort_by:
                ordering = f"-{sort_by}" if order == "desc" else sort_by
            # 始终基于 get_queryset()（含视图自定义过滤）再叠加排序，
            # 避免排序分支直接重建 queryset 绕过 get_queryset() 中的领域或租户过滤。
            queryset = self.filter_queryset(self.get_queryset())
            if ordering:
                queryset = queryset.order_by(ordering)
            page = request.query_params.get("pageNum", "") or request.query_params.get(
                "page", ""
            )
            size = request.query_params.get("pageSize", "") or request.query_params.get(
                "size", ""
            )
            if page or size:
                page_queryset = self.paginate_queryset(queryset)
                if page is not None:
                    serializer = self.get_serializer(page_queryset, many=True)
                    return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return api_ok_response(data=serializer.data)
        except Exception as exc:
            return api_error_response(message=str(exc))

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return api_ok_response(serializer.data)
