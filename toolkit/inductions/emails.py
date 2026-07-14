# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""
Outbound induction sign-up / reminder / welcome / acknowledgement emails.

Subject + body templates are stored in InductionsSettings (admin-configurable)
and rendered via _format with the vars dict assembled per Email type. The
password-set URL is built via toolkit.toolkit_auth.password_emails so the
token + venue lookup is shared with members' volunteer password flow and
the post-check-in reset flow in inductions/views.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMessage, get_connection, send_mail
from django.urls import reverse
from django.utils import timezone

from toolkit.toolkit_auth import password_emails
from .models import get_inductions_settings

logger = logging.getLogger(__name__)


def _venue():
    return password_emails.venue_name()


def _from_email():
    return password_emails.from_email()


def _format(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def send_signup_confirmation(request, signup):
    """Confirmation email sent immediately when someone signs up for a session."""
    cfg = get_inductions_settings()
    session = signup.session
    calendar_url = request.build_absolute_uri(
        reverse("inductions:calendar_ics", kwargs={"slug": session.slug})
    )
    vars = {
        "name": signup.name,
        "venue": _venue(),
        "session_title": session.title,
        "session_date": session.date.strftime("%A %-d %B %Y at %H:%M"),
        "session_location": session.location or "TBC",
        "calendar_url": calendar_url,
    }
    subject = _format(cfg.get_confirmation_subject(), **vars)
    body = _format(cfg.get_confirmation_body(), **vars)
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[signup.email],
        fail_silently=False,
    )


def send_reminder(request, signup):
    """3-day reminder email."""
    cfg = get_inductions_settings()
    session = signup.session
    calendar_url = request.build_absolute_uri(
        reverse("inductions:calendar_ics", kwargs={"slug": session.slug})
    )
    vars = {
        "name": signup.name,
        "venue": _venue(),
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


def send_welcome_email(request, signup, user):
    """Welcome + password-set email sent when someone is checked in.

    Subject + body are admin-configured templates (InductionsSettings); the
    password-set URL itself is built via password_emails.build_password_reset_url
    so the token + venue lookup are shared with the members reset flow.
    """
    cfg = get_inductions_settings()
    session = signup.session

    password_url = password_emails.build_password_reset_url(request, user)
    password_reset_url = request.build_absolute_uri(reverse("password_reset"))
    validity = password_emails.password_reset_validity()

    vars = {
        "name": signup.name,
        "username": user.username,
        "venue": _venue(),
        "session_title": session.title,
        "password_url": password_url,
        "password_reset_url": password_reset_url,
        "validity": validity,
        "welcome_pack_url": cfg.welcome_pack_url,
    }
    subject = _format(cfg.get_welcome_subject(), **vars)
    body = _format(cfg.get_welcome_body(), **vars)
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_access_needs_ack(request, induction_request):
    """Acknowledgement email sent when someone submits an access needs request."""
    cfg = get_inductions_settings()
    vars = {
        "name": induction_request.name,
        "venue": _venue(),
    }
    subject = _format(cfg.get_access_needs_ack_subject(), **vars)
    body = _format(cfg.get_access_needs_ack_body(), **vars)
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[induction_request.email],
        fail_silently=False,
    )


def send_organiser_notification(induction_request):
    """Notify the configured organiser address of a new access needs request."""
    cfg = get_inductions_settings()
    if not cfg.organiser_notification_email:
        return
    venue = _venue()
    subject = f"[{venue}] New 1:1 induction request from {induction_request.name}"
    body = (
        f"A new 1:1 induction request has been submitted.\n\n"
        f"Name: {induction_request.name}\n"
        f"Email: {induction_request.email}\n"
        f"Access needs: {induction_request.access_needs}\n"
        f"Rough availability: {induction_request.rough_availability or 'Not specified'}\n\n"
        f"Log in to the toolkit to view and manage this request."
    )
    # Organiser notification: a failure shouldn't break the requester's
    # flow, but it must leave a trace (was fail_silently=True, a black hole).
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[cfg.organiser_notification_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            f"Failed to send organiser notification for 1:1 induction "
            f"request pk={induction_request.pk}"
        )


def send_new_signup_notification(session, signup):
    """Notify organisers of each new sign-up (only if notify_on_each_signup is enabled)."""
    cfg = get_inductions_settings()
    if not cfg.organiser_notification_email or not cfg.notify_on_each_signup:
        return
    venue = _venue()
    count = session.signups.count()
    capacity = f"{count}/{session.max_signups}" if session.max_signups else str(count)
    subject = f"[{venue}] New sign-up: {session.title} ({capacity})"
    body = (
        f"Someone has signed up for {session.title}.\n\n"
        f"Name: {signup.name}\n"
        f"Email: {signup.email}\n"
        f"Sign-ups so far: {capacity}\n\n"
        f"Log in to the toolkit to see the full list."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[cfg.organiser_notification_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            f"Failed to send new-signup notification for session "
            f"pk={session.pk} (signup pk={signup.pk})"
        )


def send_session_full_notification(session):
    """Notify organisers when a session reaches its maximum sign-up capacity."""
    cfg = get_inductions_settings()
    if not cfg.organiser_notification_email:
        return
    venue = _venue()
    subject = f"[{venue}] Session full: {session.title}"
    body = (
        f"{session.title} has reached its maximum capacity of {session.effective_capacity()} sign-up(s).\n\n"
        f"Date: {session.date.strftime('%A %-d %B %Y at %H:%M')}\n\n"
        f"The session sign-up page will now show as full. "
        f"Log in to the toolkit to manage the session or increase capacity."
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=[cfg.organiser_notification_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            f"Failed to send session-full notification for session pk={session.pk}"
        )


def _login_url():
    return settings.VENUE.get("siteurl", "").rstrip("/") + reverse("toolkit-index")


def build_consent_renewal_email(volunteer):
    """Return (subject, body) asking a volunteer to log in and reconfirm consent.

    Used by send_consent_renewal_reminders (bulk, one SMTP connection for the
    whole run) — hence returning strings rather than sending directly, unlike
    the single-recipient send_* functions above.
    """
    cfg = get_inductions_settings()
    venue = _venue()
    member = volunteer.member
    first_name = member.name.split()[0] if member.name else "there"
    policy_line = f"\n\nPrivacy policy: {cfg.privacy_policy_url}" if cfg.privacy_policy_url else ""
    subject = f"[{venue}] Please reconfirm your data consent"
    body = (
        f"Hi {first_name},\n\n"
        f"It's been a while since you confirmed you're happy for {venue} to hold your "
        f"volunteer contact and rota details. Please log in and reconfirm on your dashboard:\n\n"
        f"{_login_url()}\n\n"
        f"If you no longer volunteer with us, that's fine too — just let an organiser know, "
        f"or ignore this and we'll follow up about your account in due course.{policy_line}"
    )
    return subject, body


def build_policy_change_email(volunteer):
    """Return (subject, body) telling a volunteer the privacy policy changed.

    Used by send_policy_change_notification — same reasoning as
    build_consent_renewal_email above.
    """
    cfg = get_inductions_settings()
    venue = _venue()
    member = volunteer.member
    first_name = member.name.split()[0] if member.name else "there"
    policy_line = f"\n\n{cfg.privacy_policy_url}" if cfg.privacy_policy_url else ""
    subject = f"[{venue}] Our privacy policy has changed"
    body = (
        f"Hi {first_name},\n\n"
        f"We've updated the privacy policy covering how {venue} handles your volunteer data. "
        f"Please take a look, then log in and reconfirm your consent on your dashboard.{policy_line}\n\n"
        f"{_login_url()}"
    )
    return subject, body


def notify_policy_change():
    """Email every active, non-exempt volunteer behind the current policy version.

    Called both by the send_policy_change_notification management command and
    directly (as a plain function call) by the "mark privacy policy as
    updated" admin action, so the admin action gets an immediate sent/skipped
    count without shelling out via call_command. Stamps consent_reminder_sent_at
    so send_consent_renewal_reminders doesn't also nag these volunteers the
    same week. Returns (sent, skipped).
    """
    from toolkit.members.models import Volunteer

    cfg = get_inductions_settings()
    outstanding = Volunteer.objects.filter(
        status=Volunteer.STATUS_ACTIVE,
        retention_exempt=False,
        consent_policy_version__lt=cfg.privacy_policy_version,
    ).select_related("member")

    now = timezone.now()
    sent = 0
    skipped = 0
    connection = get_connection()
    connection.open()
    try:
        for volunteer in outstanding:
            email = volunteer.member.email
            if not email:
                skipped += 1
                continue
            try:
                subject, body = build_policy_change_email(volunteer)
                EmailMessage(subject, body, _from_email(), [email], connection=connection).send()
                volunteer.consent_reminder_sent_at = now
                volunteer.save(update_fields=["consent_reminder_sent_at"])
                sent += 1
            except Exception:
                logger.exception(f"Failed to send policy-change notification to volunteer pk={volunteer.pk}")
                skipped += 1
    finally:
        connection.close()
    return sent, skipped


def send_test_notification_email(recipient_email):
    """Send a test notification to confirm email delivery is working."""
    venue = _venue()
    subject = f"[{venue}] Test notification — inductions email check"
    body = (
        f"This is a test notification from the {venue} toolkit.\n\n"
        f"If you're reading this, organiser notification emails are working correctly.\n\n"
        f"You can safely ignore this message."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[recipient_email],
        fail_silently=False,
    )
