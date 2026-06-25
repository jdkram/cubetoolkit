from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inductions", "0004_inductionssettings_default_max_signups"),
    ]

    operations = [
        migrations.AddField(
            model_name="inductionssettings",
            name="privacy_policy_url",
            field=models.CharField(
                blank=True,
                max_length=500,
                help_text="URL to your GDPR/privacy policy. Linked from the sign-up consent checkbox. Leave blank to omit the link.",
            ),
        ),
        migrations.AddField(
            model_name="inductionssettings",
            name="access_needs_intro_text",
            field=models.TextField(
                blank=True,
                help_text="Introductory paragraph on the 1:1 induction request form. Leave blank to use the default text.",
            ),
        ),
    ]
