from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0037_printedprogramme_seasons"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="printed_programme_archive_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Make the printed programme archive gallery publicly visible, "
                    "and add a link to it from the programme navigation. "
                    "Public URL: /programme/programme-archive/. Off by default."
                ),
            ),
        ),
    ]
