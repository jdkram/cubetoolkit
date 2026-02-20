# Migration to fix Wagtail 6 translation_key column overflow
# Wagtail 6 generates 36-char UUIDs with dashes, but MariaDB column was varchar(32)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0012_alter_complexarticlepage_content"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE wagtailcore_page
                MODIFY COLUMN translation_key varchar(36) NULL UNIQUE;
            """,
            reverse_sql="""
                ALTER TABLE wagtailcore_page
                MODIFY COLUMN translation_key varchar(32) NULL UNIQUE;
            """,
        ),
    ]
