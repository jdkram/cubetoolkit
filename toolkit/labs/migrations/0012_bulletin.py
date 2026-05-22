from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0011_collective_invite_only"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Bulletin",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True,
                        help_text=(
                            "Leave blank to use the site default (bulletin_default_expiry_days). "
                            "Set explicitly to override."
                        ),
                        null=True,
                    ),
                ),
                (
                    "pinned",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "Pinned bulletins appear at the top of the board regardless of date. "
                            "Programmer+ only."
                        ),
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "labs_bulletins",
                "ordering": ["-pinned", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="BulletinRead",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                (
                    "bulletin",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="reads",
                        to="labs.bulletin",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "labs_bulletin_reads",
                "unique_together": {("bulletin", "user")},
            },
        ),
    ]
