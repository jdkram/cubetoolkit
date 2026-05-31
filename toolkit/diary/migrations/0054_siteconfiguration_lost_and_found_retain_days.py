from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('diary', '0053_siteconfiguration_general_training_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='lost_and_found_retain_days',
            field=models.PositiveSmallIntegerField(
                default=60,
                help_text='Number of days to retain unclaimed lost and found items before flagging for disposal. Set to 0 to disable flagging.',
            ),
        ),
    ]
