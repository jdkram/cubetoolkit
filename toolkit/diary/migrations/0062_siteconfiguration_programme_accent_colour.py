from django.db import migrations, models


def _add_column(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` ADD COLUMN IF NOT EXISTS"
            " `programme_accent_colour` varchar(7) NOT NULL DEFAULT '#e91e8c';"
        )
    else:
        with conn.cursor() as cur:
            cur.execute("PRAGMA table_info(SiteConfiguration)")
            existing = {r[1] for r in cur.fetchall()}
        if "programme_accent_colour" not in existing:
            schema_editor.execute(
                "ALTER TABLE SiteConfiguration ADD COLUMN"
                " programme_accent_colour varchar(7) NOT NULL DEFAULT '#e91e8c';"
            )


def _remove_column(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor == "mysql":
        schema_editor.execute(
            "ALTER TABLE `SiteConfiguration` DROP COLUMN IF EXISTS `programme_accent_colour`;"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0061_mediaitem_crop_h_mediaitem_crop_w_mediaitem_crop_x_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="siteconfiguration",
                    name="programme_accent_colour",
                    field=models.CharField(
                        default="#e91e8c",
                        help_text=(
                            "The primary brand colour used in the public programme (hex, e.g. #e91e8c). "
                            "Shown as a suggested bar colour when editing event images."
                        ),
                        max_length=7,
                        verbose_name="Programme accent colour",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(_add_column, _remove_column),
            ],
        ),
    ]
