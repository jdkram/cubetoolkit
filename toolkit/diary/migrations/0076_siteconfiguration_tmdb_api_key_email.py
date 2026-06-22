from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0075_film_model_and_event_film_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="tmdb_api_key_email",
            field=models.EmailField(
                blank=True,
                default="",
                max_length=254,
                verbose_name="TMDB API key contact email",
                help_text=(
                    "Email address of the account registered with The Movie Database (TMDB) that "
                    "owns the API key. For reference only — the API key itself is set via the "
                    "TMDB_API_KEY environment variable. Leave blank if TMDB integration is not in use."
                ),
            ),
        ),
    ]
