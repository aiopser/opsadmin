from django.db import migrations


def _unique_code(CommandAtom, base, legacy_id):
    candidate = base[:128]
    if not CommandAtom.objects.filter(code=candidate).exists():
        return candidate
    suffix = f".{legacy_id}"
    return f"{base[:128 - len(suffix)]}{suffix}"


def migrate_legacy_resources(apps, schema_editor):
    CommandAtom = apps.get_model("automation", "CommandAtom")
    CommandVersion = apps.get_model("automation", "CommandVersion")
    ModuleCatalog = apps.get_model("jobs", "ModuleCatalog")
    Playbook = apps.get_model("jobs", "Playbook")

    for item in ModuleCatalog.objects.all().iterator():
        if CommandVersion.objects.filter(
            command__resource_kind="module",
            content=item.value,
        ).exists():
            continue
        code = _unique_code(CommandAtom, f"module.{item.value}", item.id)
        command = CommandAtom.objects.create(
            name=item.label or item.value,
            code=code,
            category=item.group or "其他",
            resource_kind="module",
            description=item.description or "",
            status="published" if item.is_active else "disabled",
            risk_level="low",
        )
        CommandVersion.objects.create(
            command=command,
            version=1,
            status="published",
            command_type="ansible_module",
            content=item.value,
            argument_schema={"legacy_description": item.params or ""},
            default_vars={"module_args": item.default_args or ""},
            timeout_seconds=60,
            check_mode_supported=True,
        )

    for item in Playbook.objects.all().iterator():
        if CommandVersion.objects.filter(
            command__resource_kind="playbook",
            content=item.content or "",
        ).exists():
            continue
        code = _unique_code(CommandAtom, f"playbook.legacy.{item.id}", item.id)
        command = CommandAtom.objects.create(
            name=item.name,
            code=code,
            category="历史 Playbook",
            resource_kind="playbook",
            description=item.description or "",
            status="published",
            risk_level="low",
        )
        CommandVersion.objects.create(
            command=command,
            version=1,
            status="published",
            command_type="playbook",
            content=item.content or "",
            timeout_seconds=60,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0012_auto_20260812_1749"),
        ("jobs", "0022_domain_audit_event_domain"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_resources, migrations.RunPython.noop),
        migrations.DeleteModel(name="ModuleCatalog"),
        migrations.DeleteModel(name="Playbook"),
    ]
