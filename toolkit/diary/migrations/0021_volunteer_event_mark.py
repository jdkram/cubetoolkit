import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0020_event_terms_revision"),
        ("members", "0010_make_email_mandatory"),
    ]

    operations = [
        migrations.CreateModel(
            name="VolunteerEventMark",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "mark_type",
                    models.CharField(
                        choices=[("star", "Star"), ("shadow", "Shadow")], max_length=10
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="volunteer_marks",
                        to="diary.event",
                    ),
                ),
                (
                    "volunteer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="event_marks",
                        to="members.volunteer",
                    ),
                ),
            ],
            options={
                "unique_together": {("volunteer", "event")},
            },
        ),
    ]
