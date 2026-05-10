from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0005_collective_audit_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="collective",
            name="colour",
            field=models.CharField(
                choices=[
                    ("#343a40", "Slate"),
                    ("#1a5c72", "Teal"),
                    ("#7a3a2a", "Rust"),
                    ("#2d5a2a", "Forest"),
                    ("#523070", "Plum"),
                    ("#1a3a5c", "Navy"),
                    ("#4a5a20", "Olive"),
                    ("#6b4428", "Umber"),
                    ("#1a5c48", "Jade"),
                    ("#2d3a7a", "Indigo"),
                ],
                default="#343a40",
                max_length=7,
            ),
        ),
    ]
