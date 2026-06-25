from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inductions", "0006_inductionssettings_access_needs_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="inductionsignup",
            name="phone",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="inductionsignup",
            name="address",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="inductionsignup",
            name="postcode",
            field=models.CharField(blank=True, max_length=16),
        ),
    ]
