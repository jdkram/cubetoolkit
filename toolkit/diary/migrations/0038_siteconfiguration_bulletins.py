from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0037_siteconfiguration_access_rider_guidance_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="bulletin_default_expiry_days",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text=(
                    "How many days a bulletin stays active if no explicit expiry is set. "
                    "Default is 30. Set to 0 to keep bulletins active indefinitely by default."
                ),
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="bulletin_guidance",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Guidance shown on the 'Post a bulletin' form. Use this to set local "
                    "conventions: what kinds of notices belong here, how to write them, "
                    "and examples of good and bad bulletins."
                ),
            ),
        ),
    ]
