# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-written"
"""
Per-showing "Add to calendar" link generation.

Three flavours per showing:
  - .ics file (text/calendar) — universal, works with Apple Calendar,
    Outlook desktop, anything that handles the MIME type.
  - Google Calendar prepopulated template URL.
  - Outlook.com prepopulated template URL.

These are one-shot adds, not subscriptions: if the showing moves, the
calendar entry won't update. See docs/TASKS.md 9.10.4a.
"""

from urllib.parse import urlencode

from django.conf import settings


def _utc_compact(dt):
    """Format a tz-aware datetime as basic UTC iCalendar form: YYYYMMDDTHHMMSSZ."""
    return dt.astimezone(tz=_utc()).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso(dt):
    """Format a tz-aware datetime as extended UTC ISO 8601, no fractional seconds."""
    return dt.astimezone(tz=_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc():
    import datetime as _dt
    return _dt.timezone.utc


def _ics_escape(text):
    """Escape per RFC 5545: backslash, semicolon, comma, newline."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _venue_location():
    venue = getattr(settings, "VENUE", {}) or {}
    return venue.get("cinemaname") or venue.get("longname") or venue.get("name") or ""


def _summary(showing):
    parts = [showing.event.name]
    room = getattr(showing, "room", None)
    if getattr(settings, "MULTIROOM_ENABLED", False) and room:
        parts.append(f"({room.name})")
    return " ".join(p for p in parts if p)


def _description(showing, public_url=None):
    bits = []
    summary = (showing.event.copy_summary or "").strip()
    if summary:
        bits.append(summary)
    if public_url:
        bits.append(public_url)
    return "\n\n".join(bits)


def _public_url(request, showing):
    """Absolute URL to the public event page for this showing."""
    if request is None:
        return ""
    from django.urls import reverse
    return request.build_absolute_uri(
        reverse("single-showing-view", kwargs={"showing_id": showing.pk})
    )


def build_ics(showing, request=None, dtstamp=None):
    """
    Hand-rolled single-event iCalendar payload (RFC 5545).

    No external dep — one VEVENT is trivial. Lines are CRLF-terminated as
    the spec requires; long lines are not folded (clients tolerate this
    and our content rarely exceeds 75 octets in practice).
    """
    import datetime as _dt
    if dtstamp is None:
        dtstamp = _dt.datetime.now(tz=_utc())

    venue = getattr(settings, "VENUE", {}) or {}
    host = (
        request.get_host()
        if request is not None
        else (venue.get("url", "toolkit.local").replace("https://", "").replace("http://", "").rstrip("/"))
    )
    prodid = f"-//{venue.get('longname', 'Toolkit')}//Toolkit//EN"
    uid = f"showing-{showing.pk}@{host}"
    public_url = _public_url(request, showing)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_ics_escape(prodid)}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_utc_compact(dtstamp)}",
        f"DTSTART:{_utc_compact(showing.start)}",
        f"DTEND:{_utc_compact(showing.end_time)}",
        f"SUMMARY:{_ics_escape(_summary(showing))}",
        f"DESCRIPTION:{_ics_escape(_description(showing, public_url))}",
        f"LOCATION:{_ics_escape(_venue_location())}",
    ]
    if public_url:
        lines.append(f"URL:{public_url}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"


def google_calendar_url(showing, request=None):
    public_url = _public_url(request, showing)
    params = {
        "action": "TEMPLATE",
        "text": _summary(showing),
        "dates": f"{_utc_compact(showing.start)}/{_utc_compact(showing.end_time)}",
        "details": _description(showing, public_url),
        "location": _venue_location(),
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(
        {k: v for k, v in params.items() if v}
    )


def outlook_calendar_url(showing, request=None):
    public_url = _public_url(request, showing)
    params = {
        "path": "/calendar/action/compose",
        "rru": "addevent",
        "subject": _summary(showing),
        "startdt": _utc_iso(showing.start),
        "enddt": _utc_iso(showing.end_time),
        "body": _description(showing, public_url),
        "location": _venue_location(),
    }
    return "https://outlook.live.com/calendar/0/deeplink/compose?" + urlencode(
        {k: v for k, v in params.items() if v}
    )
