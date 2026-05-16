from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0034_room_map_slugs"),
    ]

    operations = [
        migrations.AddField(
            model_name="room",
            name="show_column",
            field=models.BooleanField(
                default=True,
                help_text="Show this room as its own column in the diary list view. Uncheck to bundle bookings into the 'Other rooms' column.",
            ),
        ),
    ]
