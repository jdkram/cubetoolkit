#!/usr/bin/env python3
"""
Fix room data after migration from old s+s branch to master.

Maps old room names/colours to the new format defined in rooms.toml.
Updates room colours and is_primary flags, fixes case-sensitive names.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "toolkit.docker_settings_ss")
sys.path.insert(0, "/site")
django.setup()

from toolkit.diary.models import Room, Showing

# Mapping: old name -> new name, colour, is_primary
ROOM_MAPPING = {
    "Cinema": {
        "new_name": "Cinema",
        "colour": "#CC2200",  # vivid vermilion
        "is_primary": True,
    },
    "Venue Space": {
        "new_name": "Venue Space",
        "colour": "#0057B8",  # royal blue
        "is_primary": True,
    },
    "Café": {
        "new_name": "Café",
        "colour": "#FFD700",  # bright yellow
        "is_primary": True,
    },
    "External": {
        "new_name": "External",
        "colour": "#E0F5CC",  # faint lime green
        "is_primary": False,
    },
    "Meeting": {
        "new_name": "Meeting",
        "colour": "#DDD0FF",  # soft lavender
        "is_primary": False,
    },
    "Dark Room": {
        "new_name": "Dark Room",
        "colour": "#707070",  # dark grey
        "is_primary": False,
    },
    "Print Room": {
        "new_name": "Print Room",
        "colour": "#CCE8F8",  # cool sky blue
        "is_primary": False,
    },
    "workshop": {  # Note: lowercase in old data
        "new_name": "Workshop",  # Fixed: Title Case
        "colour": "#F2E4A8",  # warm cream/tan
        "is_primary": False,
    },
    "Green room": {
        "new_name": "Green room",
        "colour": "#74BB88",  # medium mint
        "is_primary": False,
    },
}


def fix_rooms():
    """Update room names, colours, and is_primary flags."""
    print("Fixing room data...")
    print()

    # First, handle the workshop -> Workshop rename (case change)
    # This is tricky because Django ORM might not see them as different
    try:
        old_workshop = Room.objects.get(name="workshop")
        # Check if "Workshop" already exists
        if Room.objects.filter(name="Workshop").exists():
            new_workshop = Room.objects.get(name="Workshop")
            print(f"Both 'workshop' and 'Workshop' exist. Merging...")
            # Move all showings from old to new
            showing_count = Showing.objects.filter(room=old_workshop).update(
                room=new_workshop
            )
            print(f"  Moved {showing_count} showings from 'workshop' to 'Workshop'")
            # Delete old room
            old_workshop.delete()
            print(f"  Deleted old 'workshop' room")
        else:
            # Just rename it
            print(f"Renaming 'workshop' -> 'Workshop'")
            old_workshop.name = "Workshop"
            old_workshop.save()
            print(f"  Renamed successfully")
    except Room.DoesNotExist:
        print("No 'workshop' room found (lowercase) - may have been renamed already")

    print()

    # Now update all rooms with correct colours and is_primary
    updated = 0
    for old_name, config in ROOM_MAPPING.items():
        try:
            room = Room.objects.get(name=config["new_name"])
            old_colour = room.colour
            old_is_primary = room.is_primary

            # Update fields
            room.colour = config["colour"]
            room.is_primary = config["is_primary"]
            room.save()

            print(f"Updated '{config['new_name']}':")
            print(f"  Colour: {old_colour} -> {config['colour']}")
            print(f"  is_primary: {old_is_primary} -> {config['is_primary']}")
            updated += 1

        except Room.DoesNotExist:
            print(f"WARNING: Room '{config['new_name']}' not found!")

    print()
    print(f"Updated {updated} rooms successfully")

    # Verify
    print()
    print("Current room configuration:")
    for room in Room.objects.all().order_by("-is_primary", "name"):
        primary_marker = " [PRIMARY]" if room.is_primary else ""
        print(f"  {room.name}: {room.colour}{primary_marker}")


def check_other_rooms():
    """Check if there are any rooms that don't match our mapping."""
    known_rooms = set(ROOM_MAPPING.keys()) | set(
        r["new_name"] for r in ROOM_MAPPING.values()
    )

    unknown = []
    for room in Room.objects.all():
        if room.name not in known_rooms:
            unknown.append(room.name)

    if unknown:
        print()
        print("WARNING: Found rooms not in mapping:")
        for name in unknown:
            showing_count = Showing.objects.filter(room__name=name).count()
            print(f"  - '{name}' ({showing_count} showings)")
        print("These may need manual handling or might be the 'Other rooms' issue")
    else:
        print()
        print("All rooms accounted for in mapping.")


if __name__ == "__main__":
    print("=" * 60)
    print("Room Data Migration Fix")
    print("=" * 60)
    print()

    # Show current state
    print("Current rooms before fix:")
    for room in Room.objects.all().order_by("id"):
        primary_marker = " [PRIMARY]" if room.is_primary else ""
        print(f"  ID {room.id}: {room.name} ({room.colour}){primary_marker}")
    print()

    # Apply fixes
    fix_rooms()
    check_other_rooms()

    print()
    print("Done!")
