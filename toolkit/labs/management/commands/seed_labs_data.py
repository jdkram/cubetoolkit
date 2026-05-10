"""
seed_labs_data - populate the labs app with anonymised sample data.

Data is loaded from TOML files in toolkit/labs/management/commands/seed_data/.
Run after seed_dev_data (depends on rooms existing for room notes).
"""

import datetime
import random
import tomllib
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.labs.models import Collective, DonationItem, Job, RoomNote, COLLECTIVE_PALETTE

DATA_DIR = Path(__file__).parent / "seed_data"


def _load(filename):
    with open(DATA_DIR / filename, "rb") as f:
        return tomllib.load(f)


class Command(BaseCommand):
    help = "Seed the labs app with sample collectives, donations, jobs, and room notes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Delete all existing labs data before seeding.",
        )

    def handle(self, *args, **options):
        if options["wipe"]:
            self.stdout.write("Wiping existing labs data...")
            Collective.objects.all().delete()
            DonationItem.objects.all().delete()
            Job.objects.all().delete()
            RoomNote.objects.all().delete()
            self.stdout.write("Done.")

        counts = {
            "collectives": self._seed_collectives(),
            "donations": self._seed_donations(),
            "jobs": self._seed_jobs(),
            "room_notes": self._seed_room_notes(),
        }

        self.stdout.write(
            self.style.SUCCESS(
                f"\nLabs seed data created:\n"
                f"  Collectives:     {counts['collectives']} new\n"
                f"  Donation items:  {counts['donations']} new\n"
                f"  Jobs:            {counts['jobs']} new\n"
                f"  Room notes:      {counts['room_notes']} new\n"
            )
        )

    def _seed_collectives(self):
        data = _load("collectives.toml")
        palette_hexes = [hex_val for hex_val, _ in COLLECTIVE_PALETTE]
        created = 0
        for item in data["collectives"]:
            item.setdefault("colour", random.choice(palette_hexes))
            _, made = Collective.objects.get_or_create(slug=item["slug"], defaults=item)
            if made:
                created += 1
        return created

    def _seed_donations(self):
        data = _load("donations.toml")
        created = 0
        for item in data["donations"]:
            _, made = DonationItem.objects.get_or_create(
                name=item["name"], defaults=item
            )
            if made:
                created += 1
        return created

    def _seed_jobs(self):
        data = _load("jobs.toml")
        admin_user = User.objects.filter(is_superuser=True).first()
        created = 0
        for item in data["jobs"]:
            days_ago = item.pop("resolved_days_ago", 0)
            resolved_at = (
                timezone.now() - datetime.timedelta(days=days_ago)
                if item.get("resolved") and days_ago
                else None
            )
            _, made = Job.objects.get_or_create(
                title=item["title"],
                defaults={**item, "posted_by": admin_user, "resolved_at": resolved_at},
            )
            if made:
                created += 1
        return created

    def _seed_room_notes(self):
        data = _load("room_notes.toml")
        created = 0
        for item in data["room_notes"]:
            _, made = RoomNote.objects.get_or_create(
                room_id=item["room_id"], defaults={"body": item["body"]}
            )
            if made:
                created += 1
        return created
