"""
Replace the auto-managed EventTemplates_Roles M2M join table with an explicit
EventTemplateRole through model that adds a `count` field (default 1).

Sequence:
  1. Create EventTemplateRoles table (through model)
  2. Copy existing rows from EventTemplates_Roles with count=1
  3. Remove old auto-managed roles M2M field (drops EventTemplates_Roles table)
  4. Add new roles M2M field pointing at the through model (metadata only)
"""
from django.db import migrations, models
import django.db.models.deletion


def copy_roles_to_through_model(apps, schema_editor):
    db = schema_editor.connection.alias
    EventTemplate = apps.get_model("diary", "EventTemplate")
    EventTemplateRole = apps.get_model("diary", "EventTemplateRole")
    # At this point the old `roles` M2M (EventTemplates_Roles) is still present,
    # so we can iterate via the historical model accessor.
    for template in EventTemplate.objects.using(db).prefetch_related("roles").all():
        for role in template.roles.using(db).all():
            EventTemplateRole.objects.using(db).get_or_create(
                template=template, role=role, defaults={"count": 1}
            )


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0013_add_eventtemplate_fields"),
    ]

    operations = [
        # 1. Create the through model table
        migrations.CreateModel(
            name="EventTemplateRole",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("count", models.PositiveSmallIntegerField(default=1)),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="diary.role",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="role_slots",
                        to="diary.eventtemplate",
                    ),
                ),
            ],
            options={
                "db_table": "EventTemplateRoles",
                "ordering": ["role__name"],
                "unique_together": {("template", "role")},
            },
        ),
        # 2. Copy existing M2M rows into the through model with count=1
        migrations.RunPython(
            copy_roles_to_through_model,
            migrations.RunPython.noop,
        ),
        # 3. Remove the old auto-managed M2M (drops EventTemplates_Roles table)
        migrations.RemoveField(
            model_name="eventtemplate",
            name="roles",
        ),
        # 4. Add new roles M2M backed by the through model (no DB change needed)
        migrations.AddField(
            model_name="eventtemplate",
            name="roles",
            field=models.ManyToManyField(
                through="diary.EventTemplateRole", to="diary.role"
            ),
        ),
    ]
