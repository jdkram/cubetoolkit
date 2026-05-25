from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
import django.utils.timezone


def validate_in_future(time):
    # Use d.u.t.now() instead of datetime.now as the django version returns
    # a datetime object with the timezone set (to UTC) so the comparison will
    # be correct for summertime, etc.
    if time < django.utils.timezone.now():
        raise ValidationError("Must be in the future")


# Domains that may appear as EventLink URLs.
# Any subdomain of a listed domain is also accepted.
_EVENTLINK_BUILTIN_DOMAINS = [
    "riseup.net",
    "nextcloud.com",
    "nextcloud.org",
    "chat.whatsapp.com",
    "linktr.ee",
]


def _get_extra_allowed_domains():
    """Return extra allowed domains from SiteConfiguration, falling back to
    the EVENTLINK_EXTRA_ALLOWED_DOMAINS Django setting."""
    # Try SiteConfiguration first (DB-backed, editable via dashboard)
    try:
        from toolkit.diary.models import SiteConfiguration

        raw = SiteConfiguration.load().eventlink_extra_allowed_domains
        if raw:
            return [
                d.strip()
                for d in raw.splitlines()
                if d.strip()
            ]
    except Exception:
        pass

    # Fall back to settings constant
    return list(getattr(settings, "EVENTLINK_EXTRA_ALLOWED_DOMAINS", []))


def validate_event_link_url(url):
    """Accept only URLs from the EventLink domain whitelist.

    Accepted if the netloc matches (or is a subdomain of) one of the
    built-in domains, a domain in EVENTLINK_EXTRA_ALLOWED_DOMAINS, or the
    URL path contains a self-hosted Nextcloud share pattern.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]  # strip optional port
    except Exception:
        raise ValidationError("Enter a valid URL.")

    all_domains = _EVENTLINK_BUILTIN_DOMAINS + _get_extra_allowed_domains()

    for domain in all_domains:
        if host == domain or host.endswith("." + domain):
            return

    allowed_str = ", ".join(all_domains)
    raise ValidationError(
        f"Event links must use an approved domain ({allowed_str}). "
        "Ask a Panopticon member to add a new domain to the "
        "Site Settings dashboard if you need another service."
    )


def get_eventlink_allowed_domains():
    """Return the full list of allowed event-link domains (builtins + extras).

    Suitable for passing into templates so the hint text stays in sync with
    the validator.
    """
    return _EVENTLINK_BUILTIN_DOMAINS + _get_extra_allowed_domains()
