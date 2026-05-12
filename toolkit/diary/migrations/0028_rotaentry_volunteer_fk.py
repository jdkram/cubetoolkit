import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0027_event_approval_metadata"),
        ("members", "0013_volunteer_login_inactive"),
    ]

    operations = [
        migrations.AddField(
            model_name="rotaentry",
            name="volunteer",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="rota_entries",
                to="members.volunteer",
            ),
        ),
    ]
