# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
from django.db import migrations

ROOM_SLUGS = {
    "Kitchen":          "room-kitchen",
    "Snug":             "room-snug",
    "Projection Booth": "room-projection-booth",
    "Middle Corridor":  "room-middle-corridor",
}


def set_map_slugs(apps, schema_editor):
    Room = apps.get_model("diary", "Room")
    for name, slug in ROOM_SLUGS.items():
        Room.objects.filter(name=name, map_slug="").update(map_slug=slug)


class Migration(migrations.Migration):
    dependencies = [
        ("diary", "0048_siteconfiguration_breakeven_fields"),
    ]

    operations = [
        migrations.RunPython(set_map_slugs, migrations.RunPython.noop),
    ]
