import json
import datetime
import logging
import csv
import os

from collections import OrderedDict

from django.http import (
    HttpResponse,
    Http404,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.conf import settings
from django import forms as django_forms
from django.forms.models import modelformset_factory
from django.contrib import messages
from django.views.generic import View
import django.template
import django.db
from django.db.models import Count, Q, Min
import django.utils.timezone as timezone
from django.contrib.auth.decorators import (
    permission_required,
    user_passes_test,
)
from toolkit.toolkit_auth.decorators import (
    feature_required,
    write_required,
    read_required,
)
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.html import escape, mark_safe
from django.utils.http import url_has_allowed_host_and_scheme

from toolkit.diary.models import (
    Showing,
    Event,
    EventLink,
    EventTemplateLink,
    DiaryIdea,
    MediaItem,
    EventTemplate,
    EventTag,
    Role,
    RotaEntry,
    PrintedProgramme,
    Room,
    RoomBooking,
    EventTemplateRoom,
    VolunteerEventMark,
    get_site_config,
    SITE_CONFIG_FIELD_GROUPS,
)
import toolkit.diary.forms as diary_forms
from ._common import _get_omdb_api_key
import toolkit.diary.validators as diary_validators
import toolkit.diary.edit_prefs as edit_prefs
from toolkit.diary.poster import generate_event_placeholder
from toolkit.members.models import Qualification, VolunteerQualification
from toolkit.util.image import adjust_colour

# Shared utility method:
from toolkit.diary.daterange import get_date_range

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@user_passes_test(lambda u: u.is_superuser)
def edit_site_configuration(request):
    """Panopticon-only page for editing the SiteConfiguration singleton."""

    config = get_site_config()

    # Grouping/ordering comes from the model module so the model is the single
    # source of truth for which fields exist and how they are presented.
    field_groups = list(SITE_CONFIG_FIELD_GROUPS.items())

    if request.method == "POST":
        form = diary_forms.SiteConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.add_message(
                request, messages.SUCCESS, "Site configuration updated."
            )
            return HttpResponseRedirect(reverse("edit-site-configuration"))
    else:
        form = diary_forms.SiteConfigurationForm(instance=config)

    grouped_fields = [
        (label, [form[name] for name in names])
        for label, names in field_groups
    ]

    # Permission table: configurable rows carry the bound form field so the template
    # can render a dropdown; fixed rows carry only a display string.
    from toolkit.diary.models import SiteConfiguration

    _level_labels = dict(SiteConfiguration.PERMISSION_LEVEL_CHOICES)

    def _fixed(label):
        return {"field": None, "display": label}

    def _configurable(field_name):
        return {
            "field": form[field_name],
            "display": _level_labels.get(getattr(config, field_name), "?"),
        }

    permission_rows = [
        ("Diary — view diary list", _configurable("perm_diary_read")),
        ("Diary — create / edit events", _fixed("Programmer+")),
        ("Diary — calendar", _configurable("perm_diary_calendar")),
        (
            "Diary — programming queue (view)",
            _configurable("perm_programming_queue_read"),
        ),
        (
            "Diary — programming queue (change status)",
            _configurable("perm_programming_queue_write"),
        ),
        (
            "Diary — event templates (list & detail)",
            _configurable("perm_event_templates"),
        ),
        ("Diary — event templates (import)", _fixed("Panopticon only")),
        ("Diary — event tags", _configurable("perm_event_tags")),
        ("Diary — roles", _configurable("perm_roles")),
        ("Diary — rooms", _configurable("perm_rooms")),
        (
            "Diary — copy / terms / text reports",
            _configurable("perm_diary_reports"),
        ),
        (
            "Diary — upload printed programmes",
            _configurable("perm_printed_programmes"),
        ),
        ("Rota — view and sign up", _fixed("All volunteers")),
        ("Rota — vacancies page", _configurable("perm_rota_vacancies")),
        (
            "Community — post bulletins",
            _fixed("Configurable (see Bulletins section)"),
        ),
        ("Community — other features", _fixed("All volunteers")),
        ("Website — donations manage", _configurable("perm_donations_manage")),
        ("Website — Wagtail CMS", _fixed("Panopticon only")),
        ("People — volunteer profiles / training", _fixed("Panopticon only")),
        ("People — export CSV / audit log", _fixed("Panopticon only")),
        ("People — qualification report", _fixed("Panopticon only")),
        ("People — bulk training / qual record", _fixed("Panopticon only")),
        ("People — pool health", _fixed("Panopticon only")),
        ("People — member management", _fixed("Panopticon only")),
        ("Meta — access levels", _fixed("Panopticon only")),
        ("Meta — site settings", _fixed("Panopticon only")),
    ]

    try:
        from toolkit.inductions.models import get_inductions_settings

        inductions_settings = get_inductions_settings()
    except Exception:
        inductions_settings = None

    return render(
        request,
        "edit_site_configuration.html",
        {
            "form": form,
            "grouped_fields": grouped_fields,
            "permission_rows": permission_rows,
            "inductions_settings": inductions_settings,
            "omdb_configured": bool(_get_omdb_api_key()),
        },
    )


@require_POST
@write_required
def generate_event_poster(request, event_id):
    """Generate a placeholder poster image for an event (AJAX endpoint).

    Creates the MediaItem immediately and returns its ID and URL for preview.
    The image is associated with the event on form save via generated_media_id.

    POST params:
        colour: Optional hex colour (e.g. "#FF5733") to use as the accent colour.
                If not provided, uses the event's first tag colour or a default.
    """
    event = get_object_or_404(Event, pk=event_id)

    # Get optional colour from POST
    colour_hex = request.POST.get("colour", "").strip()

    try:
        media_item = generate_event_placeholder(
            event, colour_hex=colour_hex or None
        )
        return JsonResponse(
            {
                "success": True,
                "media_id": media_item.id,
                "url": media_item.media_file.url,
                "filename": os.path.basename(media_item.media_file.name),
            }
        )
    except Exception as exc:
        logger.exception("Failed to generate poster for event %s", event_id)
        return JsonResponse({"success": False, "error": str(exc)}, status=500)


@feature_required("programming_queue_read")
def programming_queue(request):
    """Show all events in the programming queue (draft, proposed, or returned for changes)."""
    queue = (
        Event.objects.filter(
            programming_status__in=["draft", "proposed", "rejected"]
        )
        .prefetch_related(
            "showings",
            "showings__room_bookings__room",
            "tags",
            "template__tags",
        )
        .select_related("template")
        .annotate(first_showing_start=Min("showings__start"))
        .order_by("first_showing_start")
    )
    # Attach epoch timestamps for client-side sorting.
    # Django templates block attributes starting with underscores, so we use
    # plain attribute names via a wrapper list of dicts.
    queue_items = []
    for event in queue:
        queue_items.append(
            {
                "event": event,
                "sort_event_date": (
                    int(event.first_showing_start.timestamp())
                    if event.first_showing_start
                    else 9999999999
                ),
                "sort_submitted": int(event.created_at.timestamp()),
                "sort_status_changed": (
                    int(event.programming_status_changed_at.timestamp())
                    if event.programming_status_changed_at
                    else int(event.created_at.timestamp())
                ),
            }
        )
    cfg = get_site_config()
    return render(
        request,
        "programming_queue.html",
        {
            "queue": queue_items,
            "fc_standard_threshold": cfg.breakeven_fc_standard_threshold,
            "fc_music_threshold": cfg.breakeven_fc_music_threshold,
            "can_write": request.user.has_perm("toolkit.write"),
        },
    )


@feature_required("programming_queue_write")
@require_POST
def update_event_programming_status(request, event_id):
    """Update the programming_status (and optionally programming_notes) of an event.

    POST params:
      action     — one of: propose, withdraw, make_active, return_for_changes,
                   approve_at_meeting, save_notes
      notes      — optional text appended to programming_notes
    """
    event = get_object_or_404(Event, pk=event_id)
    action = request.POST.get("action", "")
    notes = request.POST.get("notes", "").strip()

    status_changed = False
    if action == "propose":
        event.programming_status = "proposed"
        status_changed = True
        messages.success(
            request, f"'{event.name}' added to the programming queue."
        )
    elif action == "withdraw":
        event.programming_status = "draft"
        status_changed = True
        messages.info(
            request,
            f"'{event.name}' withdrawn from the queue — back to draft.",
        )
    elif action == "make_active":
        event.programming_status = "active"
        status_changed = True
        messages.success(request, f"'{event.name}' marked as active.")
    elif action == "return_for_changes":
        event.programming_status = "rejected"
        status_changed = True
        messages.warning(
            request, f"'{event.name}' returned to the proposer for changes."
        )
    elif action == "approve_at_meeting":
        event.programming_status = "active"
        event.approval_type = "meeting"
        event.approved_at_meeting_date = timezone.now().date()
        status_changed = True
        messages.success(
            request, f"'{event.name}' approved at today's meeting."
        )
    elif action == "save_notes":
        pass  # just append notes below, no status change
    else:
        messages.error(request, "Unknown action.")
        return HttpResponseRedirect(
            reverse("edit-event-details-view", kwargs={"event_id": event_id})
        )

    if status_changed:
        event.programming_status_changed_at = timezone.now()

    if notes:
        sep = "\n\n" if event.programming_notes else ""
        event.programming_notes = event.programming_notes + sep + notes

    event.save()

    # Return to the queue if coming from there, otherwise to Event Hub
    next_url = request.POST.get("next")
    if not next_url or not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}
    ):
        next_url = reverse(
            "edit-event-details-view", kwargs={"event_id": event_id}
        )
    return HttpResponseRedirect(next_url)


# ---------------------------------------------------------------------------
# Film metadata views (TMDB integration — 9.66)
# ---------------------------------------------------------------------------
