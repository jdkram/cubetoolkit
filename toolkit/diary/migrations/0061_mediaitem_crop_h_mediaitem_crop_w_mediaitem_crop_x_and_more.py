from django.db import migrations, models


def _add_crop_columns(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        for col in ("crop_x", "crop_y", "crop_w", "crop_h"):
            schema_editor.execute(
                f"ALTER TABLE `MediaItems` ADD COLUMN IF NOT EXISTS `{col}` DOUBLE NULL;"
            )
    else:
        with conn.cursor() as cur:
            cur.execute("PRAGMA table_info(MediaItems)")
            media_cols = {r[1] for r in cur.fetchall()}
        for col in ("crop_x", "crop_y", "crop_w", "crop_h"):
            if col not in media_cols:
                schema_editor.execute(
                    f"ALTER TABLE MediaItems ADD COLUMN {col} REAL NULL;"
                )


def _remove_crop_columns(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        for col in ("crop_x", "crop_y", "crop_w", "crop_h"):
            schema_editor.execute(
                f"ALTER TABLE `MediaItems` DROP COLUMN IF EXISTS `{col}`;"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0060_mediaitem_bar_colour_siteconfiguration_thumbnail_crop"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="mediaitem",
                    name="crop_x",
                    field=models.FloatField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="mediaitem",
                    name="crop_y",
                    field=models.FloatField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="mediaitem",
                    name="crop_w",
                    field=models.FloatField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="mediaitem",
                    name="crop_h",
                    field=models.FloatField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunPython(_add_crop_columns, _remove_crop_columns),
            ],
        ),
        migrations.AlterField(
            model_name="mediaitem",
            name="bar_colour",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "If set, the programme grid thumbnail is padded with bars of "
                    "this colour before being cropped. Your original image is never "
                    "modified. Leave empty to use the crop box alone."
                ),
                max_length=7,
                verbose_name="Letterbox bar colour",
            ),
        ),
    ]
