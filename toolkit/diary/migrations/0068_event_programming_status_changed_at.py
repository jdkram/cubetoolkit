from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0067_merge_notes_into_programming_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="programming_status_changed_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                db_index=True,
                verbose_name="Status last changed",
                help_text="Set automatically whenever programming_status is updated.",
            ),
        ),
    ]
