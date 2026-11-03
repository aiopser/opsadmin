from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cmdb', '0004_assetprobe'),
    ]

    operations = [
        migrations.RenameField(
            model_name='assethost',
            old_name='primary_ip',
            new_name='internal_ip',
        ),
        migrations.AlterField(
            model_name='assethost',
            name='internal_ip',
            field=models.GenericIPAddressField(db_index=True, verbose_name='内网IP'),
        ),
        migrations.AddField(
            model_name='assethost',
            name='external_ip',
            field=models.GenericIPAddressField(blank=True, db_index=True, null=True, verbose_name='外网IP'),
        ),
        migrations.AlterUniqueTogether(
            name='assethost',
            unique_together={('internal_ip', 'hostname')},
        ),
    ]
