from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0074_siteconfiguration_stats_training_tag_slugs_blank"),
    ]

    operations = [
        migrations.CreateModel(
            name="Film",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tmdb_id", models.IntegerField(blank=True, db_index=True, null=True, unique=True, verbose_name="TMDB ID", help_text="The Movie Database numeric ID. Leave blank for works not in TMDB.")),
                ("imdb_id", models.CharField(blank=True, max_length=20, verbose_name="IMDB ID", help_text="e.g. tt0036775")),
                ("media_type", models.CharField(choices=[("film", "Film"), ("tv", "TV show")], default="film", max_length=8)),
                ("title", models.CharField(max_length=500)),
                ("original_title", models.CharField(blank=True, max_length=500)),
                ("year", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("director", models.CharField(blank=True, max_length=256, help_text="Director(s) or TV creator(s), comma-separated if more than one.")),
                ("runtime_minutes", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("countries", models.CharField(blank=True, max_length=256, help_text="e.g. GB, US")),
                ("languages", models.CharField(blank=True, max_length=256, help_text="e.g. English, French")),
                ("tmdb_certificate", models.CharField(blank=True, max_length=16, verbose_name="Certificate (TMDB)", help_text="UK certificate as returned by TMDB.")),
                ("overview", models.TextField(blank=True, help_text="Plot summary from TMDB. Internal reference only — not shown publicly.")),
                ("tmdb_poster_path", models.CharField(blank=True, max_length=256)),
                ("tmdb_fetched_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True, help_text="Internal programmer notes about this title.")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["title", "year"],
            },
        ),
        migrations.AddField(
            model_name="event",
            name="film",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="screenings",
                to="diary.film",
                help_text="Structured film/TV metadata. Optional — link via the film search in the edit form.",
            ),
        ),
    ]
