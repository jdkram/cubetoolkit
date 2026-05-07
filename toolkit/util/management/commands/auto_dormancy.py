# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-written"
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.members.models import Volunteer


class Command(BaseCommand):
    help = (
        "Flag active volunteers as login-inactive if they have not logged in for the "
        "configured number of months (see Site settings > volunteer_dormancy_months). "
        "This sets a soft warning flag only — it does not change their status or "
        "restrict access. Run periodically via cron."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would be flagged without making any changes.",
        )

    def handle(self, *args, **options):
        config = get_site_config()
        months = config.volunteer_dormancy_months

        if months == 0:
            self.stdout.write(
                "Automatic inactivity flagging is disabled "
                "(volunteer_dormancy_months = 0 means never). Nothing to do."
            )
            return

        cutoff = timezone.now() - timedelta(days=months * 30)

        candidates = Volunteer.objects.filter(
            login_inactive=False,
        ).filter(
            user__last_login__lt=cutoff,
        ).select_related("member", "user")

        if not candidates.exists():
            self.stdout.write(
                self.style.SUCCESS(
                    f"No volunteers to flag (none inactive for more than {months} months)."
                )
            )
            return

        dry_run = options["dry_run"]

        for vol in candidates:
            last_login = vol.user.last_login
            self.stdout.write(
                f"  {'[DRY RUN] Would flag' if dry_run else 'Flagging'}: "
                f"{vol.member.name} (last login: {last_login.date() if last_login else 'never'})"
            )

        if not dry_run:
            count = candidates.count()
            candidates.update(login_inactive=True)
            self.stdout.write(
                self.style.SUCCESS(f"Flagged {count} volunteer(s) as login-inactive.")
            )
        else:
            self.stdout.write(
                f"[DRY RUN] Would have flagged {candidates.count()} volunteer(s)."
            )
