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
