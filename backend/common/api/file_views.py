import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser
from drf_spectacular.utils import extend_schema, OpenApiParameter

from common.api.responses import api_error_response, api_ok_response
from common.api.views import StandardApiView
from common.api.schema import api_envelope_serializer, api_message_response
from common.api.schema_serializers import (
    FileUploadRequestSerializer,
    FileUploadResultSerializer,
)
from common.system_policy import validate_upload


class FileUploadApiView(StandardApiView):
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request={"multipart/form-data": FileUploadRequestSerializer},
        responses=api_envelope_serializer(
            "FileUploadResponse", FileUploadResultSerializer
        ),
    )
    def post(self, request):
        upload_file = request.FILES.get("file")
        if not upload_file:
            return api_error_response("请选择上传文件")

        validate_upload(upload_file)

        today = timezone.now()
        relative_dir = (
            Path("uploads")
            / today.strftime("%Y")
            / today.strftime("%m")
            / today.strftime("%d")
        )
        target_dir = Path(settings.MEDIA_ROOT) / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(upload_file.name).suffix
        filename = f"{uuid.uuid4().hex}{suffix}"
        target_path = target_dir / filename

        with target_path.open("wb+") as destination:
            for chunk in upload_file.chunks():
                destination.write(chunk)

        relative_path = (relative_dir / filename).as_posix()
        return api_ok_response(
            {
                "name": upload_file.name,
                "url": f"{settings.MEDIA_URL}{relative_path}",
            }
        )

    @extend_schema(
        parameters=[OpenApiParameter("filePath", str, description="相对媒体路径或媒体URL路径")],
        responses=api_message_response("FileDeleteResponse"),
    )
    def delete(self, request):
        file_path = request.query_params.get("filePath")
        if not file_path:
            return api_ok_response()

        media_url = getattr(settings, "MEDIA_URL", "/media/")
        normalized = file_path
        if normalized.startswith(media_url):
            normalized = normalized[len(media_url) :]
        normalized = normalized.lstrip("/\\")
        target_path = (Path(settings.MEDIA_ROOT) / normalized).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        if media_root not in target_path.parents and target_path != media_root:
            return api_error_response("文件路径非法")
        if target_path.exists() and target_path.is_file():
            target_path.unlink()
        return api_ok_response()
