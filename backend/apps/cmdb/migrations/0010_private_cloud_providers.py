from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cmdb", "0009_explicit_gateway_only")]

    operations = [
        migrations.AlterField(
            model_name="assetsource",
            name="cloud_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("aliyun", "Alibaba Cloud"),
                    ("tencent", "Tencent Cloud"),
                    ("vmware", "VMware vSphere"),
                    ("openstack", "OpenStack"),
                    ("pve", "Proxmox VE"),
                ],
                default="",
                max_length=16,
            ),
        ),
    ]
