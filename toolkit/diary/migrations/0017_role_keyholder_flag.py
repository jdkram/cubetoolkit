from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0016_role_badge_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="keyholder_only",
            field=models.BooleanField(
                default=False,
                help_text="Show the 🔑 keyholder badge on the rota — slot must be filled by a trained venue keyholder.",
            ),
        ),
    ]
