from rest_framework import status
from rest_framework.response import Response

SUCCESS = "00000"
BAD_REQUEST = "A0400"
UNAUTHORIZED = "A0230"
REFRESH_TOKEN_INVALID = "A0231"
FORBIDDEN = "A0301"
NOT_FOUND = "A0404"
SERVER_ERROR = "B0001"


def api_response(code, data=None, msg=None, http_status=status.HTTP_200_OK):
    payload = {"code": code, "data": data, "msg": msg}
    return Response(payload, status=http_status)


def api_ok_response(data="success"):
    return api_response(
        code=SUCCESS, data=data, msg=None, http_status=status.HTTP_200_OK
    )


def api_error_response(
    message="error",
    code=BAD_REQUEST,
    http_status=status.HTTP_400_BAD_REQUEST,
    status=None,
):
    # Existing callers used status=..., keep that keyword working while moving
    # the project to real HTTP status codes plus frontend business codes.
    if status is not None:
        http_status = status
    return api_response(code=code, data=None, msg=message, http_status=http_status)
