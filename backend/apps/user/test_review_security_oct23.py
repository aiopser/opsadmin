from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.permission.models import SystemConfig
from apps.user.serializers import UserProfileSerializer


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field", ["is_superuser", "is_staff", "groups", "user_permissions"]
)
def test_user_management_rejects_hidden_privilege_fields(user, field):
    serializer = UserProfileSerializer(
        user,
        data={field: True},
        partial=True,
        context={"request": SimpleNamespace(user=user)},
    )
    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.django_db
def test_password_change_invalidates_old_access_and_refresh(api_client, user):
    token = RefreshToken.for_user(user)
    user.set_password("new-test-password-123")
    user.save(update_fields=["password"])
    response = api_client.post(
        "/api/v1/auth/refresh-token", {"refreshToken": str(token)}, format="json"
    )
    assert response.status_code == 401
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    response = api_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_failure_policy_locks_and_recovers(api_client, user):
    SystemConfig.objects.create(
        config_name="Login max",
        config_key="security.login.max_failures",
        config_value="2",
    )
    for _ in range(2):
        assert (
            api_client.post(
                "/api/v1/auth/login",
                {"username": user.username, "password": "wrong"},
                format="json",
            ).status_code
            == 401
        )
    assert (
        api_client.post(
            "/api/v1/auth/login",
            {"username": user.username, "password": "test-pass-123"},
            format="json",
        ).status_code
        == 401
    )
    user.refresh_from_db()
    assert user.login_locked_until is not None
    user.login_locked_until = timezone.now() - timezone.timedelta(seconds=1)
    user.save(update_fields=["login_locked_until"])
    assert (
        api_client.post(
            "/api/v1/auth/login",
            {"username": user.username, "password": "test-pass-123"},
            format="json",
        ).status_code
        == 200
    )
    user.refresh_from_db()
    assert user.login_failure_count == 0


@pytest.mark.django_db
def test_first_password_change_blocks_business_apis_until_changed(api_client, user):
    from common.auth.jwt import MyTokenSerializer

    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    token = MyTokenSerializer.get_token(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    assert api_client.get("/api/v1/auth/me").status_code == 200
    assert api_client.get("/api/v1/tasks/runs").status_code == 403
    response = api_client.put(
        "/api/v1/users/password",
        {"oldPassword": "test-pass-123", "newPassword": "updated-password-123"},
        format="json",
    )
    assert response.status_code == 200, response.data
    user.refresh_from_db()
    assert not user.must_change_password
    assert api_client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_user_role_assignment_cannot_expand_job_data_scope(user):
    from apps.permission.models import Role
    from rest_framework.exceptions import PermissionDenied

    broad_role = Role.objects.create(
        name="broad-scope", code="broad", job_data_scope="all"
    )
    serializer = UserProfileSerializer(
        user,
        data={"roleIds": [broad_role.pk]},
        partial=True,
        context={"request": SimpleNamespace(user=user)},
    )
    with pytest.raises(PermissionDenied):
        serializer.is_valid(raise_exception=True)


@pytest.mark.django_db
def test_user_role_assignment_cannot_grant_unowned_permissions(user):
    from apps.permission.models import Permission, Role
    from rest_framework.exceptions import PermissionDenied

    permission = Permission.objects.create(
        code="review.unowned", path="/review/unowned", method="POST", type="api"
    )
    role = Role.objects.create(name="unowned-permission", code="unowned-permission")
    role.permission.add(permission)
    serializer = UserProfileSerializer(
        user,
        data={"roleIds": [role.pk]},
        partial=True,
        context={"request": SimpleNamespace(user=user)},
    )
    with pytest.raises(PermissionDenied):
        serializer.is_valid(raise_exception=True)


@pytest.mark.django_db
def test_password_reset_ignores_query_password_and_protects_superusers(
    api_client, user, django_user_model
):
    from unittest.mock import patch

    admin = django_user_model.objects.create_superuser(
        username="review-reset-admin", password="admin-old-password-123"
    )
    api_client.force_authenticate(admin)
    response = api_client.put(
        f"/api/v1/users/{user.pk}/password/reset?password=query-secret-password",
        {},
        format="json",
    )
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password("test-pass-123")
    api_client.force_authenticate(user)
    with patch("common.auth.rbac.verify_permission", return_value=(True, "")):
        response = api_client.put(
            f"/api/v1/users/{admin.pk}/password/reset",
            {"password": "attempted-admin-reset"},
            format="json",
        )
    assert response.status_code == 400
    admin.refresh_from_db()
    assert admin.check_password("admin-old-password-123")
