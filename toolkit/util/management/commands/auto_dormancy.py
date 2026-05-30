# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.members.models import Volunteer


class Command(BaseCommand):
    help = (
        "Mark active volunteers as Dormant when they have gone quiet, based on the "
        "day-based thresholds in Site settings:\n"
        "  - volunteer_dormancy_days: active volunteers who have not logged in for this long.\n"
        "  - volunteer_never_logged_in_grace_days: active volunteers who have never logged "
        "in, this long after their account was created (likely re-induction candidates).\n"
        "Dormant is a soft, reversible label — it does not disable login or rota signup. "
        "This command only ever moves Active -> Dormant; it never touches Retired or "
        "Suspended volunteers and never deletes anything. Run periodically via cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would be marked Dormant without making any changes.",
        )

    def handle(self, *args, **options):
        config = get_site_config()
        dormancy_days = config.volunteer_dormancy_days
        grace_days = config.volunteer_never_logged_in_grace_days
        dry_run = options["dry_run"]
        now = timezone.now()

        active = Volunteer.objects.filter(
            status=Volunteer.STATUS_ACTIVE
        ).select_related("member", "user")

        # Cohort 1: hasn't logged in for longer than the dormancy threshold.
        inactive = Volunteer.objects.none()
        if dormancy_days:
            inactive = active.filter(
                user__last_login__lt=now - timedelta(days=dormancy_days)
            )

        # Cohort 2: never logged in, and the grace period since joining has passed.
        # `last_login__lt` above silently excludes NULLs, so these need a separate,
        # NULL-safe query — otherwise they would never be caught at all.
        never_logged_in = Volunteer.objects.none()
        if grace_days:
            never_logged_in = active.filter(
                user__last_login__isnull=True,
                user__date_joined__lt=now - timedelta(days=grace_days),
            )

        if not dormancy_days and not grace_days:
            self.stdout.write(
                "Auto-dormancy is disabled (both volunteer_dormancy_days and "
                "volunteer_never_logged_in_grace_days are 0). Nothing to do."
            )
            return

        self._report("Inactive (no login)", inactive, dry_run, lambda v: v.user.last_login)
        self._report(
            "Never logged in", never_logged_in, dry_run, lambda v: None
        )

        if dry_run:
            total = inactive.count() + never_logged_in.count()
            self.stdout.write(
                f"[DRY RUN] Would mark {total} volunteer(s) as Dormant."
            )
            return

        # Two updates rather than a combined OR query: the cohorts are disjoint
        # (one requires last_login NOT NULL, the other requires it NULL) and the
        # per-cohort counts make the summary clearer.
        count = inactive.update(status=Volunteer.STATUS_DORMANT)
        count += never_logged_in.update(status=Volunteer.STATUS_DORMANT)
        self.stdout.write(
            self.style.SUCCESS(f"Marked {count} volunteer(s) as Dormant.")
        )

    def _report(self, label, queryset, dry_run, last_seen):
        verb = "Would mark" if dry_run else "Marking"
        for vol in queryset:
            when = last_seen(vol)
            self.stdout.write(
                f"  [{label}] {verb} Dormant: {vol.member.name} "
                f"(last login: {when.date() if when else 'never'})"
            )
