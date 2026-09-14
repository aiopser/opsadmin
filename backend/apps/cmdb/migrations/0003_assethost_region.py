from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cmdb', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='assethost',
            name='region',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
    ]
