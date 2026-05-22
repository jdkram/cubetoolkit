from django.db import migrations, models


def split_dir_share_name(apps, schema_editor):
    Volunteer = apps.get_model("members", "Volunteer")
    # Map old enum → (listed, style). Anything other than "none" means listed.
    for vol in Volunteer.objects.all():
        old = getattr(vol, "dir_share_name", "none") or "none"
        vol.dir_share_listed = old != "none"
        vol.dir_share_name_style = "initial" if old == "initial" else "full"
        vol.save(update_fields=["dir_share_listed", "dir_share_name_style"])


def recombine_dir_share_name(apps, schema_editor):
    Volunteer = apps.get_model("members", "Volunteer")
    for vol in Volunteer.objects.all():
        if not vol.dir_share_listed:
            vol.dir_share_name = "none"
        else:
            vol.dir_share_name = vol.dir_share_name_style or "full"
        vol.save(update_fields=["dir_share_name"])


class Migration(migrations.Migration):

    # MariaDB doesn't allow schema changes inside a transaction with data migrations
    atomic = False

    dependencies = [
        ("members", "0014_volunteer_directory_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteer",
            name="dir_share_listed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="volunteer",
            name="dir_share_name_style",
            field=models.CharField(
                choices=[("full", "Full name"), ("initial", "First name + initial")],
                default="full",
                max_length=10,
            ),
        ),
        migrations.RunPython(split_dir_share_name, recombine_dir_share_name),
        migrations.RemoveField(
            model_name="volunteer",
            name="dir_share_name",
        ),
    ]
