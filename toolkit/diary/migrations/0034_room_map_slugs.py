# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
from django.db import migrations

# Maps room names (as seeded) to their SVG floorplan element IDs.
ROOM_SLUGS = {
    "Cinema":       "room-cinema",
    "Venue Space":  "room-venue",
    "Café":         "room-cafe",
    "Meeting":      "room-meeting-room",
    "Dark Room":    "room-dark-room",
    "Print Room":   "room-screen-printing-room",
    "Workshop":     "room-workshop",
    "Green room":   "room-green-room",
}


def set_map_slugs(apps, schema_editor):
    Room = apps.get_model("diary", "Room")
    for name, slug in ROOM_SLUGS.items():
        Room.objects.filter(name=name, map_slug="").update(map_slug=slug)


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0033_alter_room_map_slug"),
    ]

    operations = [
        migrations.RunPython(set_map_slugs, migrations.RunPython.noop),
    ]
