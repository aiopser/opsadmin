from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, extend_schema_view
from common.api.schema import api_envelope_serializer
from .schema_serializers import (
    CatalogPageSerializer,
    CredentialCatalogQuerySerializer,
    ConfigurationCatalogQuerySerializer,
)

from common.auth.rbac import ApiRBACPermission
from common.api.responses import api_ok_response
from .contracts import ProvisioningError
from .catalog.service import list_catalog


@extend_schema_view(
    get=extend_schema(
        parameters=[CredentialCatalogQuerySerializer],
        responses=api_envelope_serializer(
            "ProvisioningCatalogResponse", CatalogPageSerializer
        ),
    )
)
class CatalogView(APIView):
    permission_classes = [IsAuthenticated, ApiRBACPermission]
    configuration = False

    def get(self, request):
        try:
            data = list_catalog(
                request.user,
                request.query_params.dict(),
                configuration=self.configuration,
            )
        except ProvisioningError as exc:
            raise serializers.ValidationError(str(exc)) from None
        return api_ok_response(data)


@extend_schema_view(
    get=extend_schema(
        parameters=[ConfigurationCatalogQuerySerializer],
        responses=api_envelope_serializer(
            "ProvisioningConfigurationCatalogResponse", CatalogPageSerializer
        ),
    )
)
class ConfigurationCatalogView(CatalogView):
    configuration = True
