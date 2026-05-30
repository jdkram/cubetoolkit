from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0018_remove_volunteer_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='volunteer',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('dormant', 'Dormant'),
                    ('retired', 'Retired'),
                    ('suspended', 'Suspended'),
                ],
                default='active',
                max_length=10,
            ),
        ),
    ]
