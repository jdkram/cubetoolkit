# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""
Shared helpers for sending password-set / password-reset emails.

Centralises the token-building, URL-derivation, and venue lookup that
were previously tripped across three call sites:

- members/volunteer_views._send_password_set_email (Panopticon-triggered
  welcome or reset for a volunteer account) — uses send_password_set_email
  below verbatim.
- inductions/views._send_password_reset_email (post-induction login
  confirmation for a checked-in attendee who already had an account) —
  reuses build_password_reset_url + password_reset_validity but keeps its
  own inductor-confirmation copy, because that wording is inductions-specific.
- inductions/emails.send_welcome_email (template-driven welcome email sent
  at check-in) — reuses build_password_reset_url + password_reset_validity
  but keeps its template-based subject/body (configured in InductionsSettings).

Venue name and from-address are read from settings.VENUE consistently here
so callers don't each re-inline the fallback chain that drifted between
apps (longname->name vs longname->name->"" vs hardcoded VENUE["longname"]).
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def venue_name() -> str:
    """Display name for the venue, from settings.VENUE.longname (or .name)."""
    return settings.VENUE.get("longname", settings.VENUE.get("name", ""))


def from_email() -> str:
    """From: address for outbound password emails — VENUE.mailout_from_address or DEFAULT_FROM_EMAIL."""
    return settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL


def password_reset_timeout_days() -> int:
    """PASSWORD_RESET_TIMEOUT (seconds) converted to whole days, minimum 1.

    Django's default is 3 days (259200s). A 0-day config would format poorly,
    so we floor at 1.
    """
    return max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)


def password_reset_validity() -> str:
    """Human-readable validity string, e.g. '3 days' or '1 day'."""
    days = password_reset_timeout_days()
    return f"{days} day" if days == 1 else f"{days} days"


def build_password_reset_url(request, user) -> str:
    """Absolute one-use URL the recipient must visit to set their password.

    Uses Django's default_token_generator (the same mechanism backing the
    built-in password-reset views). The token is single-use and the URL is
    valid for PASSWORD_RESET_TIMEOUT seconds (see password_reset_validity).
    """
    token = default_token_generator.make_token(user)
    uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
    return request.build_absolute_uri(
        reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uid_b64, "token": token},
        )
    )


def send_password_set_email(request, user, welcome=False):
    """Send a password-set link to a volunteer user.

    welcome=True: first-time welcome copy ("You've been added as a volunteer")
    welcome=False: reset copy ("A password reset has been requested")

    Used by members (Panopticon-triggered). The inductions check-in welcome
    email (template-driven, configured in InductionsSettings) and the
    inductions post-check-in reset for existing accounts (inductor-confirmation
    copy) live separately and reuse build_password_reset_url +
    password_reset_validity from here, not this function.
    """
    reset_url = build_password_reset_url(request, user)
    validity = password_reset_validity()
    name = user.first_name or user.username
    venue = venue_name()

    if welcome:
        subject = f"[{venue}] Welcome — set your toolkit password"
        message = (
            f"Hi {name},\n\n"
            f"You've been added as a volunteer at {venue}.\n\n"
            f"Click the link below to set your password and log in to the toolkit "
            f"(valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this email, you can ignore it — no account "
            f"will be activated unless you follow the link."
        )
    else:
        subject = f"[{venue}] Set your toolkit password"
        message = (
            f"Hi {name},\n\n"
            f"A password reset has been requested for your toolkit account.\n\n"
            f"Click the link below to set a new password (valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this, you can ignore this email."
        )

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email(),
        recipient_list=[user.email],
        fail_silently=False,
    )