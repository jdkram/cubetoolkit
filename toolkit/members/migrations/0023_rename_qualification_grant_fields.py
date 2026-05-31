from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0022_qualification_volunteerqualification"),
    ]

    operations = [
        migrations.RenameField(
            model_name="volunteerqualification",
            old_name="awarded_on",
            new_name="granted_on",
        ),
        migrations.RenameField(
            model_name="volunteerqualification",
            old_name="awarded_by",
            new_name="granted_by",
        ),
        migrations.AlterField(
            model_name="volunteerqualification",
            name="granted_by",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Name of the person who recorded this (leave blank if self-recorded).",
                max_length=128,
            ),
        ),
    ]
