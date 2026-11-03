"""Read explicit Module fields, including pre-migration execution snapshots."""
from copy import deepcopy


def module_name_for(version):
    return str(
        getattr(version, "module_name", "") or getattr(version, "content", "") or ""
    ).strip()


def legacy_parameter_docs(schema):
    if not isinstance(schema, dict):
        return []
    if "x-module-parameter-docs" in schema:
        notes = schema["x-module-parameter-docs"]
        return deepcopy(notes) if isinstance(notes, list) else []
    properties = schema.get("properties", schema)
    if not isinstance(properties, dict):
        return []
    return [
        {"name": name, "description": str(definition.get("description") or "")}
        for name, definition in properties.items()
        if name not in {"properties", "required"} and isinstance(definition, dict)
    ]


def parameter_docs_for(version):
    notes = getattr(version, "parameter_docs", None)
    if notes:
        return deepcopy(notes)
    return legacy_parameter_docs(getattr(version, "argument_schema", {}))
