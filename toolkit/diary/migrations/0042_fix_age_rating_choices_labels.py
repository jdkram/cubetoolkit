from django.db import migrations

_OLD_BBFC_DEFAULTS = [
    {"value": "U", "label": "U — Universal"},
    {"value": "PG", "label": "PG — Parental Guidance"},
    {"value": "12A", "label": "12A — Cinema only, under 12s with adult"},
    {"value": "12", "label": "12"},
    {"value": "15", "label": "15"},
    {"value": "18", "label": "18"},
]

_NEW_BBFC_DEFAULTS = [
    {"value": "U", "label": "U (Universal)"},
    {"value": "PG", "label": "PG (Parental Guidance)"},
    {"value": "12A", "label": "12A (Cinema only, under 12s with adult)"},
    {"value": "12", "label": "12"},
    {"value": "15", "label": "15"},
    {"value": "18", "label": "18"},
]


def fix_labels(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    # Only touch rows still holding the original seeded defaults verbatim, so a
    # venue that's customised this list isn't overwritten.
    SiteConfiguration.objects.filter(age_rating_choices=_OLD_BBFC_DEFAULTS).update(
        age_rating_choices=_NEW_BBFC_DEFAULTS
    )


def revert_labels(apps, schema_editor):
    SiteConfiguration = apps.get_model("diary", "SiteConfiguration")
    SiteConfiguration.objects.filter(age_rating_choices=_NEW_BBFC_DEFAULTS).update(
        age_rating_choices=_OLD_BBFC_DEFAULTS
    )


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0041_alter_siteconfiguration_rota_show_tags"),
    ]

    operations = [
        migrations.RunPython(fix_labels, revert_labels),
    ]
