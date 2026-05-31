from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0052_role_qualification_gate"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="general_training_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Show General Safety Training records and prompts across the volunteer list, "
                    "profile 'Key dates', and training report. Disable if your venue does not run "
                    "General Safety Training — role-specific training records remain available "
                    "regardless of this setting. The GST training type is also hidden from the "
                    "'add training record' form when disabled."
                ),
            ),
        ),
    ]
