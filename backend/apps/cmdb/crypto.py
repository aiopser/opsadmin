"""
Credential secret encryption utility.

Uses Fernet with an independent, explicitly configured key.
Secrets are stored as url-safe base64 tokens in the database.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_ENCRYPTED_PLACEHOLDER = "$encrypted$"


def _get_fernet() -> Fernet:
    return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.encode())


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret and return a Fernet token string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt current-key ciphertext; invalid ciphertext is an explicit error."""
    if not token:
        return ""
    return _get_fernet().decrypt(token.encode()).decode()


def mask_secret(token: str) -> str:
    """Return placeholder if a secret is stored, else empty string."""
    return _ENCRYPTED_PLACEHOLDER if token else ""
