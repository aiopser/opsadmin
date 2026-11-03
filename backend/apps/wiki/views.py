from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action

from common.api.responses import api_ok_response
from common.api.viewsets import StandardModelViewSet

from .models import WikiPage
from .serializers import WikiPageSerializer, WikiPageTreeSerializer


class WikiPageViewSet(StandardModelViewSet):
    queryset = WikiPage.objects.all()
    serializer_class = WikiPageSerializer

    @extend_schema(summary="获取知识库目录树", tags=["知识库"])
    @action(methods=["GET"], detail=False, url_path="tree")
    def tree(self, request, *args, **kwargs):
        """返回扁平节点列表（含 parent），由前端组装成树，避免大树深递归。"""
        queryset = self.get_queryset().order_by("sort", "id")
        serializer = WikiPageTreeSerializer(queryset, many=True)
        return api_ok_response(serializer.data)
