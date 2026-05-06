from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DonationItem",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128)),
                ("category", models.CharField(blank=True, default="", max_length=64)),
                ("status", models.CharField(
                    choices=[("wanted", "Wanted"), ("check_first", "Check first"), ("not_needed", "Not needed")],
                    default="wanted",
                    max_length=16,
                )),
                ("notes", models.TextField(blank=True, default="")),
                ("contact", models.CharField(
                    blank=True,
                    default="",
                    help_text="Contact for this item — leave blank to use the site default.",
                    max_length=128,
                )),
                ("display_order", models.IntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"db_table": "labs_donation_items", "ordering": ["category", "display_order", "name"]},
        ),
        migrations.CreateModel(
            name="Job",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=128)),
                ("description", models.TextField(blank=True, default="")),
                ("location", models.CharField(
                    blank=True,
                    default="",
                    help_text="Where the job needs to happen, e.g. 'Main hall', 'Kitchen'.",
                    max_length=128,
                )),
                ("skills", models.TextField(
                    blank=True,
                    default="",
                    help_text="What skills or tools are needed.",
                )),
                ("keyholder_required", models.BooleanField(default=False)),
                ("urgency", models.CharField(
                    choices=[("high", "Urgent"), ("medium", "Soon"), ("low", "Whenever")],
                    default="low",
                    max_length=16,
                )),
                ("posted_at", models.DateTimeField(auto_now_add=True)),
                ("done", models.BooleanField(default=False)),
                ("done_at", models.DateTimeField(blank=True, null=True)),
                ("posted_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="posted_jobs",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("claimed_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="claimed_jobs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "labs_jobs", "ordering": ["-done", "urgency", "-posted_at"]},
        ),
    ]
