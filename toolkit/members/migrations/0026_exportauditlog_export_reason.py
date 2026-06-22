from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0025_volunteer_retention_exempt_and_last_gasp_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportauditlog",
            name="export_reason",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
    ]
