import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0021_volunteer_event_mark"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rotaentry",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="diary.role",
            ),
        ),
    ]
