# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-written"
"""Inclusion tag for the per-showing "Add to calendar" trio."""

from django import template
from django.template.defaultfilters import date as date_filter
from django.urls import reverse

from toolkit.diary.calendar_links import (
    google_calendar_url,
    outlook_calendar_url,
)

register = template.Library()


@register.inclusion_tag("_calendar_links.html", takes_context=True)
def calendar_links(context, showing, date_trigger=False):
    request = context.get("request")
    date_label = None
    if date_trigger:
        date_label = date_filter(showing.start, "D j H:i")
        if showing.event.duration:
            date_label += f"–{date_filter(showing.end_time, 'H:i')}"
    return {
        "ics_url": reverse(
            "single-showing-ics", kwargs={"showing_id": showing.pk}
        ),
        "google_url": google_calendar_url(showing, request=request),
        "outlook_url": outlook_calendar_url(showing, request=request),
        "date_label": date_label,
    }
