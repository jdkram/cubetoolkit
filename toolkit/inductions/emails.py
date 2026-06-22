# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import get_inductions_settings


def _venue():
    return settings.VENUE.get("longname", settings.VENUE.get("name", ""))


def _from_email():
    return settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL


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
    """Welcome + password-set email sent when someone is checked in."""
    cfg = get_inductions_settings()
    session = signup.session

    token = default_token_generator.make_token(user)
    uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
    password_url = request.build_absolute_uri(
        reverse("password_reset_confirm", kwargs={"uidb64": uid_b64, "token": token})
    )
    timeout_days = max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)
    validity = f"{timeout_days} day" if timeout_days == 1 else f"{timeout_days} days"

    if cfg.welcome_pack_url:
        welcome_pack_section = (
            f"{cfg.welcome_pack_label}: {cfg.welcome_pack_url}\n\n"
        )
    else:
        welcome_pack_section = ""

    vars = {
        "name": signup.name,
        "venue": _venue(),
        "session_title": session.title,
        "password_url": password_url,
        "validity": validity,
        "welcome_pack_section": welcome_pack_section,
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
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[cfg.organiser_notification_email],
        fail_silently=True,
    )
