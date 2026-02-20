# Generated migration for adding description field to Role

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0008_remove_terms_from_event_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="description",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Guidance for volunteers about this role: what's involved, "
                "accessibility notes, links to guides, training requirements, etc.",
            ),
        ),
    ]
