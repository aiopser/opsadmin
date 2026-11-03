from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from rest_framework.exceptions import AuthenticationFailed

from apps.user.serializers import UserProfileUpdateSerializer
from common.auth.jwt import JWTAuthentication, MyTokenSerializer


@pytest.mark.django_db
def test_stale_profile_update_cannot_restore_password_and_old_session(user):
    old_token = MyTokenSerializer.get_token(user).access_token
    stale = type(user).objects.get(pk=user.pk)
    fresh = type(user).objects.get(pk=user.pk)
    fresh.set_password("new-password-after-reset-123")
    fresh.save(update_fields=["password"])
    initial_version = fresh.auth_version
    edit = UserProfileUpdateSerializer(
        stale, data={"name": "Concurrent profile"}, partial=True
    )
    assert edit.is_valid(), edit.errors
    edit.save()
    fresh.refresh_from_db()
    assert (
        fresh.auth_version == initial_version
    ), "stale profile write restored old auth_version"
    assert fresh.check_password(
        "new-password-after-reset-123"
    ), "stale profile write restored old password"
    auth = JWTAuthentication()
    auth.request_path = "/api/v1/auth/me"
    with pytest.raises(AuthenticationFailed):
        auth.get_user(old_token)


@pytest.mark.django_db
def test_password_hash_upgrade_cannot_clear_first_password_change(user):
    encoded = PBKDF2PasswordHasher().encode(
        "test-pass-123", "review-salt", iterations=1
    )
    type(user).objects.filter(pk=user.pk).update(
        password=encoded, must_change_password=True
    )
    user.refresh_from_db()
    assert user.check_password("test-pass-123")
    user.refresh_from_db()
    assert (
        user.must_change_password
    ), "automatic password hash upgrade removed the initial password gate"


@pytest.mark.django_db
def test_password_hash_upgrade_cas_cannot_undo_concurrent_password_reset(user):
    encoded = PBKDF2PasswordHasher().encode(
        "test-pass-123", "review-salt", iterations=1
    )
    type(user).objects.filter(pk=user.pk).update(password=encoded)
    user.refresh_from_db()
    original = PBKDF2PasswordHasher.verify

    def reset_during_verification(hasher, raw_password, encoded_password):
        valid = original(hasher, raw_password, encoded_password)
        if encoded_password == encoded:
            newer = type(user).objects.get(pk=user.pk)
            newer.set_password("reset-won-before-hash-upgrade-123")
            newer.save(update_fields=["password"])
        return valid

    with patch.object(PBKDF2PasswordHasher, "verify", reset_during_verification):
        assert not user.check_password("test-pass-123")
    user.refresh_from_db()
    assert user.check_password("reset-won-before-hash-upgrade-123")


@pytest.mark.django_db
def test_user_create_and_reset_keep_password_gate_and_revoke_old_token(
    django_user_model,
):
    from rest_framework.test import APIClient

    actor = django_user_model.objects.create_superuser(username="review-create-admin")
    client = APIClient()
    client.force_authenticate(actor)
    created_response = client.post(
        "/api/v1/users",
        {
            "username": "created-with-password-gate",
            "name": "Created account",
            "email": "created@example.test",
            "phone": "12345678901",
            "password": "Initial-test-password-123!",
        },
        format="json",
    )
    assert created_response.status_code == 200, created_response.data
    created = django_user_model.objects.get(username="created-with-password-gate")
    assert created.must_change_password and created.check_password(
        "Initial-test-password-123!"
    )
    previous_version = created.auth_version
    token = MyTokenSerializer.get_token(created).access_token
    reset_response = client.put(
        f"/api/v1/users/{created.pk}/password/reset",
        {"password": "Reset-test-password-456!"},
        format="json",
    )
    assert reset_response.status_code == 200, reset_response.data
    created.refresh_from_db()
    assert created.auth_version == previous_version + 1
    assert created.must_change_password and created.check_password(
        "Reset-test-password-456!"
    )
    old_session = APIClient()
    old_session.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    assert old_session.get("/api/v1/auth/me").status_code == 401
