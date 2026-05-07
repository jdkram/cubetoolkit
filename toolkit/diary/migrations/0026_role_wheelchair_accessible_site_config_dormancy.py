# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0025_event_template_links"),
    ]

    operations = [
        # Rename: not_wheelchair_accessible → wheelchair_accessible (semantics inverted).
        # Old field: True = role is NOT accessible (show a warning badge).
        # New field: True = role has been explicitly reviewed and confirmed accessible.
        # Because no existing roles have been through a proper accessibility review,
        # all are reset to False regardless of their prior value.
        migrations.RenameField(
            model_name="role",
            old_name="not_wheelchair_accessible",
            new_name="wheelchair_accessible",
        ),
        migrations.RunSQL(
            sql="UPDATE `Roles` SET wheelchair_accessible = 0",
            reverse_sql="UPDATE `Roles` SET wheelchair_accessible = 0",
        ),
        migrations.AlterField(
            model_name="role",
            name="wheelchair_accessible",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Show the ♿ accessible badge on the rota — "
                    "someone has specifically reviewed this role and confirmed it is suitable for wheelchair users."
                ),
            ),
        ),
        # Add configurable dormancy threshold to site configuration.
        migrations.AddField(
            model_name="siteconfiguration",
            name="volunteer_dormancy_months",
            field=models.PositiveSmallIntegerField(
                default=24,
                help_text=(
                    "Mark active volunteers as Dormant if they have not logged in for this many months. "
                    "Set to 0 to never auto-enforce dormancy. "
                    "Run the 'auto_dormancy' management command periodically (e.g. via cron) to apply this rule."
                ),
            ),
        ),
    ]
