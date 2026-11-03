import pytest
from cryptography.fernet import Fernet, InvalidToken
from django.test import override_settings

from apps.cmdb.crypto import decrypt_secret, encrypt_secret


def test_credentials_use_independent_key():
    with override_settings(CREDENTIAL_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        encrypted = encrypt_secret("test-password")
        with override_settings(SECRET_KEY="another-session-signing-key"):
            assert decrypt_secret(encrypted) == "test-password"


def test_invalid_ciphertext_is_explicit():
    with pytest.raises(InvalidToken):
        decrypt_secret("invalid-ciphertext")


@pytest.mark.django_db
def test_inline_secret_without_key_is_readable_400():
    """未配置加密 key 时，内联密钥保存应返回可读的校验错误而非 Fernet 500。"""
    from apps.cmdb.serializers import CredentialRefSerializer

    with override_settings(CREDENTIAL_ENCRYPTION_KEY=""):
        serializer = CredentialRefSerializer(
            data={
                "name": "no-key-cred",
                "type": "password",
                "scope": "global",
                "connection_type": "ssh",
                "username": "root",
                "secret": "plain-password",
            }
        )
        assert not serializer.is_valid()
        assert "DEVOPS_CREDENTIAL_ENCRYPTION_KEY" in str(serializer.errors)
