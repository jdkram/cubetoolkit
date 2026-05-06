from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0022_rotatentry_role_protect"),
    ]

    operations = [
        migrations.AddField(
            model_name="showing",
            name="setup_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="showing",
            name="doors_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="showing",
            name="final_volunteer_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
