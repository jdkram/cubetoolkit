from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inductions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='inductionsignup',
            name='desired_username',
            field=models.CharField(
                blank=True,
                default='',
                help_text="If set, used as the volunteer's login username instead of auto-generating from name.",
                max_length=150,
            ),
            preserve_default=False,
        ),
    ]
