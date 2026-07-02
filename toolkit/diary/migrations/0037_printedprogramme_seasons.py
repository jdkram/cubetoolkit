from django.db import migrations, models


def _copy_start_to_end_month(apps, schema_editor):
    PrintedProgramme = apps.get_model("diary", "PrintedProgramme")
    PrintedProgramme.objects.update(end_month=models.F("start_month"))


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0036_v2"),
    ]

    operations = [
        migrations.RenameField(
            model_name="printedprogramme",
            old_name="month",
            new_name="start_month",
        ),
        migrations.AlterField(
            model_name="printedprogramme",
            name="start_month",
            field=models.DateField(editable=False),
        ),
        migrations.AddField(
            model_name="printedprogramme",
            name="end_month",
            field=models.DateField(editable=False, null=True),
        ),
        migrations.RunPython(
            code=_copy_start_to_end_month,
            reverse_code=_noop_reverse,
        ),
        migrations.AlterField(
            model_name="printedprogramme",
            name="end_month",
            field=models.DateField(editable=False),
        ),
        migrations.AddField(
            model_name="printedprogramme",
            name="thumbnail",
            field=models.ImageField(
                blank=True,
                editable=False,
                max_length=256,
                null=True,
                upload_to="printedprogramme_thumbnails",
            ),
        ),
    ]
