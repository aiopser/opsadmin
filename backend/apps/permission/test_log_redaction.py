import pytest

from apps.permission.models import OperationLog
from common.exception import custom_exception_handler


@pytest.mark.django_db
def test_auth_request_secrets_are_absent_from_operation_log(api_client):
    secret = "test-secret-marker-unique"
    api_client.post(
        f"/api/v1/auth/refresh-token?refreshToken={secret}",
        {"refreshToken": secret, "password": secret},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {secret}",
    )
    assert OperationLog.objects.exists()
    assert secret not in str(list(OperationLog.objects.values()))


def test_unhandled_exception_never_exposes_internal_message(caplog):
    response = custom_exception_handler(RuntimeError("internal-secret-marker"), {})
    assert response.status_code == 500
    assert "internal-secret-marker" not in str(response.data)
    assert "internal-secret-marker" not in caplog.text
