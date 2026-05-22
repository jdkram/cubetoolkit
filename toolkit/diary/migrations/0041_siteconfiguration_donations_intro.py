from django.db import migrations, models


_DEFAULT_INTRO = (
    "<p>The most valuable things you can give us are your time, energy, and ideas. "
    "If you want to get involved, the best place to start is by volunteering at events "
    "or joining one of our working groups.</p>"
    "<p>That said, we do sometimes need physical things too, and this page lists what's "
    "currently useful. Before bringing anything, please check the status: "
    "<strong>Wanted</strong> means yes please; <strong>Check first</strong> means it might "
    "work but talk to us first; <strong>Not needed</strong> means we're already well "
    "supplied or can't use it.</p>"
    "<p>One of our most precious resources as a DIY space is space itself. We share the "
    "building across a lot of different groups and uses, and it's much easier to add "
    "things than to remove them. Please don't drop anything off without checking first, "
    "even if it seems obviously useful.</p>"
)


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0040_siteconfiguration_bulletin_post_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="donations_intro",
            field=models.TextField(
                blank=True,
                default=_DEFAULT_INTRO,
                help_text="Introductory copy shown at the top of the public donations page. HTML.",
            ),
        ),
    ]
