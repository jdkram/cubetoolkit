from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("index", "0002_auto_20180223_2138"),
    ]

    operations = [
        migrations.AddField(
            model_name="indexlink",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Optional plain-text note shown below the link (e.g. login credentials, instructions). Visible only to logged-in volunteers.",
            ),
        ),
    ]
