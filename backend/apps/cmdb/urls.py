from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AssetHostViewSet,
    AssetSourceViewSet,
    AssetSyncRecordViewSet,
    BusinessViewSet,
    CredentialRefViewSet,
    HostGroupViewSet,
    HostTagViewSet,
    ServiceTreeNodeViewSet,
    WorkerPoolViewSet,
    CMDBSearchView,
)

router = SimpleRouter(trailing_slash=False)
router.register(r"v1/cmdb/hosts", AssetHostViewSet, basename="cmdb-hosts")
router.register(
    r"v1/cmdb/asset-sources", AssetSourceViewSet, basename="cmdb-asset-sources"
)
router.register(
    r"v1/cmdb/asset-sync-records",
    AssetSyncRecordViewSet,
    basename="cmdb-asset-sync-records",
)
router.register(r"v1/cmdb/businesses", BusinessViewSet, basename="cmdb-businesses")
router.register(
    r"v1/cmdb/service-tree-nodes",
    ServiceTreeNodeViewSet,
    basename="cmdb-service-tree-nodes",
)
router.register(r"v1/cmdb/host-groups", HostGroupViewSet, basename="cmdb-host-groups")
router.register(r"v1/cmdb/tags", HostTagViewSet, basename="cmdb-tags")
router.register(
    r"v1/cmdb/credential-refs",
    CredentialRefViewSet,
    basename="cmdb-credential-refs",
)
router.register(
    r"v1/cmdb/worker-pools", WorkerPoolViewSet, basename="cmdb-worker-pools"
)

urlpatterns = [
    path("v1/cmdb/search", CMDBSearchView.as_view(), name="cmdb-search"),
] + router.urls
