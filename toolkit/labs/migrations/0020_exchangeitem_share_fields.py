# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
import django.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0019_exchange_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangeitem",
            name="quantity",
            field=models.CharField(
                blank=True,
                default="",
                help_text="How much is there? e.g. 'about 10kg', '3 trays', 'a big bag'. Share listings only.",
                max_length=64,
            ),
        ),
        migrations.AddField(
            model_name="exchangeitem",
            name="available_until",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Optional — show urgency. Useful for food that will go off. Share listings only.",
            ),
        ),
        migrations.AlterField(
            model_name="exchangeitem",
            name="listing_type",
            field=models.CharField(
                choices=[
                    ("lend", "🔧 Lend — borrow and return"),
                    ("give", "🎁 Give away — free to a good home"),
                    ("share", "🥔 Share — help yourself to some"),
                ],
                default="give",
                max_length=8,
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
                    ("withdrawn", "Withdrawn"),
                ],
                default="available",
                max_length=16,
            ),
        ),
    ]
