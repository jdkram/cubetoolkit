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
    password_reset_url = request.build_absolute_uri(reverse("password_reset"))
    timeout_days = max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)
    validity = f"{timeout_days} day" if timeout_days == 1 else f"{timeout_days} days"

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
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[cfg.organiser_notification_email],
        fail_silently=True,
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
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[cfg.organiser_notification_email],
        fail_silently=True,
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
    send_mail(
        subject=subject,
        message=body,
        from_email=_from_email(),
        recipient_list=[cfg.organiser_notification_email],
        fail_silently=True,
    )


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
