from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0027_volunteer_dashboard_and_diary_prefs"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteer",
            name="suspension_reason",
            field=models.TextField(blank=True),
        ),
    ]
