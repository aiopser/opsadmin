from common.api.responses import api_ok_response

from collections import OrderedDict
from rest_framework import pagination


class StandardResultSetPagination(pagination.PageNumberPagination):
    page_size = 10
    max_page_size = 100
    page_query_param = "pageNum"
    page_size_query_param = "pageSize"

    def get_page_number(self, request, paginator):
        return (
            request.query_params.get(self.page_query_param)
            or request.query_params.get("page")
            or 1
        )

    def get_page_size(self, request):
        size = request.query_params.get(
            self.page_size_query_param
        ) or request.query_params.get("size")
        if size:
            return min(int(size), self.max_page_size)
        return self.page_size

    def get_paginated_response(self, data):
        return api_ok_response(
            data=OrderedDict(
                [
                    ("list", data),
                    ("total", self.page.paginator.count),
                    ("count", self.page.paginator.count),
                    ("page", self.page.number),
                    ("size", self.page.paginator.per_page),
                    ("num_pages", self.page.paginator.num_pages),
                    ("result", data),
                ]
            )
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "example": 123,
                },
                "page": {
                    "type": "integer",
                    "example": 1,
                },
                "size": {
                    "type": "integer",
                    "example": 10,
                },
                "num_pages": {
                    "type": "integer",
                    "example": 123,
                },
                "results": schema,
            },
        }
