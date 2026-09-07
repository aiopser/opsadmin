from datetime import date, datetime
from decimal import Decimal


def _to_audit_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def build_automation_audit_snapshot(instance):
    """Create a JSON-safe snapshot of an automation resource."""
    return {
        field.name: _to_audit_value(getattr(instance, field.attname))
        for field in instance._meta.fields
    }
