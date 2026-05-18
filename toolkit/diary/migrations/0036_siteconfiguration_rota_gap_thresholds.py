from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0035_room_show_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="rota_gap_min_missing",
            field=models.PositiveSmallIntegerField(
                default=3,
                help_text=(
                    "Show the 'rota gaps' dashboard widget for showings with at least this many "
                    "unfilled required slots. Set to 0 to use only the percentage threshold."
                ),
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="rota_gap_min_pct",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    "Show the 'rota gaps' dashboard widget for showings where at least this "
                    "percentage of required slots are unfilled (0–100). Set to 0 to use only "
                    "the count threshold."
                ),
            ),
        ),
    ]
