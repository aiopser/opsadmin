"""Execution-time credential resolution."""

from pathlib import Path
import os
import stat
import tempfile
from typing import Any, Mapping

from apps.cmdb.models import CredentialRef


class CredentialProvider:
    def resolve(self, credential_id: int) -> Mapping[str, Any]:
        raise NotImplementedError


class DatabaseCredentialProvider(CredentialProvider):
    """Resolve connection variables from the CMDB credential ref.

    Supports hybrid storage:
    - encrypted_secret (inline, Fernet-encrypted in DB)
    - secret_ref (external: env:/file:/vault://)
    """

    def __init__(self, key_directory=None):
        self.key_directory = Path(key_directory) if key_directory else None

    def resolve(self, credential_id: int) -> Mapping[str, Any]:
        credential = CredentialRef.objects.get(id=credential_id)
        if not credential.is_active:
            raise ValueError("Credential is disabled")
        variables = dict((credential.metadata or {}).get("ansible_vars") or {})

        # Inject username and connection params from credential
        if credential.username:
            variables.setdefault("ansible_user", credential.username)
        if credential.connection_type == "winrm":
            variables.setdefault("ansible_connection", "winrm")
            variables.setdefault("ansible_winrm_transport", "ntlm")
            variables.setdefault("ansible_winrm_server_cert_validation", "ignore")

        # Resolve secret: prefer encrypted_secret, fallback to secret_ref
        secret = self._resolve_secret(credential)
        if secret:
            self._inject_secret(variables, credential, secret)
        return variables

    def _resolve_secret(self, credential: CredentialRef) -> str:
        """Resolve the actual secret value from encrypted storage or external ref."""
        # 1. Inline encrypted secret
        if credential.encrypted_secret:
            from apps.cmdb.crypto import decrypt_secret

            return decrypt_secret(credential.encrypted_secret)

        # 2. External reference
        secret_ref = credential.secret_ref or ""
        if secret_ref.startswith("env:"):
            env_name = secret_ref[4:]
            secret = os.environ.get(env_name)
            if not secret:
                raise ValueError(
                    f"Credential environment variable {env_name} is not configured."
                )
            return secret
        elif secret_ref.startswith("file:"):
            secret_path = Path(secret_ref[5:]).expanduser().resolve()
            if credential.type == CredentialRef.CredentialType.SSH_KEY:
                return str(secret_path)  # Return path for key files
            return secret_path.read_text(encoding="utf-8").strip()
        elif credential.type == CredentialRef.CredentialType.VAULT_REF:
            raise ValueError(
                "Vault credential resolution is not configured for this deployment."
            )
        return ""

    def _inject_secret(self, variables: dict, credential: CredentialRef, secret: str):
        """Inject resolved secret into Ansible variables based on credential type."""
        if credential.type == CredentialRef.CredentialType.PASSWORD:
            variables["ansible_password"] = secret
            # 不再强制 paramiko：默认 OpenSSH 连接支持 pipelining/ControlMaster，
            # 速度远优于 paramiko；前提是 worker 节点已安装 sshpass。
        elif credential.type == CredentialRef.CredentialType.SSH_KEY:
            # secret is either a file path (from file: ref) or raw key content
            if credential.secret_ref.startswith("file:") and not credential.encrypted_secret and Path(secret).is_file():
                variables["ansible_private_key_file"] = secret
            else:
                # Write key content to a temp file (INI inventory cannot hold multiline values)
                key_path = self._write_key_to_tmp(
                    secret, credential.id
                )
                variables["ansible_private_key_file"] = str(key_path)

    def _write_key_to_tmp(self, key_content: str, credential_id: int) -> Path:
        if self.key_directory is None:
            raise ValueError("Execution-owned key directory is required")
        descriptor, name = tempfile.mkstemp(prefix=f"cred-{credential_id}-", suffix=".key", dir=self.key_directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.chmod(name, stat.S_IRUSR | stat.S_IWUSR)
            stream.write(key_content)
        return Path(name)
