from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0017_founditem'),
    ]

    operations = [
        migrations.AddField(
            model_name='founditem',
            name='report_type',
            field=models.CharField(
                choices=[('found', 'Found item'), ('lost', 'Lost report')],
                default='found',
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name='founditem',
            name='reporter_contact',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Private contact details for the person who lost the item. Not shown in the list view.',
            ),
        ),
    ]
