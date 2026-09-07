"""Shared secret redaction; has no Django or business-model dependency."""

import re

REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEY_PARTS = (
    "api_key",
    "ansible_become_pass",
    "ansible_ssh_pass",
    "authorization",
    "credential",
    "passphrase",
    "passwd",
    "password",
    "private_key",
    "secret",
    "secret_ref",
    "ssh_key",
    "token",
    "vault",
)
SENSITIVE_KEY_PATTERN = "|".join(
    re.escape(part).replace("_", "[_-]") for part in SENSITIVE_KEY_PARTS
)
KEY_VALUE_CREDENTIAL_PATTERN = re.compile(
    rf"(?<![A-Za-z0-9])({SENSITIVE_KEY_PATTERN})(?![A-Za-z0-9])"
    rf"(\s*[=:]\s*)(?:(?:Bearer\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s,;]+))",
    re.IGNORECASE,
)
AUTHORIZATION_HEADER_PATTERN = re.compile(r"(?im)(\bauthorization\s*:\s*)[^\r\n]*")
JSON_QUOTED_CREDENTIAL_PATTERN = re.compile(
    rf'(?P<prefix>"[^"\r\n]*(?:{SENSITIVE_KEY_PATTERN})[^"\r\n]*"\s*:\s*)'
    r'"(?:\\.|[^"\\])*"',
    re.IGNORECASE,
)
URI_CREDENTIAL_PATTERN = re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s@]+@", re.IGNORECASE)

def redact_text(value: object) -> str:
    text = str(value or "")
    text = AUTHORIZATION_HEADER_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED_VALUE}",
        text,
    )
    text = JSON_QUOTED_CREDENTIAL_PATTERN.sub(
        rf'\g<prefix>"{REDACTED_VALUE}"',
        text,
    )
    text = KEY_VALUE_CREDENTIAL_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED_VALUE}",
        text,
    )
    return URI_CREDENTIAL_PATTERN.sub(rf"\1{REDACTED_VALUE}@", text)


def redact_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): REDACTED_VALUE if re.search(SENSITIVE_KEY_PATTERN, str(key), re.IGNORECASE) else redact_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
