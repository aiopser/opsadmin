"""
Credential secret encryption utility.

Uses Fernet (AES-128-CBC + HMAC-SHA256) derived from Django SECRET_KEY.
Secrets are stored as url-safe base64 tokens in the database.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_ENCRYPTED_PLACEHOLDER = "$encrypted$"


def _get_fernet() -> Fernet:
    """Derive a 32-byte url-safe base64 key from Django SECRET_KEY."""
    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret and return a Fernet token string."""
    if not plaintext:
        return ""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decrypt a Fernet token back to plaintext. Returns '' on failure."""
    if not token:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def mask_secret(token: str) -> str:
    """Return placeholder if a secret is stored, else empty string."""
    return _ENCRYPTED_PLACEHOLDER if token else ""
