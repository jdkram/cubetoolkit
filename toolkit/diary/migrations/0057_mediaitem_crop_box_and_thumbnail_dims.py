from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diary', '0056_siteconfiguration_collectives_mailing_list_signup_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediaitem',
            name='crop_x',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mediaitem',
            name='crop_y',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mediaitem',
            name='crop_w',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='mediaitem',
            name='crop_h',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='siteconfiguration',
            name='thumbnail_crop_width',
            field=models.PositiveIntegerField(
                default=600,
                verbose_name='Thumbnail crop width (px)',
                help_text=(
                    'Width of the cropped index thumbnail in pixels. '
                    'Default 600 px. '
                    'See thumbnail_crop_height for common ratios.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='siteconfiguration',
            name='thumbnail_crop_height',
            field=models.PositiveIntegerField(
                default=900,
                verbose_name='Thumbnail crop height (px)',
                help_text=(
                    'Height of the cropped index thumbnail in pixels. '
                    'Common ratios: 600 × 900 (2:3, film one-sheet — default), '
                    '600 × 600 (1:1 square), '
                    '600 × 450 (4:3, UK quad / lobby card), '
                    '600 × 400 (3:2 landscape). '
                    'Changing this does not regenerate existing thumbnails — '
                    'clear the diary/thumbs_cropped/ folder in MEDIA_ROOT to force a rebuild.'
                ),
            ),
        ),
    ]
