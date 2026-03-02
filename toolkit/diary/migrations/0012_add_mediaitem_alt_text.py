from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diary', '0011_add_room_is_primary'),
    ]

    operations = [
        migrations.AddField(
            model_name='mediaitem',
            name='alt_text',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Describe the image for screen readers and when images fail to load. '
                    'E.g. "People sitting in an outdoor cinema under a night sky."'
                ),
                max_length=255,
                verbose_name='Alt text',
            ),
        ),
    ]
