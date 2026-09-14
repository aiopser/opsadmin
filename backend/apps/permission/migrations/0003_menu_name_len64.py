from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('permission', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='menu',
            name='name',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='Route name'),
        ),
    ]
