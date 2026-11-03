"""Versioned, explicitly configured keys for private delivery artifacts."""
import json
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from .contracts import ProvisioningError


class StateKeyring:
    def __init__(self):
        self.keys = getattr(settings, "PROVISIONING_STATE_KEYS", {})
        self.active = getattr(settings, "PROVISIONING_STATE_ACTIVE_KEY_ID", "")
        if (
            not isinstance(self.keys, dict)
            or not self.active
            or self.active not in self.keys
        ):
            raise ProvisioningError("尚未配置 state 版本密钥环")
        try:
            for key_id, value in self.keys.items():
                if not isinstance(key_id, str) or not 1 <= len(key_id) <= 64:
                    raise ValueError()
                Fernet(value.encode())
        except (ValueError, TypeError, AttributeError):
            raise ProvisioningError("state 密钥配置无效") from None

    def encrypt(self, value):
        payload = json.dumps(value, ensure_ascii=False).encode()
        if len(payload) > 32 * 1024 * 1024:
            raise ProvisioningError("制品超过 32 MiB 限制")
        try:
            token = Fernet(self.keys[self.active].encode()).encrypt(payload).decode()
        except (ValueError, TypeError):
            raise ProvisioningError("state 密钥配置无效") from None
        return {"schema": 1, "keyId": self.active, "token": token}

    def decrypt(self, envelope):
        if not isinstance(envelope, dict) or envelope.get("schema") != 1:
            raise ProvisioningError("未知的制品加密格式")
        key_id = envelope.get("keyId")
        if not isinstance(key_id, str) or key_id not in self.keys:
            raise ProvisioningError("缺少备份使用的历史密钥")
        try:
            return json.loads(
                Fernet(self.keys[key_id].encode()).decrypt(envelope["token"].encode())
            )
        except (InvalidToken, ValueError, KeyError, TypeError, AttributeError):
            raise ProvisioningError("制品密钥或完整性校验失败") from None
