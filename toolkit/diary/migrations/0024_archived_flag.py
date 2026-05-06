from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0023_showing_time_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="archived",
            field=models.BooleanField(
                default=False,
                help_text="Archived roles are hidden from normal use. Roles used in past rota entries cannot be permanently deleted.",
            ),
        ),
        migrations.AddField(
            model_name="eventtag",
            name="archived",
            field=models.BooleanField(
                default=False,
                help_text="Archived tags are hidden from normal use. Tags used on past events cannot be permanently deleted.",
            ),
        ),
    ]
