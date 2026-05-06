from django.db import migrations, models


def populate_status_from_active(apps, schema_editor):
    Volunteer = apps.get_model("members", "Volunteer")
    Volunteer.objects.filter(active=False).update(status="retired")
    # active=True rows already default to 'active'


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0011_anonymisation_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteer",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("dormant", "Dormant"),
                    ("retired", "Retired"),
                ],
                default="active",
                max_length=10,
            ),
        ),
        migrations.RunPython(
            populate_status_from_active,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
