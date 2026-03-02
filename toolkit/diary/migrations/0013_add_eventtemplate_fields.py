from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0012_add_mediaitem_alt_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="eventtemplate",
            name="copy",
            field=models.TextField(blank=True, max_length=8192, null=True),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="copy_summary",
            field=models.TextField(blank=True, max_length=4096, null=True),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="terms",
            field=models.TextField(blank=True, max_length=4096, null=True),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="film_information",
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="private",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="outside_hire",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="eventtemplate",
            name="rota_notes",
            field=models.TextField(blank=True, default="", max_length=4096),
            preserve_default=False,
        ),
    ]
