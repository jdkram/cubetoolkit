# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Yearly consent renewal reminders.

Run periodically via cron, alongside auto_dormancy (see docs/ONBOARDING.md).
Reminds active volunteers whose consent (Member.gdpr_opt_in) has gone stale
that they should log in and reconfirm it. Never changes Volunteer.status and
never anonymises anything — a volunteer who doesn't respond is only flagged
via Volunteer.consent_overdue, for a human to review in the volunteer list.
"""
import logging

from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.inductions.emails import _from_email, build_consent_renewal_email
from toolkit.members.models import Volunteer

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Email active volunteers whose consent has gone stale, asking them to reconfirm it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report who would be emailed without sending anything or updating consent_reminder_sent_at.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        cfg = get_site_config()
        renewal_days = cfg.consent_renewal_days
        if not renewal_days:
            self.stdout.write("Consent renewal is disabled (consent_renewal_days = 0). Nothing to do.")
            return

        cutoff = now - timezone.timedelta(days=renewal_days)

        due = (
            Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE, retention_exempt=False)
            .filter(member__gdpr_opt_in__lt=cutoff)
            .select_related("member")
        )
        # Don't re-send to someone already reminded this cycle.
        due = [v for v in due if not v.consent_reminder_sent_at or v.consent_reminder_sent_at < cutoff]

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}{len(due)} volunteer(s) due a consent renewal reminder"
        )

        if not due:
            return

        sent = 0
        skipped = 0
        connection = get_connection() if not dry_run else None
        try:
            if connection:
                connection.open()
            for volunteer in due:
                email = volunteer.member.email
                name = volunteer.member.name or "Volunteer"
                if not email:
                    self.stdout.write(self.style.WARNING(f"  Skipping {name}: no email address"))
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  [DRY RUN] Would remind {name} <{email}>")
                    continue

                try:
                    subject, body = build_consent_renewal_email(volunteer)
                    EmailMessage(subject, body, _from_email(), [email], connection=connection).send()
                    volunteer.consent_reminder_sent_at = now
                    volunteer.save(update_fields=["consent_reminder_sent_at"])
                    self.stdout.write(self.style.SUCCESS(f"  Reminded {name} <{email}>"))
                    sent += 1
                except Exception:
                    logger.exception(f"Failed to send consent renewal reminder to volunteer pk={volunteer.pk}")
                    skipped += 1
        finally:
            if connection:
                connection.close()

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s); {skipped} skipped."))
