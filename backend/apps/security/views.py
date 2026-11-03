from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from common.api.viewsets import StandardModelViewSet
from common.api.responses import api_ok_response
from .models import SecurityAdvisory, SecurityCollection, SecuritySubscription
from .serializers import (
    AdvisorySerializer,
    CollectionSerializer,
    SubscriptionSerializer,
)
from .tasks import enqueue
from django.db import transaction
from apps.audit_center.services import create_domain_audit_event


class SubscriptionViewSet(StandardModelViewSet):
    queryset = SecuritySubscription.objects.all().order_by("-id")
    serializer_class = SubscriptionSerializer

    def audit(self, row, action):
        create_domain_audit_event(
            self.request.user,
            "security.subscription." + action,
            "security_subscription",
            row.pk,
            after={"name": row.name, "enabled": row.enabled},
            request=self.request,
            domain="monitoring",
        )

    def perform_create(self, serializer, request=None):
        self.audit(serializer.save(actor=self.request.user), "create")

    def perform_update(self, serializer, request=None):
        self.audit(serializer.save(actor=self.request.user), "update")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        row = SecuritySubscription.objects.select_for_update().get(
            pk=self.get_object().pk
        )
        if SecurityCollection.objects.filter(subscription=row).exists():
            raise ValidationError("订阅已有采集记录，请停用订阅以保留历史")
        self.audit(row, "delete")
        row.delete()
        return api_ok_response()

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def collect(self, request, pk=None):
        subscription = self.get_object()
        try:
            record = enqueue(subscription.pk, request.user)
            self.audit(subscription, "collect")
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
        return api_ok_response(CollectionSerializer(record).data)


class AdvisoryViewSet(StandardModelViewSet):
    queryset = SecurityAdvisory.objects.all().order_by("-published", "-id")
    serializer_class = AdvisorySerializer
    http_method_names = ["get", "head", "options"]
    search_fields = ["stable_id", "title", "category"]
    filterset_fields = ["severity"]


class CollectionViewSet(StandardModelViewSet):
    queryset = SecurityCollection.objects.all().order_by("-id")
    serializer_class = CollectionSerializer
    http_method_names = ["get", "head", "options"]
    filterset_fields = ["subscription", "status"]
