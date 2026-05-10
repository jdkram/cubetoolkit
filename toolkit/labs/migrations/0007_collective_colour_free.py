from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0006_collective_colour"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collective",
            name="colour",
            field=models.CharField(default="#343a40", max_length=7),
        ),
    ]
