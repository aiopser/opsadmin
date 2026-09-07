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

from common.api.responses import (
    BAD_REQUEST,
    FORBIDDEN,
    NOT_FOUND,
    SERVER_ERROR,
    UNAUTHORIZED,
    api_error_response,
)

logger = logging.getLogger("drf_exception")


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
        message = f"Exception: {exc}"
    logger.error(message)

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
