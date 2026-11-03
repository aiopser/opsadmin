from django.core.cache import cache
from django.db.models import Q
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from common.api.responses import api_error_response, api_ok_response
from common.api.schema import generate_crud_schema, api_envelope_serializer
from common.api.viewsets import StandardModelViewSet
from common.api.views import StandardOpenApiView
from ..models import SystemConfig
from ..serializers import SystemConfigSerializer


CONFIG_CACHE_KEY = "system_config:snapshot"

# 允许未登录访问的公开配置键（避免泄露内部配置）
PUBLIC_CONFIG_KEYS = (
    "basic.system.name",
    "basic.login.title",
    "basic.user.default_avatar",
)


def get_system_config_snapshot(force_refresh=False):
    snapshot = None
    if not force_refresh:
        try:
            snapshot = cache.get(CONFIG_CACHE_KEY)
        except Exception:
            snapshot = None
    if snapshot is None:
        snapshot = {
            item.config_key: item.config_value
            for item in SystemConfig.objects.all().order_by("config_group", "id")
        }
        try:
            cache.set(CONFIG_CACHE_KEY, snapshot, 60 * 10)
        except Exception:
            if force_refresh:
                raise
    return snapshot


@generate_crud_schema(verbose_name="系统配置", tags=["系统配置"])
class SystemConfigViewSet(StandardModelViewSet):
    queryset = SystemConfig.objects.all().order_by("config_group", "id")
    serializer_class = SystemConfigSerializer
    ordering_fields = ("id", "config_group", "config_key")
    filterset_fields = ("id", "config_key", "config_group")
    search_fields = ("config_name", "config_key", "remark")

    def get_queryset(self):
        queryset = super().get_queryset()
        keywords = self.request.query_params.get("keywords")
        config_group = self.request.query_params.get(
            "configGroup"
        ) or self.request.query_params.get("config_group")
        if config_group:
            queryset = queryset.filter(config_group=config_group)
        if keywords:
            queryset = queryset.filter(
                Q(config_name__icontains=keywords)
                | Q(config_key__icontains=keywords)
                | Q(remark__icontains=keywords)
            )
        return queryset

    def perform_create(self, serializer, request=None):
        instance = serializer.save(request=request)
        self.__clear_cache()
        return instance

    def perform_update(self, serializer, request=None):
        instance = serializer.save(request=request)
        self.__clear_cache()
        return instance

    def destroy(self, request, *args, **kwargs):
        response = super().destroy(request, *args, **kwargs)
        self.__clear_cache()
        return response

    def __clear_cache(self):
        try:
            cache.delete(CONFIG_CACHE_KEY)
        except Exception:
            pass

    @extend_schema(summary="获取系统配置表单", tags=["系统配置"])
    @action(methods=["GET"], detail=True, url_path="form")
    def form(self, request, pk=None):
        return self.retrieve(request, pk=pk)

    @extend_schema(summary="刷新系统配置缓存", tags=["系统配置"])
    @action(methods=["PUT"], detail=False, url_path="refresh")
    def refresh(self, request):
        try:
            snapshot = get_system_config_snapshot(force_refresh=True)
        except Exception:
            return api_error_response("刷新配置缓存失败，请检查缓存服务后重试", http_status=503)
        return api_ok_response({"count": len(snapshot)})

    @extend_schema(summary="获取系统配置快照", tags=["系统配置"])
    @action(methods=["GET"], detail=False, url_path="snapshot")
    def snapshot(self, request):
        return api_ok_response(get_system_config_snapshot())


class PublicConfigApiView(StandardOpenApiView):
    """公开站点配置（开放接口，无需认证，仅返回白名单键）"""

    @extend_schema(
        summary="获取公开站点配置",
        tags=["系统配置"],
        auth=[],
        responses=api_envelope_serializer(
            "PublicConfigResponse",
            inline_serializer(
                name="PublicSiteConfig",
                fields={
                    key: serializers.CharField(allow_blank=True)
                    for key in PUBLIC_CONFIG_KEYS
                },
            ),
        ),
    )
    def get(self, request, *args, **kwargs):
        snapshot = get_system_config_snapshot()
        data = {key: snapshot.get(key, "") for key in PUBLIC_CONFIG_KEYS}
        return api_ok_response(data)
