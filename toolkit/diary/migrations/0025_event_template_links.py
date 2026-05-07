from django.db import migrations, models
import django.db.models.deletion
import toolkit.diary.validators


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0024_archived_flag"),
    ]

    operations = [
        migrations.CreateModel(
            name="EventTemplateLink",
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
                ("label", models.CharField(max_length=80)),
                (
                    "url",
                    models.URLField(
                        max_length=500,
                        validators=[toolkit.diary.validators.validate_event_link_url],
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="links",
                        to="diary.eventtemplate",
                    ),
                ),
            ],
            options={
                "db_table": "EventTemplateLinks",
                "ordering": ["order", "pk"],
            },
        ),
    ]
