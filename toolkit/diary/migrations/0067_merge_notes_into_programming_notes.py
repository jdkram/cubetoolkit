from django.db import migrations, models


def copy_notes_to_programming_notes(apps, schema_editor):
    Event = apps.get_model("diary", "Event")
    for event in Event.objects.exclude(notes__isnull=True).exclude(notes=""):
        if event.programming_notes:
            event.programming_notes = event.notes + "\n\n" + event.programming_notes
        else:
            event.programming_notes = event.notes
        event.save(update_fields=["programming_notes"])


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0066_siteconfiguration_confirm_label_and_more"),
    ]

    operations = [
        migrations.RunPython(
            copy_notes_to_programming_notes,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="event",
            name="notes",
        ),
    ]
