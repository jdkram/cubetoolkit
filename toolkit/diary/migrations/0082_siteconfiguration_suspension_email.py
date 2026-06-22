from django.db import migrations, models

_DEFAULT_BODY = (
    "Hi {name},\n\n"
    "This is to let you know that your volunteer account at {venue} has been suspended. "
    "Your login is currently disabled and you have been removed from upcoming shifts.\n\n"
    "If you have any questions or would like to discuss this, please get in touch.\n\n"
    "Best wishes,\n{venue}"
)


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0081_update_ticketsource_guidance"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="suspension_email_subject",
            field=models.CharField(
                blank=True,
                default="Your volunteer account at {venue}",
                max_length=300,
                verbose_name="Suspension email subject",
                help_text="Subject line for the email offered when suspending a volunteer. Supports {name} and {venue} variables.",
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="suspension_email_body",
            field=models.TextField(
                blank=True,
                default=_DEFAULT_BODY,
                verbose_name="Suspension email body",
                help_text="Body of the email offered when suspending a volunteer. Supports {name} and {venue} variables.",
            ),
        ),
    ]
