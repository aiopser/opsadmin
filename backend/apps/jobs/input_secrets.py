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


def definition_input_values(instance, workflow_version, submitted=None):
    """Resolve an edit without ever treating the public mask as a new secret."""
    from rest_framework.exceptions import ValidationError

    previous = resolve_workflow_inputs(instance) if instance is not None else {}
    same_version = (
        instance is not None and instance.workflow_version_id == workflow_version.pk
    )
    if submitted is None:
        return previous if same_version else {}
    values = dict(submitted)
    for field in _workflow_input_fields(workflow_version):
        if not isinstance(field, dict) or field.get("type") != "secret":
            continue
        name = field.get("name")
        if values.get(name) == REDACTED_VALUE:
            if not same_version or previous.get(name) in (None, "", REDACTED_VALUE):
                raise ValidationError({"inputVars": f"秘密参数 {name} 需要重新填写"})
            values[name] = previous[name]
        elif name not in values and same_version and name in previous:
            values[name] = previous[name]
    return values


class ProtectedDefinitionInputsMixin:
    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if self.workflow_version_id and (
            fields is None
            or {"input_vars", "workflow_version", "workflow_version_id"}.intersection(
                fields
            )
        ):
            # Explicit plaintext/empty edits take precedence; only public masks
            # are resolved from the protected copy.
            protected = resolve_workflow_inputs(self)
            values = {
                name: protected.get(name) if value == REDACTED_VALUE else value
                for name, value in (self.input_vars or {}).items()
            }
            safe, encrypted = protect_workflow_inputs(self.workflow_version, values)
            self.input_vars = safe
            self.secret_input_vars_encrypted = encrypted
            if fields is not None:
                kwargs["update_fields"] = set(fields) | {
                    "input_vars",
                    "secret_input_vars_encrypted",
                }
        return super().save(*args, **kwargs)
