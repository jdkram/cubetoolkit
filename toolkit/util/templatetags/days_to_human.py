# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
from django.template import Library

register = Library()


@register.filter
def days_to_human(days):
    """Convert an integer number of days to a compact human-readable string.

    E.g. 365 → "1 year", 400 → "1 year, 35 days", 90 → "3 months".
    Months are approximated as 30 days; years as 365 days.
    """
    if not days:
        return str(days)
    days = int(days)
    years, remainder = divmod(days, 365)
    months, remaining_days = divmod(remainder, 30)

    parts = []
    if years:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    if remaining_days:
        parts.append(f"{remaining_days} day{'s' if remaining_days != 1 else ''}")
    return ", ".join(parts) or "0 days"
