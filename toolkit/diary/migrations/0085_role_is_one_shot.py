from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0084_cost_rider_and_sound_engineer_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="is_one_shot",
            field=models.BooleanField(
                default=False,
                help_text="One-shot roles are created on the fly for a specific showing "
                "and do not appear in the permanent roles list.",
            ),
        ),
    ]
