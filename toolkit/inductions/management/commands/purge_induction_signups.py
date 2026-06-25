# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.inductions.models import InductionRequest, InductionSession, InductionSignup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Purge PII from pending/no-show induction sign-ups past their purge_after date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be purged without actually deleting any data.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        if dry_run:
            self.stdout.write("[dry-run] No data will be deleted.")

        # Purge session sign-ups
        sessions_due = InductionSession.objects.filter(
            purge_after__lte=now,
        ).exclude(status=InductionSession.STATUS_PURGED)

        for session in sessions_due:
            to_purge = session.signups.filter(
                status__in=[InductionSignup.STATUS_PENDING, InductionSignup.STATUS_NO_SHOW]
            )
            count = to_purge.count()
            if count:
                if not dry_run:
                    to_purge.update(name="", email="", custom_responses={})
                self.stdout.write(f"{'[dry-run] Would purge' if dry_run else 'Purged'} {count} record(s) from '{session.title}'")
            if not dry_run:
                session.status = InductionSession.STATUS_PURGED
                session.save(update_fields=["status"])
            elif sessions_due.exists():
                self.stdout.write(f"  [dry-run] Would mark '{session.title}' as purged")

        # Purge stale access needs requests
        stale_requests = InductionRequest.objects.filter(
            purge_after__lte=now,
        ).exclude(status__in=[
            InductionRequest.STATUS_COMPLETED,
            InductionRequest.STATUS_PURGED,
        ])

        for req in stale_requests:
            if dry_run:
                self.stdout.write(f"[dry-run] Would purge access needs request #{req.pk} ({req.name or '(no name)'})")
                continue
            req.name = ""
            req.email = ""
            req.access_needs = ""
            req.rough_availability = ""
            req.status = InductionRequest.STATUS_PURGED
            req.save(update_fields=["name", "email", "access_needs", "rough_availability", "status"])
            self.stdout.write(f"Purged stale access needs request #{req.pk}")
