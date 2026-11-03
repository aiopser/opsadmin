"""Payload contracts for custom common APIs; not runtime validation substitutes."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers


@extend_schema_field(OpenApiTypes.BINARY)
class UploadFileField(serializers.FileField):
    pass


class FileUploadRequestSerializer(serializers.Serializer):
    file = UploadFileField()


class FileUploadResultSerializer(serializers.Serializer):
    name = serializers.CharField()
    url = serializers.CharField()


class OperationLogItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    module = serializers.CharField()
    actionType = serializers.CharField()
    title = serializers.CharField()
    content = serializers.CharField()
    operatorId = serializers.IntegerField(allow_null=True)
    operatorName = serializers.CharField()
    requestUri = serializers.CharField()
    requestMethod = serializers.CharField()
    ip = serializers.CharField()
    region = serializers.CharField()
    device = serializers.CharField()
    browser = serializers.CharField()
    os = serializers.CharField()
    status = serializers.IntegerField()
    executionTime = serializers.IntegerField()
    errorMsg = serializers.CharField()
    createTime = serializers.RegexField(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$",
        allow_null=True,
        help_text="本地时间，格式 YYYY-MM-DD HH:MM:SS",
    )


class OperationLogPageSerializer(serializers.Serializer):
    list = OperationLogItemSerializer(many=True)
    total = serializers.IntegerField()
    count = serializers.IntegerField()
    page = serializers.IntegerField()
    size = serializers.IntegerField()


class VisitOverviewSerializer(serializers.Serializer):
    todayUvCount = serializers.IntegerField()
    totalUvCount = serializers.IntegerField()
    uvGrowthRate = serializers.FloatField()
    todayPvCount = serializers.IntegerField()
    totalPvCount = serializers.IntegerField()
    pvGrowthRate = serializers.FloatField()


class VisitTrendSerializer(serializers.Serializer):
    dates = serializers.ListField(child=serializers.DateField())
    pvList = serializers.ListField(child=serializers.IntegerField())
    uvList = serializers.ListField(child=serializers.IntegerField())


class RuntimeSdkSerializer(serializers.Serializer):
    name = serializers.CharField()
    available = serializers.BooleanField()
    version = serializers.CharField(allow_null=True)


class RuntimeEnvironmentSerializer(serializers.Serializer):
    sdks = RuntimeSdkSerializer(many=True)
    credentialsEncryptionConfigured = serializers.BooleanField()
    credentialsEncryptionValid = serializers.BooleanField()
    apiVersion = serializers.CharField()
    workersVersionStatus = serializers.CharField()
    workerVersions = serializers.DictField(child=serializers.CharField())
