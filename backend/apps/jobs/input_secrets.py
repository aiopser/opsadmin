import json

from apps.cmdb.crypto import decrypt_secret, encrypt_secret


REDACTED_VALUE = "[REDACTED]"


def _workflow_input_fields(workflow_version):
    schema = getattr(workflow_version, "input_schema", None) or []
    if isinstance(schema, dict):
        schema = schema.get("fields") or []
    return schema if isinstance(schema, list) else []


def protect_workflow_inputs(workflow_version, input_vars):
    safe_values = dict(input_vars or {})
    secret_values = {}
    secret_names = {
        str(field.get("name") or "").strip()
        for field in _workflow_input_fields(workflow_version)
        if isinstance(field, dict) and field.get("type") == "secret"
    }
    secret_names.discard("")
    for name in secret_names:
        if name not in safe_values or safe_values[name] in (None, ""):
            continue
        secret_values[name] = safe_values[name]
        safe_values[name] = REDACTED_VALUE
    encrypted = (
        encrypt_secret(
            json.dumps(secret_values, ensure_ascii=False, separators=(",", ":"))
        )
        if secret_values
        else ""
    )
    return safe_values, encrypted


def resolve_workflow_inputs(run):
    values = dict(run.input_vars or {})
    encrypted = getattr(run, "secret_input_vars_encrypted", "") or ""
    if not encrypted:
        return values
    decrypted = decrypt_secret(encrypted)
    if not decrypted:
        return values
    try:
        secret_values = json.loads(decrypted)
    except (TypeError, ValueError):
        return values
    if isinstance(secret_values, dict):
        values.update(secret_values)
    return values
