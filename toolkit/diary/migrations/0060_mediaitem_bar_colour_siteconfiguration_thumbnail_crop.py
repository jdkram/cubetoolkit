from django.db import migrations, models


def _add_columns(apps, schema_editor):
    """Add the three new columns, guarding against pre-existing ones.

    On the dev MariaDB the columns already exist (crop-box feature 9.59 was
    implemented, its migration ran, then the code was reverted but the DB was
    never rolled back). MariaDB supports ADD COLUMN IF NOT EXISTS; SQLite
    (test runner) needs a manual existence check.
    """
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        schema_editor.execute(
            "ALTER TABLE `MediaItems` ADD COLUMN IF NOT EXISTS"
            " `bar_colour` varchar(7) NOT NULL DEFAULT '';"
        )
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` ADD COLUMN IF NOT EXISTS"
            " `thumbnail_crop_width` smallint unsigned NOT NULL DEFAULT 600;"
        )
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` ADD COLUMN IF NOT EXISTS"
            " `thumbnail_crop_height` smallint unsigned NOT NULL DEFAULT 900;"
        )
    else:
        # SQLite: inspect existing columns before adding.
        with conn.cursor() as cur:
            cur.execute("PRAGMA table_info(MediaItems)")
            media_cols = {r[1] for r in cur.fetchall()}
            cur.execute("PRAGMA table_info(SiteConfiguration)")
            cfg_cols = {r[1] for r in cur.fetchall()}
        if "bar_colour" not in media_cols:
            schema_editor.execute(
                "ALTER TABLE MediaItems ADD COLUMN bar_colour varchar(7) NOT NULL DEFAULT '';"
            )
        if "thumbnail_crop_width" not in cfg_cols:
            schema_editor.execute(
                "ALTER TABLE SiteConfiguration ADD COLUMN thumbnail_crop_width smallint NOT NULL DEFAULT 600;"
            )
        if "thumbnail_crop_height" not in cfg_cols:
            schema_editor.execute(
                "ALTER TABLE SiteConfiguration ADD COLUMN thumbnail_crop_height smallint NOT NULL DEFAULT 900;"
            )


def _remove_columns(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        schema_editor.execute(
            "ALTER TABLE `MediaItems` DROP COLUMN IF EXISTS `bar_colour`;"
        )
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` DROP COLUMN IF EXISTS `thumbnail_crop_width`;"
        )
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` DROP COLUMN IF EXISTS `thumbnail_crop_height`;"
        )
    # SQLite: DROP COLUMN not supported in older SQLite; skip reverse migration.


class Migration(migrations.Migration):
    """Add bar_colour to MediaItem and thumbnail_crop_width/height to SiteConfiguration."""

    dependencies = [
        ("diary", "0059_eventtag_description"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="mediaitem",
                    name="bar_colour",
                    field=models.CharField(
                        blank=True,
                        default="",
                        help_text=(
                            "If set, pad the uploaded image to the programme card ratio using bars of "
                            "this colour, instead of letting the browser crop it. "
                            "Pick a colour that matches your poster. "
                            "Only applied when a new image is uploaded."
                        ),
                        max_length=7,
                        verbose_name="Letterbox bar colour",
                    ),
                ),
                migrations.AddField(
                    model_name="siteconfiguration",
                    name="thumbnail_crop_width",
                    field=models.PositiveSmallIntegerField(
                        default=600,
                        help_text=(
                            "Width of the programme card image ratio (e.g. 2 for 2:3, or 600 for 600×900). "
                            "Used when padding uploaded images with letterbox bars and when generating typographic posters. "
                            "Default 600 (2:3 portrait)."
                        ),
                    ),
                ),
                migrations.AddField(
                    model_name="siteconfiguration",
                    name="thumbnail_crop_height",
                    field=models.PositiveSmallIntegerField(
                        default=900,
                        help_text=(
                            "Height of the programme card image ratio (e.g. 3 for 2:3, or 900 for 600×900). "
                            "Default 900 (2:3 portrait)."
                        ),
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(_add_columns, _remove_columns),
            ],
        ),
    ]
