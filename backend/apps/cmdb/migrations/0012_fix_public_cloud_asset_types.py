from django.db import migrations


def repair_public_cloud_types(apps, schema_editor):
    Host = apps.get_model("cmdb", "AssetHost")
    Host.objects.using(schema_editor.connection.alias).filter(
        asset_source__source_type="cloud",
        asset_source__cloud_provider__in=["aliyun", "tencent"],
        source_type="cloud",
        asset_type="server",
    ).exclude(source_id="").update(asset_type="cloud_instance")


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0011_cloud_import_preview")]
    operations = [migrations.RunPython(repair_public_cloud_types, migrations.RunPython.noop)]
