from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0038_siteconfiguration_bulletins"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="show_donations_in_public_nav",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Show a 'Donations wishlist' link in the public site navigation, "
                    "pointing at the labs donations list. Off by default."
                ),
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="banner_active",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Show a site-wide announcement banner at the top of every page "
                    "(public and toolkit) for important notices."
                ),
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="banner_level",
            field=models.CharField(
                max_length=10,
                default="info",
                choices=[
                    ("info", "Info (blue)"),
                    ("warning", "Warning (amber)"),
                    ("critical", "Critical (red)"),
                ],
                help_text="Colour scheme for the banner.",
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="banner_text",
            field=models.TextField(
                blank=True,
                default="",
                help_text=(
                    "Banner content. Plain text; line breaks are preserved. "
                    "Edit this and re-save to issue an updated notice — visitors who "
                    "previously dismissed the banner will see the new version."
                ),
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="banner_dismissible",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Allow visitors to dismiss the banner. Their choice is stored in "
                    "their browser only, and resets when the banner text changes."
                ),
            ),
        ),
    ]
