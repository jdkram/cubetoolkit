#!/usr/bin/env python3
"""
Handle orphaned showings after room merge issues.

This script helps fix showings that lost their room assignments during migration.
Run this after fix_rooms_after_migration.py if you have orphaned showings.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "toolkit.docker_settings_ss")
sys.path.insert(0, "/site")
django.setup()

from toolkit.diary.models import Room, Showing

# Mapping: Event template name -> suggested room
TEMPLATE_ROOM_MAP = {
    "Café": "Café",
    "Volunteer Induction": "Meeting",
    "Meeting": "Meeting",
    "Workshop": "Workshop",
    "Exhibition": "Venue Space",
    "Losing the Plot Film Retreat": "Cinema",
    "Party": "Venue Space",
    "Build": "Venue Space",
    "Talk": "Venue Space",
    "Drop-in": "Venue Space",
    "Conference": "Meeting",
    "Training": "Meeting",
    "Cleaning Session": "Venue Space",
    # Radio shows were online/external events during COVID
    "Radio": "External",
    # Gigs and club nights happen in Venue Space
    "Complex gig": "Venue Space",
    "Club Night": "Venue Space",
    # Multiform festival events - usually Venue Space
    "Multiform Festival": "Venue Space",
    # Film templates usually go in Cinema
    "Film (35mm)": "Cinema",
    "Film (DCP)": "Cinema",
    "Film (DVD)": "Cinema",
    "Film (16/8mm)": "Cinema",
}


def analyze_orphaned_showings():
    """Show analysis of orphaned showings."""
    orphaned = Showing.objects.filter(room__isnull=True)
    total = orphaned.count()

    print(f"Orphaned showings: {total}")
    print()

    if total == 0:
        print("No orphaned showings found. You're all set!")
        return

    # Count by template
    templates = {}
    for s in orphaned:
        template_name = s.event.template.name if s.event.template else "No Template"
        templates[template_name] = templates.get(template_name, 0) + 1

    print("Breakdown by event template:")
    for t, count in sorted(templates.items(), key=lambda x: -x[1]):
        suggested = TEMPLATE_ROOM_MAP.get(t, "Unknown")
        print(f"  {t}: {count} (suggested: {suggested})")

    print()
    print("Recent orphaned showings:")
    for s in orphaned.order_by("-start")[:10]:
        template = s.event.template.name if s.event.template else "No Template"
        print(f"  {s.start.date()}: {s.event.name[:50]} ({template})")


def fix_orphaned_showings(dry_run=True):
    """Assign rooms to orphaned showings based on event templates."""
    orphaned = Showing.objects.filter(room__isnull=True)

    if dry_run:
        print("DRY RUN - No changes will be made")
        print()

    fixed = 0
    unknown = 0

    for showing in orphaned:
        template_name = showing.event.template.name if showing.event.template else None
        suggested_room_name = TEMPLATE_ROOM_MAP.get(template_name)

        if suggested_room_name:
            try:
                room = Room.objects.get(name=suggested_room_name)
                if not dry_run:
                    showing.room = room
                    showing.save()
                fixed += 1
                if fixed <= 10 or not dry_run:
                    print(
                        f"{'Would assign' if dry_run else 'Assigned'}: {showing.event.name[:40]} -> {room.name}"
                    )
            except Room.DoesNotExist:
                print(
                    f"WARNING: Room '{suggested_room_name}' not found for '{showing.event.name[:40]}'"
                )
                unknown += 1
        else:
            unknown += 1
            if unknown <= 5:
                print(
                    f"No mapping for template '{template_name}': {showing.event.name[:40]}"
                )

    print()
    print(f"{'Would fix' if dry_run else 'Fixed'}: {fixed} showings")
    print(f"Still unknown: {unknown} showings")

    if dry_run:
        print()
        print("To actually apply these changes, run:")
        print("  python fix_orphaned_showings.py --apply")


if __name__ == "__main__":
    print("=" * 60)
    print("Orphaned Showings Fix")
    print("=" * 60)
    print()

    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        dry_run = False
    else:
        dry_run = True

    analyze_orphaned_showings()

    if Showing.objects.filter(room__isnull=True).count() > 0:
        print()
        print("-" * 60)
        print()
        fix_orphaned_showings(dry_run=dry_run)
