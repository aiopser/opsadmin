"""An execution request and its replay response commit in one transaction."""
from functools import wraps
import hashlib
import hmac
import json
import re

from django.conf import settings
from django.db import transaction
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from apps.cmdb.crypto import decrypt_secret, encrypt_secret
from apps.jobs.models import ExecutionRequestKey
from common.api.responses import api_error_response


def execution_idempotent(handler):
    @wraps(handler)
    def wrapped(view, request, *args, **kwargs):
        key = request.headers.get("Idempotency-Key") or request.data.get(
            "executionRequestId"
        )
        if not key:
            return handler(view, request, *args, **kwargs)
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", key):
            return api_error_response("执行请求标识格式不正确", http_status=400)
        if request.headers.get("Idempotency-Key") and request.data.get(
            "executionRequestId"
        ) not in (None, key):
            return api_error_response("执行请求标识不一致", http_status=409)
        encoded = json.dumps(
            request.data,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode()
        digest = hmac.new(
            settings.SECRET_KEY.encode(), encoded, hashlib.sha256
        ).hexdigest()
        with transaction.atomic():
            record, _ = ExecutionRequestKey.objects.get_or_create(
                owner=request.user,
                key=key,
                path=request.path,
                defaults={"request_hash": digest},
            )
            record = ExecutionRequestKey.objects.select_for_update().get(pk=record.pk)
            if not hmac.compare_digest(record.request_hash, digest):
                return api_error_response("该执行请求标识已用于不同配置，请重新预览", http_status=409)
            if record.status_code:
                lookup = getattr(view, "lookup_url_kwarg", None) or getattr(
                    view, "lookup_field", "pk"
                )
                if kwargs.get(lookup) is not None:
                    # Data scope is checked inside get_object, so a replay
                    # must recheck it even though no new work is dispatched.
                    view.get_object()
            if record.status_code == 410:
                return api_error_response(
                    "该执行请求已处理，响应已归档，请在执行历史查看；如需再次执行请重新预览", http_status=410
                )
            if record.status_code:
                result = Response(
                    json.loads(decrypt_secret(record.response_encrypted)),
                    status=record.status_code,
                )
                result["Idempotency-Replayed"] = "true"
                return result
            result = handler(view, request, *args, **kwargs)
            if (
                result.status_code >= 400
                or not isinstance(result.data, dict)
                or result.data.get("code") not in ("00000", 0)
            ):
                record.delete()
                return result
            record.response_encrypted = encrypt_secret(
                JSONRenderer().render(result.data).decode()
            )
            record.status_code = result.status_code
            record.save(update_fields=["response_encrypted", "status_code"])
            return result

    return wrapped
