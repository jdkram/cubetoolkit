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


def validate_event_link_url(url):
    """Accept only URLs from the EventLink domain whitelist.

    Accepted if the netloc matches (or is a subdomain of) one of the
    built-in domains, a domain in EVENTLINK_EXTRA_ALLOWED_DOMAINS, or the
    URL path contains a self-hosted Nextcloud share pattern.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]  # strip optional port
        path = parsed.path.lower()
    except Exception:
        raise ValidationError("Enter a valid URL.")

    extra = getattr(settings, "EVENTLINK_EXTRA_ALLOWED_DOMAINS", [])
    all_domains = _EVENTLINK_BUILTIN_DOMAINS + list(extra)

    for domain in all_domains:
        if host == domain or host.endswith("." + domain):
            return

    # Self-hosted Nextcloud: match on path heuristic regardless of domain
    if "/nextcloud/" in path or "/index.php/s/" in path:
        return

    allowed_str = ", ".join(all_domains)
    raise ValidationError(
        f"Event links must use an approved domain ({allowed_str}). "
        "For a self-hosted Nextcloud the URL path must contain /nextcloud/ "
        "or /index.php/s/. Ask a Panopticon member to add a new domain to "
        "EVENTLINK_EXTRA_ALLOWED_DOMAINS if you need another service."
    )
