import logging

from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler
from common.redaction import redact_text, redact_value

from common.api.responses import (
    BAD_REQUEST,
    FORBIDDEN,
    NOT_FOUND,
    SERVER_ERROR,
    UNAUTHORIZED,
    api_error_response,
)

logger = logging.getLogger("drf_exception")


def _redact_validation_copy(message):
    """Keep DRF field-error structure but redact secret-shaped text.

    Key-level redaction would replace the whole copy of errors raised on
    secret-named fields (e.g. secret_ref) with a placeholder and hide the
    rejection reason from the user; validation copy is fixed policy text,
    and text-level redaction still guards secret-shaped substrings.
    """
    if isinstance(message, dict):
        return {key: _redact_validation_copy(value) for key, value in message.items()}
    if isinstance(message, (list, tuple)):
        return [_redact_validation_copy(item) for item in message]
    return redact_text(message)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, list):
            message = response.data[0]
        else:
            message = (
                response.data.get("detail")
                if response.data.get("detail")
                else response.data
            )
    else:
        message = "Internal server error"
    if isinstance(exc, (ValidationError, ParseError)):
        message = _redact_validation_copy(message)
    else:
        message = redact_value(message)
    logger.error("API error: %s", type(exc).__name__)

    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return api_error_response(
            message=message,
            code=UNAUTHORIZED,
            http_status=status.HTTP_401_UNAUTHORIZED,
        )
    if isinstance(exc, PermissionDenied):
        return api_error_response(
            message=message,
            code=FORBIDDEN,
            http_status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, NotFound):
        return api_error_response(
            message=message,
            code=NOT_FOUND,
            http_status=status.HTTP_404_NOT_FOUND,
        )
    if isinstance(exc, (ValidationError, ParseError)):
        return api_error_response(
            message=message,
            code=BAD_REQUEST,
            http_status=status.HTTP_400_BAD_REQUEST,
        )

    http_status = (
        response.status_code
        if response is not None
        else status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    code = BAD_REQUEST if http_status < 500 else SERVER_ERROR
    return api_error_response(message=message, code=code, http_status=http_status)
