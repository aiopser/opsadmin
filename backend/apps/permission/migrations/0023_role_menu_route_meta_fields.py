from django.db import migrations, models


def populate_role_codes(apps, schema_editor):
    """存量角色无 code 的，用 name 回填（name 唯一，可保证 code 唯一）。"""
    Role = apps.get_model("permission", "Role")
    for role in Role.objects.filter(code__isnull=True):
        role.code = (role.name or "")[:64] or None
        if role.code:
            role.save(update_fields=["code"])


class Migration(migrations.Migration):

    dependencies = [
        ("permission", "0022_menu_button_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="code",
            field=models.CharField(
                blank=True,
                help_text="角色编码，用于前端路由权限匹配（如 R_ADMIN）",
                max_length=64,
                null=True,
                unique=True,
                verbose_name="Role code",
            ),
        ),
        migrations.AddField(
            model_name="role",
            name="description",
            field=models.CharField(
                blank=True, default="", max_length=255, verbose_name="Role description"
            ),
        ),
        migrations.AddField(
            model_name="role",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Active"),
        ),
        migrations.AddField(
            model_name="role",
            name="home_path",
            field=models.CharField(
                blank=True,
                help_text="默认首页路由名（如 home）",
                max_length=128,
                null=True,
                verbose_name="Default home route",
            ),
        ),
        migrations.RunPython(populate_role_codes, migrations.RunPython.noop),
        migrations.AddField(
            model_name="menu",
            name="icon_type",
            field=models.CharField(
                choices=[("1", "Iconify"), ("2", "Local svg icon")],
                default="1",
                help_text="1=iconify 图标，2=本地 svg 图标",
                max_length=1,
                verbose_name="Icon type",
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="i18n_key",
            field=models.CharField(
                blank=True, max_length=128, null=True, verbose_name="I18n key"
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="href",
            field=models.CharField(
                blank=True, max_length=128, null=True, verbose_name="Outer link"
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="multi_tab",
            field=models.BooleanField(default=False, verbose_name="Multi tab"),
        ),
        migrations.AddField(
            model_name="menu",
            name="fixed_index_in_tab",
            field=models.IntegerField(
                blank=True, null=True, verbose_name="Fixed index in tab"
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="query",
            field=models.JSONField(
                blank=True,
                help_text='路由 query 参数，格式 [{"key": "id", "value": "1"}]',
                null=True,
                verbose_name="Route query",
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="constant",
            field=models.BooleanField(default=False, verbose_name="Constant route"),
        ),
        migrations.AddField(
            model_name="menu",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Active"),
        ),
    ]
