from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0026_role_wheelchair_accessible_site_config_dormancy"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="approval_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not recorded"),
                    ("meeting", "Approved at programming meeting"),
                    ("standing", "Standing / regular event — no meeting needed"),
                ],
                default="",
                max_length=16,
                verbose_name="Approval status",
                help_text="How this event entered the programme.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="approved_at_meeting_date",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Meeting date",
                help_text="Date of the programming meeting at which this was approved.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="meeting_name",
            field=models.CharField(
                blank=True,
                max_length=128,
                verbose_name="Meeting name",
                help_text="Optional identifier, e.g. 'Monday meeting'.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="meeting_minutes_url",
            field=models.URLField(
                blank=True,
                max_length=500,
                verbose_name="Minutes link",
                help_text="Optional link to the meeting minutes.",
            ),
        ),
    ]
