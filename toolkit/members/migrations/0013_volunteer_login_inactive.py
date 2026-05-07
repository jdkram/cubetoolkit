# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0012_volunteer_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="volunteer",
            name="login_inactive",
            field=models.BooleanField(
                default=False,
                help_text="Flagged by the auto-dormancy check: this volunteer has not logged in recently. Cleared manually after follow-up.",
            ),
        ),
    ]
