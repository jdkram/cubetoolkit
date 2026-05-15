# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
import django.db.models.deletion
from django.db import migrations, models


def backfill_room_bookings(apps, schema_editor):
    """For each Showing that had a room, create a single RoomBooking."""
    Showing = apps.get_model("diary", "Showing")
    RoomBooking = apps.get_model("diary", "RoomBooking")

    for showing in Showing.objects.filter(room__isnull=False).select_related(
        "event", "room"
    ):
        duration = showing.event.duration
        if duration is not None:
            import datetime

            end = showing.start + datetime.timedelta(
                hours=duration.hour, minutes=duration.minute
            )
        else:
            end = None
        RoomBooking.objects.create(
            showing=showing,
            room=showing.room,
            start=showing.start,
            end=end,
            notes="",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0031_event_hire_name"),
    ]

    operations = [
        # 1. Add map_slug to Room
        migrations.AddField(
            model_name="room",
            name="map_slug",
            field=models.SlugField(
                blank=True,
                default="",
                help_text="SVG element ID in the building floorplan (e.g. 'room-cinema'). Leave blank if not on the map.",
            ),
        ),
        # 2. Create RoomBooking table (while Showing.room still exists)
        migrations.CreateModel(
            name="RoomBooking",
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
                (
                    "showing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="room_bookings",
                        to="diary.showing",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to="diary.room",
                    ),
                ),
                ("start", models.DateTimeField()),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
            ],
            options={
                "db_table": "RoomBookings",
                "ordering": ["start"],
            },
        ),
        # 3. Backfill: copy existing showing.room into RoomBooking records
        migrations.RunPython(backfill_room_bookings, migrations.RunPython.noop),
        # 4. Remove Showing.room FK
        migrations.RemoveField(
            model_name="showing",
            name="room",
        ),
    ]
