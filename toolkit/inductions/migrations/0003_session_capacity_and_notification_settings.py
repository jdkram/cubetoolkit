from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inductions", "0002_inductionsignup_desired_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="inductionsession",
            name="max_signups",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Maximum number of sign-ups allowed. Leave blank for unlimited.",
            ),
        ),
        migrations.AlterField(
            model_name="inductionssettings",
            name="organiser_notification_email",
            field=models.EmailField(
                default="inductions@example.com",
                help_text=(
                    "Email address that receives organiser notifications (new 1:1 request, "
                    "session full, etc.). Set this to a real address before going live."
                ),
                max_length=254,
            ),
        ),
        migrations.AddField(
            model_name="inductionssettings",
            name="notify_on_each_signup",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Also send a notification for every new sign-up, not just when a session reaches capacity. "
                    "Useful for small or closely-watched sessions."
                ),
            ),
        ),
    ]
