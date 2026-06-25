from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inductions", "0003_session_capacity_and_notification_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="inductionssettings",
            name="default_max_signups",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Default maximum sign-ups for group induction sessions. "
                    "Leave blank for no site-wide cap. "
                    "Individual sessions can override this with their own limit."
                ),
            ),
        ),
    ]
