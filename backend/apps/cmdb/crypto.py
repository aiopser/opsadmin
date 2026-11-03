"""
Credential secret encryption utility.

Uses Fernet with an independent, explicitly configured key.
Secrets are stored as url-safe base64 tokens in the database.
"""

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_ENCRYPTED_PLACEHOLDER = "$encrypted$"


def _get_fernet() -> Fernet:
    key = settings.CREDENTIAL_ENCRYPTION_KEY
    if not key:
        # 未配置时 Fernet("") 会抛难以定位的裸 ValueError，这里给出可操作的指引
        raise ImproperlyConfigured(
            "CREDENTIAL_ENCRYPTION_KEY is not configured. Set the "
            "DEVOPS_CREDENTIAL_ENCRYPTION_KEY environment variable "
            '(generate with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())")'
        )
    return Fernet(key.encode())


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
