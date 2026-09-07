from unittest.mock import patch

import pytest
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
def test_refresh_rejects_query_token(api_client, user):
    response = api_client.post(f"/api/v1/auth/refresh-token?refreshToken={RefreshToken.for_user(user)}")
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize("field", ["is_active", "job_status"])
def test_disabled_user_cannot_refresh(api_client, user, field):
    token = str(RefreshToken.for_user(user))
    setattr(user, field, False)
    user.save(update_fields=[field])
    response = api_client.post("/api/v1/auth/refresh-token", {"refreshToken": token}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_revokes_refresh(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    response = api_client.post("/api/v1/auth/logout", {"refreshToken": str(refresh)}, format="json")
    assert response.status_code == 200
    api_client.credentials()
    response = api_client.post("/api/v1/auth/refresh-token", {"refreshToken": str(refresh)}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_logout_cannot_revoke_another_user_token(api_client, user, django_user_model):
    other = django_user_model.objects.create_user(username="other")
    refresh = RefreshToken.for_user(other)
    api_client.force_authenticate(user)
    response = api_client.post("/api/v1/auth/logout", {"refreshToken": str(refresh)}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_login_does_not_expose_internal_error(api_client):
    with patch("common.auth.jwt.MyTokenSerializer.is_valid", side_effect=RuntimeError("internal-secret-marker")):
        response = api_client.post("/api/v1/auth/login", {"username": "test", "password": "test"})
    assert "internal-secret-marker" not in str(response.data)


def test_cors_rejects_unlisted_origin(api_client):
    response = api_client.options("/api/v1/auth/login", HTTP_ORIGIN="https://untrusted.example", HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert "Access-Control-Allow-Origin" not in response
