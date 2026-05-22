from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0036_siteconfiguration_rota_gap_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="access_rider_guidance_url",
            field=models.URLField(
                blank=True,
                default="https://weareunlimited.org.uk/resource/creating-your-own-access-rider/",
                max_length=500,
                help_text="Link shown in the Access Rider section of the volunteer profile — guidance on writing an access rider. Leave blank to hide the link.",
            ),
        ),
    ]
