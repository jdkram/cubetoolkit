# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from toolkit.inductions.emails import send_reminder
from toolkit.inductions.models import InductionSession, InductionSignup

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send 3-day reminder emails for upcoming induction sessions."

    def handle(self, *args, **options):
        now = timezone.now()
        window_start = now
        window_end = now + timezone.timedelta(hours=72)

        sessions = InductionSession.objects.filter(
            status=InductionSession.STATUS_OPEN,
            date__gte=window_start,
            date__lte=window_end,
            reminder_sent_at__isnull=True,
        )

        for session in sessions:
            pending = session.signups.filter(
                status=InductionSignup.STATUS_PENDING,
                email__gt="",
            )
            sent = 0
            failed = 0
            for signup in pending:
                try:
                    # send_reminder needs a request for building the absolute URL.
                    # Management commands have no request, so we build the ICS URL
                    # from settings instead.
                    _send_reminder_no_request(signup)
                    sent += 1
                except Exception:
                    logger.exception(f"Failed to send reminder for signup #{signup.pk}")
                    failed += 1

            session.reminder_sent_at = now
            session.save(update_fields=["reminder_sent_at"])
            self.stdout.write(
                f"Session '{session.title}': {sent} reminders sent"
                + (f", {failed} failed" if failed else "")
            )


def _send_reminder_no_request(signup):
    """Reminder variant that constructs the ICS URL from settings."""
    from django.conf import settings
    from django.core.mail import send_mail
    from toolkit.inductions.models import get_inductions_settings
    from toolkit.inductions.emails import _venue, _from_email, _format

    cfg = get_inductions_settings()
    session = signup.session
    venue_name = _venue()

    # Build an absolute ICS URL from the SITE_URL setting (expected: "https://host")
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    from django.urls import reverse
    ics_path = reverse("inductions:calendar_ics", kwargs={"slug": session.slug})
    calendar_url = f"{site_url}{ics_path}" if site_url else ics_path

    vars = {
        "name": signup.name,
        "venue": venue_name,
        "session_title": session.title,
        "session_date": session.date.strftime("%A %-d %B %Y at %H:%M"),
        "session_location": session.location or "TBC",
        "calendar_url": calendar_url,
    }
    subject = _format(cfg.get_reminder_subject(), **vars)
    body = _format(cfg.get_reminder_body(), **vars)
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[signup.email],
        fail_silently=False,
    )
