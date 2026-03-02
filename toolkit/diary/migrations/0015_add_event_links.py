from django.db import migrations, models
import django.db.models.deletion
import toolkit.diary.validators


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0014_eventtemplate_role_counts"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventLink",
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
                    "label",
                    models.CharField(
                        help_text="Short name shown on the link chip, e.g. 'Event folder' or 'Crew chat'.",
                        max_length=80,
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        max_length=500,
                        validators=[toolkit.diary.validators.validate_event_link_url],
                    ),
                ),
                (
                    "order",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Display order (lower numbers first).",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="diary.event",
                    ),
                ),
            ],
            options={
                "db_table": "EventLinks",
                "ordering": ["order", "pk"],
            },
        ),
    ]
