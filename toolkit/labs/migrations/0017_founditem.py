import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('labs', '0016_alter_consumableitem_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='FoundItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=200)),
                ('location_found', models.CharField(max_length=100)),
                ('found_on', models.DateField(default=datetime.date.today)),
                ('logged_by', models.CharField(max_length=100)),
                ('photo', models.ImageField(blank=True, upload_to='lost-and-found/')),
                ('status', models.CharField(
                    choices=[('unclaimed', 'Unclaimed'), ('claimed', 'Claimed'), ('disposed', 'Disposed')],
                    default='unclaimed',
                    max_length=12,
                )),
                ('claimed_by', models.CharField(blank=True, default='', max_length=200)),
                ('claimed_on', models.DateField(blank=True, null=True)),
                ('disposed_on', models.DateField(blank=True, null=True)),
                ('disposal_method', models.CharField(
                    blank=True,
                    choices=[('binned', 'Binned'), ('donated', 'Donated'), ('returned', 'Returned to owner'), ('other', 'Other')],
                    default='',
                    max_length=12,
                )),
                ('notes', models.TextField(blank=True, default='')),
            ],
            options={
                'db_table': 'labs_found_items',
                'ordering': ['-found_on', '-pk'],
            },
        ),
    ]
