# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Notify volunteers that the privacy policy has changed.

Invoked directly (as a Python function call, not via call_command) by the
"Mark privacy policy as updated" admin action in InductionsSettings
(toolkit/inductions/views.py: manage_mark_policy_updated) right after the
version is bumped, so affected volunteers hear about it immediately rather
than waiting for the next send_consent_renewal_reminders cron run. This
command exists so the same notification can also be retried by hand, e.g.
after an earlier run had delivery failures.
"""
from django.core.management.base import BaseCommand

from toolkit.inductions.emails import notify_policy_change
from toolkit.inductions.models import InductionsSettings
from toolkit.members.models import Volunteer


class Command(BaseCommand):
    help = "Email active volunteers who haven't consented to the current privacy policy version."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report who would be emailed without sending anything.",
        )

    def handle(self, *args, **options):
        cfg = InductionsSettings.load()
        outstanding = Volunteer.objects.filter(
            status=Volunteer.STATUS_ACTIVE,
            retention_exempt=False,
            consent_policy_version__lt=cfg.privacy_policy_version,
        ).select_related("member")

        dry_run = options["dry_run"]
        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}{outstanding.count()} volunteer(s) "
            f"behind privacy policy version {cfg.privacy_policy_version}"
        )
        if not outstanding.exists():
            return
        if dry_run:
            for volunteer in outstanding:
                self.stdout.write(f"  [DRY RUN] Would notify {volunteer.member.name} <{volunteer.member.email}>")
            return

        sent, skipped = notify_policy_change()
        self.stdout.write(self.style.SUCCESS(f"Notified {sent} volunteer(s); {skipped} skipped."))
