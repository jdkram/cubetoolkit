from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0039_siteconfiguration_nav_and_banner"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="bulletin_post_permission",
            field=models.CharField(
                choices=[
                    ("all", "All volunteers"),
                    ("programmer", "Programmers and Panopticon"),
                    ("panopticon", "Panopticon only"),
                ],
                default="programmer",
                help_text="Who can post new bulletins.",
                max_length=12,
            ),
        ),
    ]
