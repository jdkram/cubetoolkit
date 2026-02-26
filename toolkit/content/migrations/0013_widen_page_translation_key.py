# ai-written
# Migration to fix Wagtail 6 translation_key column overflow.
# On existing databases the column may be varchar(32), which is too narrow for
# 36-character UUIDs. Fresh installs with Wagtail 6.3 already have the right
# size, so this migration is a no-op for them.
#
# Uses RunPython with an INFORMATION_SCHEMA check so it is safe to run on
# both old and fresh databases.

from django.db import migrations


def widen_translation_key_if_needed(apps, schema_editor):
    """Widen wagtailcore_page.translation_key to varchar(36) if needed."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME   = 'wagtailcore_page'
              AND COLUMN_NAME  = 'translation_key'
            """
        )
        row = cursor.fetchone()
        if row is None:
            # Column does not exist — nothing to do. Should not happen given
            # the wagtailcore.0057 dependency, but be defensive.
            return
        current_length = row[0]
        if current_length is not None and current_length >= 36:
            # Already wide enough; fresh Wagtail 6.3 installs land here.
            return
        cursor.execute(
            """
            ALTER TABLE wagtailcore_page
            MODIFY COLUMN translation_key varchar(36) NOT NULL
            """
        )


def reverse_noop(apps, schema_editor):
    # Cannot safely narrow a column that may contain data; intentional no-op.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0012_alter_complexarticlepage_content"),
        # translation_key is created by 0055 and made NOT NULL by 0057.
        # Depend on 0057 so our ALTER runs after the column is in its final form.
        ("wagtailcore", "0057_page_locale_fields_notnull"),
    ]

    operations = [
        migrations.RunPython(
            widen_translation_key_if_needed,
            reverse_noop,
        ),
    ]
