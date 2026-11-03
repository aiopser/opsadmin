from datetime import date, datetime
from decimal import Decimal


SENSITIVE_FIELD_NAMES = {"secret_ref", "encrypted_secret", "credentials_encrypted"}


def _to_audit_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def build_cmdb_audit_snapshot(instance):
    """Create a JSON-safe CMDB audit snapshot without retaining secret values."""
    snapshot = {}
    for field in instance._meta.fields:
        if field.name in SENSITIVE_FIELD_NAMES:
            snapshot[field.name] = {
                "configured": bool(getattr(instance, field.name, ""))
            }
            continue
        snapshot[field.name] = _to_audit_value(getattr(instance, field.attname))
    return snapshot
