# Generated for task 9.65 — Panopticon site configuration dashboard.
# Creates the SiteConfiguration singleton model and seeds the row from the
# current settings_*.py values, so existing behaviour is preserved on first
# deploy.

from django.conf import settings
from django.db import migrations, models

DEFAULT_FILMS_START_BANNER_TEXT = (
    "We don't show adverts or trailers, so please arrive promptly, as films "
    "start as soon as most people have arrived."
)


def _parse_images_start_date(value):
    if not value:
        return None
    import datetime

    try:
        return datetime.datetime.strptime(value, "%d %b %Y").date()
    except (ValueError, TypeError):
        return None


def seed_singleton(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    SiteConfiguration.objects.update_or_create(
        pk=1,
        defaults={
            "films_start_on_time": getattr(settings, "FILMS_START_ON_TIME", False),
            "films_start_on_time_banner_text": DEFAULT_FILMS_START_BANNER_TEXT,
            "rota_show_tags": getattr(settings, "ROTA_SHOW_TAGS", True),
            "rota_clear_email_prompt_enabled": getattr(
                settings, "ROTA_CLEAR_EMAIL_PROMPT_ENABLED", True
            ),
            "show_archive_images": getattr(settings, "SHOW_ARCHIVE_IMAGES", True),
            "images_start_date": _parse_images_start_date(
                getattr(settings, "IMAGES_START_DATE", None)
            ),
            "max_count_per_role": getattr(settings, "MAX_COUNT_PER_ROLE", 8),
            "programme_copy_summary_max_chars": getattr(
                settings, "PROGRAMME_COPY_SUMMARY_MAX_CHARS", 450
            ),
            "programme_event_terms_min_words": getattr(
                settings, "PROGRAMME_EVENT_TERMS_MIN_WORDS", 3
            ),
            "programme_media_max_size_mb": getattr(
                settings, "PROGRAMME_MEDIA_MAX_SIZE_MB", 5
            ),
            "mailout_details_days_ahead": getattr(
                settings, "MAILOUT_DETAILS_DAYS_AHEAD", 9
            ),
            "mailout_listings_days_ahead": getattr(
                settings, "MAILOUT_LISTINGS_DAYS_AHEAD", 14
            ),
            "membership_length_days": getattr(settings, "MEMBERSHIP_LENGTH_DAYS", 365),
            "default_training_expiry_months": getattr(
                settings, "DEFAULT_TRAINING_EXPIRY_MONTHS", 12
            ),
            "image_copyright_guidance_url": getattr(
                settings, "IMAGE_COPYRIGHT_GUIDANCE_URL", ""
            )
            or "",
            "alt_text_guidance_url": getattr(settings, "ALT_TEXT_GUIDANCE_URL", "")
            or "",
        },
    )


def noop_reverse(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    SiteConfiguration.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0018_alter_eventtemplaterole_count"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteConfiguration",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "films_start_on_time",
                    models.BooleanField(
                        default=False,
                        help_text="Show a banner on public event detail pages stating that films start on time.",
                    ),
                ),
                (
                    "films_start_on_time_banner_text",
                    models.TextField(
                        blank=True,
                        default=DEFAULT_FILMS_START_BANNER_TEXT,
                        help_text="The banner copy. Only shown when 'Films start on time' is enabled.",
                    ),
                ),
                (
                    "rota_show_tags",
                    models.BooleanField(
                        default=True,
                        help_text="Show event tag badges on the edit rota page.",
                    ),
                ),
                (
                    "rota_clear_email_prompt_enabled",
                    models.BooleanField(
                        default=True,
                        help_text="When clearing a rota slot, prompt the user to email the volunteer.",
                    ),
                ),
                (
                    "show_archive_images",
                    models.BooleanField(
                        default=True,
                        help_text=(
                            "If off, hide event images on the public site for events whose "
                            "showings all predate the 'Images start date' below. Volunteers "
                            "(authenticated users) always see images. Useful for taking "
                            "pre-archive imagery offline quickly (e.g. copyright issues)."
                        ),
                    ),
                ),
                (
                    "images_start_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        help_text=(
                            "Cutoff date for the 'Show archive images' setting above. Has no "
                            "effect unless that setting is off. Leave blank to disable hiding."
                        ),
                    ),
                ),
                (
                    "max_count_per_role",
                    models.PositiveSmallIntegerField(
                        default=8,
                        help_text="Maximum number of slots per role on a single showing's rota.",
                    ),
                ),
                (
                    "programme_copy_summary_max_chars",
                    models.PositiveSmallIntegerField(
                        default=450,
                        help_text="Maximum length of an event's copy summary (the listing blurb).",
                    ),
                ),
                (
                    "programme_event_terms_min_words",
                    models.PositiveSmallIntegerField(
                        default=3,
                        help_text="Minimum word count in an event's terms before it can be confirmed.",
                    ),
                ),
                (
                    "programme_media_max_size_mb",
                    models.PositiveSmallIntegerField(
                        default=5,
                        help_text="Maximum size in megabytes for an uploaded event image.",
                    ),
                ),
                (
                    "mailout_details_days_ahead",
                    models.PositiveSmallIntegerField(
                        default=9,
                        help_text="Days ahead to include detailed event copy in the members mailout.",
                    ),
                ),
                (
                    "mailout_listings_days_ahead",
                    models.PositiveSmallIntegerField(
                        default=14,
                        help_text="Days ahead to include listings in the members mailout.",
                    ),
                ),
                (
                    "membership_length_days",
                    models.PositiveSmallIntegerField(
                        default=365,
                        help_text="Default length of a new membership in days. Only used when membership expiry is enabled.",
                    ),
                ),
                (
                    "default_training_expiry_months",
                    models.PositiveSmallIntegerField(
                        default=12,
                        help_text="Months after which volunteer training records are considered expired.",
                    ),
                ),
                (
                    "image_copyright_guidance_url",
                    models.URLField(
                        blank=True,
                        default="",
                        max_length=500,
                        help_text="Link shown next to the image upload field — e.g. a Nextcloud doc on image rights.",
                    ),
                ),
                (
                    "alt_text_guidance_url",
                    models.URLField(
                        blank=True,
                        default="",
                        max_length=500,
                        help_text="Link shown next to the alt-text field — e.g. a guide to writing good alt text.",
                    ),
                ),
            ],
            options={
                "db_table": "SiteConfiguration",
                "verbose_name": "Site configuration",
                "verbose_name_plural": "Site configuration",
            },
        ),
        migrations.RunPython(seed_singleton, noop_reverse),
    ]
