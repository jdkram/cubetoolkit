from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0024_add_collective_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="exchangeitem",
            name="borrowed_by_contact",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Contact details provided by the borrower — visible only to the person who posted the listing.",
                max_length=256,
            ),
        ),
    ]
