from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0086_siteconfig_permission_fields"),
    ]

    operations = [
        migrations.RenameField(
            model_name="siteconfiguration",
            old_name="perm_diary_edit",
            new_name="perm_diary_read",
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="perm_diary_read",
            field=models.CharField(
                choices=[
                    ("volunteer", "All volunteers"),
                    ("programmer", "Programmer+"),
                    ("panopticon", "Panopticon only"),
                ],
                default="volunteer",
                help_text="Who can view the diary editing list (read-only for volunteers; event editing always requires Programmer+).",
                max_length=12,
                verbose_name="Diary — view diary list",
            ),
        ),
        migrations.RenameField(
            model_name="siteconfiguration",
            old_name="perm_programming_queue",
            new_name="perm_programming_queue_read",
        ),
        migrations.AlterField(
            model_name="siteconfiguration",
            name="perm_programming_queue_read",
            field=models.CharField(
                choices=[
                    ("volunteer", "All volunteers"),
                    ("programmer", "Programmer+"),
                    ("panopticon", "Panopticon only"),
                ],
                default="volunteer",
                help_text="Who can view the programming queue.",
                max_length=12,
                verbose_name="Diary — programming queue (view)",
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="perm_programming_queue_write",
            field=models.CharField(
                choices=[
                    ("volunteer", "All volunteers"),
                    ("programmer", "Programmer+"),
                    ("panopticon", "Panopticon only"),
                ],
                default="programmer",
                help_text="Who can approve, return, or skip events in the programming queue.",
                max_length=12,
                verbose_name="Diary — programming queue (change status)",
            ),
        ),
    ]
