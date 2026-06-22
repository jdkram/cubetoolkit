from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0079_siteconfiguration_last_gasp_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="tmdb_api_key",
            field=models.CharField(
                blank=True,
                default="",
                max_length=256,
                verbose_name="TMDB API key",
                help_text=(
                    "API key for The Movie Database (TMDB). Used for film search and metadata import. "
                    "Generate or view your key at https://www.themoviedb.org/settings/api. "
                    "If set here, this takes precedence over the TMDB_API_KEY environment variable."
                ),
            ),
        ),
    ]
