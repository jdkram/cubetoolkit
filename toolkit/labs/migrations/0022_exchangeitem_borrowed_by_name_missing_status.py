from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0021_exchangeitem_borrowed_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangeitem",
            name="borrowed_by_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Free-text name for verbal/in-person loans. Shown instead of username if set.",
                max_length=128,
            ),
        ),
        migrations.AlterField(
            model_name="exchangeitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("on_loan", "On loan"),
                    ("claimed", "Claimed"),
                    ("all_gone", "All gone"),
                    ("missing", "Missing"),
                    ("withdrawn", "Withdrawn"),
                ],
                default="available",
                max_length=16,
            ),
        ),
    ]
