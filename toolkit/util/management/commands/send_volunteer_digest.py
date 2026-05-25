# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""
Weekly volunteer digest email.

Run weekly via systemd timer or cron (see docs/ONBOARDING.md).
Sends a personalised plain-text email to every opted-in active volunteer.

Usage:
    python manage.py send_volunteer_digest
    python manage.py send_volunteer_digest --dry-run
"""

import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.core.signing import Signer
from django.template.loader import render_to_string
from django.urls import reverse
import django.utils.timezone as timezone

from toolkit.diary.models import RotaEntry, Showing, VolunteerEventMark
from toolkit.members.models import Volunteer

logger = logging.getLogger(__name__)

DIGEST_LOOKBACK_DAYS_DEFAULT = 30
STARRED_EVENTS_HORIZON_DAYS = 30
UPCOMING_SHIFTS_DAYS = 7


def _make_unsubscribe_token(volunteer):
    signer = Signer(salt="volunteer-digest-unsubscribe")
    return signer.sign(str(volunteer.pk)).split(":", 1)[1]


def _build_digest(volunteer, now):
    """Return a dict of content sections for this volunteer's digest.

    Each section is a list of strings. Empty lists mean section is omitted.
    """
    lookback_cutoff = (
        volunteer.last_digest_sent_at
        if volunteer.last_digest_sent_at
        else now - datetime.timedelta(days=DIGEST_LOOKBACK_DAYS_DEFAULT)
    )
    upcoming_cutoff = now + datetime.timedelta(days=UPCOMING_SHIFTS_DAYS)
    starred_cutoff = now + datetime.timedelta(days=STARRED_EVENTS_HORIZON_DAYS)

    # 1. Upcoming shifts (next 7 days)
    upcoming_shifts = (
        RotaEntry.objects.filter(
            volunteer=volunteer,
            showing__confirmed=True,
            showing__start__gt=now,
            showing__start__lte=upcoming_cutoff,
        )
        .select_related("showing__event", "role")
        .order_by("showing__start")
    )
    shifts_lines = [
        f"{entry.showing.event.name} — "
        f"{entry.showing.start.strftime('%-d %b %Y, %H:%M')} — "
        f"{entry.role.name}"
        for entry in upcoming_shifts
    ]

    # 2. New on the programme since last digest
    new_showings = (
        Showing.objects.public()
        .filter(
            created_at__gte=lookback_cutoff,
            start__gt=now,
        )
        .select_related("event")
        .order_by("event__name", "start")
    )
    new_programme_lines = []
    seen_events = set()
    for showing in new_showings:
        if showing.event_id not in seen_events:
            seen_events.add(showing.event_id)
            # Find the earliest future showing for this event
            first = (
                Showing.objects.public()
                .filter(event=showing.event, start__gt=now)
                .order_by("start")
                .first()
            )
            if first:
                new_programme_lines.append(
                    f"{showing.event.name} — first showing "
                    f"{first.start.strftime('%-d %b %Y, %H:%M')}"
                )

    # 3. Starred events with a showing in the next 30 days
    starred_marks = (
        VolunteerEventMark.objects.filter(
            volunteer=volunteer,
            mark_type=VolunteerEventMark.MARK_STAR,
            event__showings__start__gt=now,
            event__showings__start__lte=starred_cutoff,
        )
        .select_related("event")
        .distinct()
    )
    starred_lines = []
    for mark in starred_marks:
        next_showing = (
            Showing.objects.public()
            .filter(event=mark.event, start__gt=now, start__lte=starred_cutoff)
            .order_by("start")
            .first()
        )
        if next_showing:
            starred_lines.append(
                f"{mark.event.name} — "
                f"{next_showing.start.strftime('%-d %b %Y, %H:%M')}"
            )

    return {
        "shifts": shifts_lines,
        "new_programme": new_programme_lines,
        "starred": starred_lines,
    }


class Command(BaseCommand):
    help = "Send weekly volunteer digest email to opted-in volunteers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            default=False,
            help="Build digests and report recipients but do not send emails or update last_digest_sent_at",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        week_of = now.strftime("%-d %b %Y")

        volunteers = Volunteer.objects.filter(
            weekly_digest=True, status=Volunteer.STATUS_ACTIVE
        ).select_related("member")

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Sending weekly digest to {volunteers.count()} opted-in active volunteer(s)"
        )

        sent = 0
        skipped = 0

        for volunteer in volunteers:
            email = getattr(volunteer.member, "email", None)
            name = getattr(volunteer.member, "name", None) or "Volunteer"

            if not email:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping {name}: no email address"
                    )
                )
                skipped += 1
                continue

            sections = _build_digest(volunteer, now)

            # Skip if there's nothing to say
            if not any(sections.values()):
                self.stdout.write(f"  Skipping {name} <{email}>: nothing to report")
                skipped += 1
                continue

            token = _make_unsubscribe_token(volunteer)
            unsubscribe_url = (
                settings.VENUE.get("siteurl", "").rstrip("/")
                + reverse("volunteer-digest-unsubscribe")
                + f"?token={volunteer.pk}:{token}"
            )
            toolkit_url = (
                settings.VENUE.get("siteurl", "").rstrip("/")
                + reverse("view-volunteer-list")
            )

            context = {
                "volunteer_name": name.split()[0] if name else "Volunteer",
                "week_of": week_of,
                "shifts": sections["shifts"],
                "new_programme": sections["new_programme"],
                "starred": sections["starred"],
                "toolkit_url": toolkit_url,
                "unsubscribe_url": unsubscribe_url,
            }

            body = render_to_string("volunteer_digest_email.txt", context)
            subject = f"Your {settings.VENUE['cinemaname']} volunteer digest — week of {week_of}"
            from_email = settings.DEFAULT_FROM_EMAIL

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would send to {name} <{email}>")
                self.stdout.write(f"    Shifts: {len(sections['shifts'])}")
                self.stdout.write(f"    New programme: {len(sections['new_programme'])}")
                self.stdout.write(f"    Starred: {len(sections['starred'])}")
            else:
                try:
                    send_mail(subject, body, from_email, [email], fail_silently=False)
                    volunteer.last_digest_sent_at = now
                    volunteer.save(update_fields=["last_digest_sent_at"])
                    self.stdout.write(
                        self.style.SUCCESS(f"  Sent to {name} <{email}>")
                    )
                    sent += 1
                except Exception as exc:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  Failed to send to {name} <{email}>: {exc}"
                        )
                    )
                    skipped += 1

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone. Sent: {sent}. Skipped/failed: {skipped}."
                )
            )
