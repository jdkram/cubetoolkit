from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0015_add_event_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="beginner_friendly",
            field=models.BooleanField(
                default=False,
                help_text="Show the 🌱 beginner-friendly badge on the rota — a great first role for new volunteers.",
            ),
        ),
        migrations.AddField(
            model_name="role",
            name="not_wheelchair_accessible",
            field=models.BooleanField(
                default=False,
                help_text="Show the ♿ inaccessible badge on the rota — role may not be suitable for wheelchair users.",
            ),
        ),
    ]
