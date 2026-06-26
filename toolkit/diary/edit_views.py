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
from django.contrib.auth.decorators import permission_required, user_passes_test
from toolkit.toolkit_auth.decorators import feature_required, write_required, read_required
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
)
import toolkit.diary.forms as diary_forms
import toolkit.diary.validators as diary_validators
import toolkit.diary.edit_prefs as edit_prefs
from toolkit.diary.poster import generate_event_placeholder
from toolkit.members.models import Qualification, VolunteerQualification
from toolkit.util.image import adjust_colour

# Shared utility method:
from toolkit.diary.daterange import get_date_range

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Same escapes Django uses internally for json_script — prevents </script> injection.
_JSON_SCRIPT_ESCAPES = str.maketrans({"<": "\\u003c", ">": "\\u003e", "&": "\\u0026"})


def _safe_json(data):
    """json.dumps with HTML-special chars escaped — safe to embed in a <script> block."""
    return json.dumps(data).translate(_JSON_SCRIPT_ESCAPES)


def _return_to_editindex(request):
    return HttpResponseRedirect(reverse("default-edit"))


def _create_room_booking(showing, room, event):
    """Create a single RoomBooking for showing in room, deriving end from event.duration."""
    end = None
    if event.duration is not None:
        end = showing.start + datetime.timedelta(
            hours=event.duration.hour, minutes=event.duration.minute
        )
    RoomBooking.objects.create(showing=showing, room=room, start=showing.start, end=end)


@write_required
def cancel_edit(request):
    # Again, a dirty hack, used with the above method, used for the "Cancel"
    # link in forms, to either close the popup or just redirect to the edit
    # page
    return _return_to_editindex(request)


@feature_required("diary_read")
def edit_diary_list(request, year=None, day=None, month=None):
    # Basic "edit" list view. Logic about processing of year/month/day
    # parameters is basically the same as for the public diary view.
    #
    # The logic is a bit twisty, from the requirement to show list all dates
    # and 'ideas' fields in the range, even if they don't have any events in
    # them, yet.

    context = {}
    # Sort out date range to display

    # If the query contained the number of days ahead to show then retrieve it
    # and store it as the default for this session (so coming back to the page
    # will look the same)
    query_days_ahead = request.GET.get("daysahead", None)

    try:
        _volunteer = request.user.volunteer
    except Exception:
        _volunteer = None

    if query_days_ahead:
        edit_prefs.set_preference(request.session, "daysahead", query_days_ahead, volunteer=_volunteer)
        default_days_ahead = query_days_ahead
    else:
        default_days_ahead = int(
            edit_prefs.get_preference(request.session, "daysahead", volunteer=_volunteer)
        )

    # utility function, shared with public diary view
    startdatetime, days_ahead = get_date_range(
        year, month, day, query_days_ahead, default_days_ahead
    )
    startdate = startdatetime.date()
    if startdatetime is None:
        raise Http404(days_ahead)

    # Don't allow viewing of dates before today, to avoid editing of the past:
    local_now = timezone.localtime(timezone.now())
    if startdate < local_now.date():
        # Redirect to page with today as the start date:
        new_url = "{}?daysahead={}".format(
            reverse(
                "day-edit",
                kwargs={
                    "year": local_now.year,
                    "month": local_now.month,
                    "day": local_now.day,
                },
            ),
            days_ahead,
        )
        return HttpResponseRedirect(new_url)

    enddatetime = startdatetime + datetime.timedelta(days=days_ahead)

    # Get all showings in the date range
    showings = (
        Showing.objects.start_in_range(startdatetime, enddatetime)
        .order_by("start")
        .select_related()
        .prefetch_related("room_bookings__room")
    )
    # Build two dicts, to hold the showings and the ideas. These dicts are
    # initially empty, and get filled in if there are actually showings or
    # ideas for those dates.
    # This is done so that if dates don't have ideas/showings they still get
    # shown in the list
    dates = OrderedDict()
    # Actually, I lied: start of visible list is not necessarily the 1st of the
    # month, so make sure that it gets an 'IDEAS' link shown:
    ideas = {startdate: ""}
    for days in range(days_ahead):
        # Iterate through every date in the visible range, creating a dict
        # entry for each
        day_in_range = startdatetime + datetime.timedelta(days=days)
        dates[day_in_range.date()] = []
        # If it's the 1st of the month, make sure there's an ideas entry
        if day_in_range.day == 1:
            ideas[day_in_range.date()] = ""
    # Now insert all the showings into the 'dates' dict
    for showing in showings:
        dates[timezone.localtime(showing.start).date()].append(showing)
    # Dates without a showing will still be in the dates dict, so will still
    # be shown

    # Now get all 'ideas' in date range. Fiddle the date range to be from the
    # start of the month in startdate, so the idea for that month gets
    # included:
    idea_startdate = datetime.date(day=1, month=startdate.month, year=startdate.year)
    idea_list = (
        DiaryIdea.objects.filter(month__range=[idea_startdate, enddatetime])
        .order_by("month")
        .select_related()
    )
    # Assemble into the idea dict, with keys that will match the keys in the
    # showings dict
    for idea in idea_list:
        ideas[idea.month] = idea.ideas
    # Fiddle so that the idea for the first month is displayed, even if
    # startdate is after the first day of the month:
    if (
        idea_startdate not in showings
        and len(idea_list) > 0
        and idea_list[0].month.month == startdate.month
    ):
        ideas[startdate] = idea_list[0].ideas

    context["ideas"] = ideas

    # Dateless proposals: events with target_month in range but no showings.
    dateless_events = (
        Event.objects.filter(
            target_month__range=[idea_startdate, enddatetime],
            showings__isnull=True,
        )
        .order_by("target_month", "name")
    )
    # Build lookup: (year, month) -> the key used in the ideas dict for that month.
    # The ideas dict uses startdate as the key for the first month (which may not
    # be the 1st), and the literal 1st-of-month date for all subsequent months.
    month_to_ideas_key = {(k.year, k.month): k for k in ideas}
    dateless_by_month = {}
    for ev in dateless_events:
        key = month_to_ideas_key.get((ev.target_month.year, ev.target_month.month))
        if key is not None:
            dateless_by_month.setdefault(key, []).append(ev)
    context["dateless_by_month"] = dateless_by_month

    # Mobile list view: showings per day, sorted by start, deduplicated.
    # Passed separately because dates_by_time groups by room-booking start,
    # which would show the same event multiple times in the mobile list.
    context["mobile_dates"] = dates

    # Group each day's showings into time rows for the diary table.
    # In multiroom mode, key by each room booking's own start time so that a
    # booking at 19:00 on a 12:00 showing appears in its own 19:00 row.
    # In single-room mode, key by showing.start as before.
    dates_by_time: OrderedDict = OrderedDict()
    for day, day_showings in dates.items():
        time_groups: OrderedDict = OrderedDict()
        for showing in day_showings:
            visible_rbs = (
                showing.visible_room_bookings if settings.MULTIROOM_ENABLED else []
            )
            if visible_rbs:
                for rb in visible_rbs:
                    if rb.start not in time_groups:
                        time_groups[rb.start] = []
                    if showing not in time_groups[rb.start]:
                        time_groups[rb.start].append(showing)
            else:
                if showing.start not in time_groups:
                    time_groups[showing.start] = []
                time_groups[showing.start].append(showing)
        dates_by_time[day] = OrderedDict(sorted(time_groups.items()))
    context["dates"] = dates_by_time
    # Page title:
    context["event_list_name"] = "Diary for {} to {}".format(
        startdatetime.strftime("%d-%m-%Y"), enddatetime.strftime("%d-%m-%Y")
    )
    context["start"] = startdatetime
    context["end"] = enddatetime
    context["edit_prefs"] = edit_prefs.get_preferences(request.session, volunteer=_volunteer)
    all_rooms = list(Room.objects.all())
    column_rooms = [r for r in all_rooms if r.show_column]
    other_rooms = [r for r in all_rooms if not r.show_column]
    context["rooms"] = column_rooms
    context["other_rooms"] = other_rooms
    context["has_other_rooms"] = bool(other_rooms)
    context["multiroom_enabled"] = settings.MULTIROOM_ENABLED
    context["can_edit"] = request.user.has_perm("toolkit.write")
    return render(request, "edit_event_index.html", context)


def _is_light_colour(hex_colour):
    """Return True if the hex colour is perceptually light (needs dark text)."""
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return False
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5


@feature_required("diary_calendar")
def edit_diary_data(request):
    date_format = "%Y-%m-%d"

    current_tz = timezone.get_current_timezone()
    try:
        start_raw = request.GET.get("start", None)
        end_raw = request.GET.get("end", None)
        start_raw = start_raw.partition("T")[0] if start_raw else None
        end_raw = end_raw.partition("T")[0] if end_raw else None
        start = datetime.datetime.strptime(start_raw, date_format).replace(
            tzinfo=current_tz
        )
        end = datetime.datetime.strptime(end_raw, date_format).replace(
            tzinfo=current_tz
        )
    except (ValueError, TypeError):
        logger.error(
            f"Invalid value in date range, one of start '{start_raw}' or end, '{end_raw}'"
        )
        raise Http404("Invalid request")

    showings = (
        Showing.objects.start_in_range(start, end)
        .order_by("start")
        .select_related()
        .prefetch_related("event__tags", "room_bookings__room")
    )

    local_now = timezone.localtime(timezone.now())

    results = []
    for showing in showings:
        # Always link to the Event Hub — consistent with the list view.
        url = reverse(
            "edit-event-details-view",
            kwargs={"event_id": showing.event_id},
        )
        styles = []

        primary_room = showing.primary_room
        if settings.MULTIROOM_ENABLED:
            colour = None
        else:
            colour = settings.CALENDAR_DEFAULT_COLOUR

        if showing.cancelled:
            styles.append("s_cancelled")
        if showing.discounted:
            styles.append("s_discounted")
        if showing.event.private or showing.hide_in_programme:
            styles.append("s_private")
        if showing.event.outside_hire:
            styles.append("s_outside_hire")
        if showing.in_past():
            # Keep room colour unchanged — the "now" boundary line in the
            # calendar provides the past/future visual cue instead.
            styles.append("s_historic")
        if showing.confirmed:
            styles.append("s_confirmed")
        else:
            styles.append("s_unconfirmed")
        if settings.MULTIROOM_ENABLED and primary_room and not primary_room.is_primary:
            styles.append("s_auxiliary_room")

        # Extract hour for time-of-day filtering (0-23)
        local_start = timezone.localtime(showing.start)
        hour = local_start.hour

        # Build tag list for filtering
        tag_slugs = [tag.slug for tag in showing.event.tags.all()]

        base = {
            "title": showing.event.name,
            "url": url,
            "className": styles,
            "tags": tag_slugs,
        }

        if settings.MULTIROOM_ENABLED:
            room_bookings = showing.visible_room_bookings
            if room_bookings:
                # One calendar event per room booking, each at its own time.
                # Omit top-level color so each resource's eventColor applies.
                showing_end = timezone.localtime(showing.end_time).isoformat()
                for rb in room_bookings:
                    rb_start = timezone.localtime(rb.start)
                    rb_end = timezone.localtime(rb.end).isoformat() if rb.end else showing_end
                    results.append({
                        **base,
                        "id": f"rb-{rb.pk}",
                        "start": rb_start.isoformat(),
                        "end": rb_end,
                        "hour": rb_start.hour,
                        "resourceIds": [rb.room_id],
                    })
            else:
                # No room bookings: place in the virtual "unroomed" resource lane.
                results.append({
                    **base,
                    "id": showing.pk,
                    "start": local_start.isoformat(),
                    "end": timezone.localtime(showing.end_time).isoformat(),
                    "hour": hour,
                    "color": settings.CALENDAR_DEFAULT_COLOUR,
                    "resourceIds": ["unroomed"],
                })
        else:
            showing_data = {
                **base,
                "id": showing.pk,
                "start": local_start.isoformat(),
                "end": timezone.localtime(showing.end_time).isoformat(),
                "hour": hour,
                "color": colour,
            }
            if _is_light_colour(colour):
                showing_data["textColor"] = "#111111"
            results.append(showing_data)

    return HttpResponse(
        json.dumps(results), content_type="application/json; charset=utf-8"
    )


@feature_required("diary_calendar")
def edit_diary_calendar(request, year=None, month=None, day=None):
    defaultView = "dayGridMonth"
    try:
        if year and month and day:
            display_time = datetime.date(int(year), int(month), int(day))
            # defaultView stays dayGridMonth for MVP; week view added later
        elif year and month:
            display_time = datetime.date(int(year), int(month), 1)
        elif year and not month:
            raise Http404("Need year and month")
        else:
            display_time = timezone.localtime(timezone.now()).date()
    except ValueError as ve:
        logger.error(f"Bad calendar date: {ve}")
        raise Http404("Bad calendar date")

    context = {
        "display_time": display_time,
        "defaultView": defaultView,
        "settings": settings,
        "rooms_and_colours": (
            [
                {
                    "id": r.id,
                    "name": r.name,
                    "colour": r.colour,
                    "text_colour": "#111111" if _is_light_colour(r.colour) else "#ffffff",
                    "is_primary": r.is_primary,
                }
                for r in Room.objects.all()
            ]
            if settings.MULTIROOM_ENABLED
            else []
        ),
        "all_tags": EventTag.objects.all(),
        "calendar_slot_min_hour": get_site_config().calendar_slot_min_hour,
    }

    return render(request, "edit_event_calendar_index.html", context)


@read_required
def set_edit_preferences(request):
    # Store user preferences as specified in the request's GET variables,
    # and return a JSON object containing all current user preferences
    try:
        volunteer = request.user.volunteer
    except Exception:
        volunteer = None
    edit_prefs.set_preferences(request.session, request.GET, volunteer=volunteer)
    prefs = edit_prefs.get_preferences(request.session, volunteer=volunteer)
    return HttpResponse(json.dumps(prefs), content_type="application/json")


@write_required
@require_http_methods(["GET", "POST"])
def event_detail_view(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    now = timezone.now()
    all_showings = list(event.showings.all().order_by("start"))
    past_showings = [s for s in all_showings if s.start <= now]
    future_showings = [s for s in all_showings if s.start > now]
    latest_showing = all_showings[-1] if all_showings else None

    add_showing_form = diary_forms.ShowingForm()

    if request.method == "POST":
        add_showing_form = diary_forms.ShowingForm(request.POST)
        if add_showing_form.is_valid():
            new_showing = add_showing_form.save(commit=False)
            new_showing.event_id = event_id
            new_showing.save()
            new_showing.clone_or_reset_rota(latest_showing)
            messages.success(
                request,
                "Added {} on {}".format(
                    get_site_config().occurrence_noun,
                    timezone.localtime(new_showing.start).strftime("%d %b %Y, %H:%M"),
                ),
            )
            return HttpResponseRedirect(
                reverse("edit-event-details-view", kwargs={"event_id": event_id})
            )

    has_film_tag = event.tags.filter(slug="film").exists()
    completeness = {
        "has_copy": bool(event.copy and event.copy.strip()),
        "has_copy_summary": bool(event.copy_summary and event.copy_summary.strip()),
        "has_image": event.media.exists(),
        "terms_ok": event.terms_satisfied(),
        "terms_required": event.terms_required(),
        "has_future_showing": bool(future_showings),
        # Only shown when the event has the "film" tag
        "film_details_required": has_film_tag,
        "has_film_details": bool(event.film_id),
    }

    unconfirmed_future_count = sum(
        1 for s in future_showings if not s.confirmed and not s.cancelled
    )

    return render(
        request,
        "view_event_privatedetails.html",
        {
            "event": event,
            "past_showings": past_showings,
            "future_showings": future_showings,
            "add_showing_form": add_showing_form,
            "completeness": completeness,
            "all_showings_in_past": event.all_showings_in_past(),
            "clone_source_showing": latest_showing,
            "unconfirmed_future_count": unconfirmed_future_count,
            # A single-occurrence event reads as one thing; the "dates" concept
            # only surfaces once a second showing exists. See plan: UI collapse.
            "is_series": len(all_showings) > 1,
        },
    )


@write_required
@require_POST
def update_showing_status(request, showing_id):
    showing = get_object_or_404(Showing, pk=showing_id)
    noun = get_site_config().occurrence_noun.capitalize()
    if showing.in_past():
        messages.error(request, f"Can't change status of a past {noun.lower()}")
    else:
        action = request.POST.get("action", "")
        if action == "confirm":
            if not showing.event.terms_satisfied():
                messages.error(
                    request,
                    "Add terms to the event before confirming — "
                    "the event page needs them.",
                )
            else:
                showing.confirmed = True
                showing.save()
                messages.success(request, f"{noun} confirmed — it's now public and on the rota.")
        elif action == "unconfirm":
            showing.confirmed = False
            showing.save()
            messages.success(request, f"{noun} unconfirmed — removed from the programme and rota.")
        elif action == "cancel":
            showing.cancelled = True
            showing.confirmed = False
            showing.save()
            messages.success(request, f"{noun} cancelled — its room bookings are freed.")
        elif action == "uncancel":
            showing.cancelled = False
            showing.save()
            messages.success(request, f"{noun} reinstated.")
        else:
            messages.error(request, "Unknown action.")
    return HttpResponseRedirect(
        reverse("edit-event-details-view", kwargs={"event_id": showing.event_id})
    )


@write_required
@require_POST
def confirm_all_showings(request, event_id):
    """Confirm all unconfirmed future showings on an event in one action."""
    event = get_object_or_404(Event, pk=event_id)
    if not event.terms_satisfied():
        messages.error(
            request,
            "Add terms to the event before confirming showings.",
        )
        return HttpResponseRedirect(
            reverse("edit-event-details-view", kwargs={"event_id": event_id})
        )
    now = timezone.now()
    updated = event.showings.filter(confirmed=False, cancelled=False, start__gt=now).update(
        confirmed=True
    )
    if updated:
        messages.success(request, f"{updated} showing{'s' if updated != 1 else ''} confirmed.")
    else:
        messages.info(request, "No unconfirmed future showings to confirm.")
    return HttpResponseRedirect(
        reverse("edit-event-details-view", kwargs={"event_id": event_id})
    )


@write_required
@require_http_methods(["GET", "POST"])
def clone_event(request, event_id):
    """Clone an existing event as a brand-new event.

    Copies all text/config fields (copy, copy_summary, terms,
    film_information, pricing, pre_title, post_title, outside_hire, private,
    duration, template) and all tags to the new event.  The first showing's
    rota is cloned from the source event's latest showing.  Media (images)
    are not copied — the programmer uploads a fresh image for the new event.
    """
    source_event = get_object_or_404(Event, pk=event_id)
    all_showings = list(source_event.showings.order_by("start"))
    latest_showing = all_showings[-1] if all_showings else None

    if request.method == "POST":
        form = diary_forms.CloneEventForm(request.POST)
        if form.is_valid():
            # Build the new event *without* passing template as a kwarg so
            # that Event.__init__ doesn't try to pull defaults from a
            # potentially-None template — we're copying everything explicitly.
            new_event = Event(
                name=form.cleaned_data["event_name"],
                duration=source_event.duration,
                outside_hire=source_event.outside_hire,
                private=source_event.private,
                pre_title=source_event.pre_title,
                post_title=source_event.post_title,
                pricing=source_event.pricing,
                film_information=source_event.film_information,
                copy=source_event.copy,
                copy_summary=source_event.copy_summary,
                terms=source_event.terms,
                programming_notes=source_event.programming_notes,
                # Ticket link is date-specific — leave blank so programmer
                # notices it needs updating.
            )
            # Set template separately to avoid __init__ auto-population
            new_event.template = source_event.template
            new_event.save()
            # Copy tags from source event
            for tag in source_event.tags.all():
                new_event.tags.add(tag)

            new_showing = Showing(
                event=new_event,
                start=form.cleaned_data["start"],
                booked_by=form.cleaned_data["booked_by"],
                confirmed=False,
            )
            new_showing.save()
            room = form.cleaned_data.get("room")
            if room:
                _create_room_booking(new_showing, room, new_event)
            new_showing.clone_or_reset_rota(latest_showing)

            messages.success(
                request,
                "Cloned '{}' as new event '{}' with showing on {}.".format(
                    source_event.name,
                    new_event.name,
                    timezone.localtime(new_showing.start).strftime("%d %b %Y, %H:%M"),
                ),
            )
            return HttpResponseRedirect(
                reverse("edit-event-details-view", kwargs={"event_id": new_event.pk})
            )
    else:
        # Pre-fill the form with sensible defaults from the source event
        suggested_start = None
        suggested_room = None
        suggested_booked_by = ""
        if latest_showing:
            suggested_start = latest_showing.start + datetime.timedelta(weeks=1)
            suggested_room = latest_showing.primary_room
            suggested_booked_by = latest_showing.booked_by

        form = diary_forms.CloneEventForm(
            initial={
                "event_name": source_event.name,
                "start": suggested_start,
                "room": suggested_room,
                "booked_by": suggested_booked_by,
            }
        )

    return render(
        request,
        "clone_event.html",
        {
            "source_event": source_event,
            "latest_showing": latest_showing,
            "form": form,
        },
    )


@write_required
@require_http_methods(["GET", "POST"])
def batch_add_showings(request, event_id):
    """Add multiple showings to an existing event across several dates at once.

    The programmer picks dates via a flatpickr multi-date picker and sets a
    shared start time, room, and booked_by.  One unconfirmed Showing is
    created per date, each with its rota cloned from the event's latest showing.
    """
    event = get_object_or_404(Event, pk=event_id)
    all_showings = list(event.showings.order_by("start"))
    latest_showing = all_showings[-1] if all_showings else None

    if request.method == "POST":
        form = diary_forms.BatchAddShowingsForm(request.POST, event=event)
        if form.is_valid():
            dates = form.cleaned_data["dates"]
            start_time = form.cleaned_data["start_time"]
            room = form.cleaned_data.get("room")
            booked_by = form.cleaned_data["booked_by"]
            confirmed = form.cleaned_data.get("confirmed", False)

            created = []
            for d in dates:
                naive_dt = datetime.datetime.combine(d, start_time)
                aware_dt = timezone.make_aware(naive_dt)
                showing = Showing(
                    event=event,
                    start=aware_dt,
                    booked_by=booked_by,
                    confirmed=confirmed,
                )
                showing.save()
                if room:
                    _create_room_booking(showing, room, event)
                showing.clone_or_reset_rota(latest_showing)
                showing.create_room_bookings_from_template()
                created.append(showing)

            return render(
                request,
                "batch_add_showings_success.html",
                {
                    "event": event,
                    "created": created,
                },
            )
    else:
        latest_booked_by = latest_showing.booked_by if latest_showing else ""
        latest_room = latest_showing.primary_room if latest_showing else None
        form = diary_forms.BatchAddShowingsForm(
            initial={"booked_by": latest_booked_by, "room": latest_room},
            event=event,
        )

    return render(
        request,
        "batch_add_showings.html",
        {
            "event": event,
            "latest_showing": latest_showing,
            "form": form,
        },
    )


@write_required
@require_http_methods(["GET", "POST"])
def edit_event_links(request, event_id):
    """Edit the (up to 3) resource links attached to an event.

    Links are rendered as clickable chips on the rota view so volunteers can
    quickly reach shared folders, crew chats, planning docs, etc.  Only URLs
    from an approved domain whitelist are accepted (see validators.py).
    """
    event = get_object_or_404(Event, pk=event_id)

    if request.method == "POST":
        formset = diary_forms.EventLinkFormSet(request.POST, instance=event)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Event links saved.")
            return HttpResponseRedirect(
                reverse("edit-event-details-view", kwargs={"event_id": event.pk})
            )
    else:
        formset = diary_forms.EventLinkFormSet(instance=event)

    return render(
        request,
        "edit_event_links.html",
        {
            "event": event,
            "formset": formset,
            "allowed_domains": diary_validators.get_eventlink_allowed_domains(),
        },
    )


@write_required
@require_http_methods(["GET", "POST"])
def quick_create_open_session(request):
    """One-step form for a keyholder to announce the building is open.

    Creates a private, confirmed Event using the 'Building Open' template and
    a single Showing with the given times. The closing time is stored as
    final_volunteer_time so it appears on the rota automatically.
    """
    today = timezone.localtime(timezone.now()).date()

    if request.method == "POST":
        form = diary_forms.QuickCreateOpenSessionForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            template = EventTemplate.objects.filter(name="Building Open").first()

            note = d["note"].strip()
            event_name = f"Building open — {d['date'].strftime('%-d %b')}"

            new_event = Event(
                name=event_name,
                private=True,
                **({'template': template} if template else {}),
            )
            if note:
                new_event.notes = note
            new_event.save()
            new_event.reset_tags_to_default()

            start_dt = datetime.datetime.combine(
                d["date"],
                d["opens_at"],
                tzinfo=timezone.get_current_timezone(),
            )
            new_showing = Showing(
                event=new_event,
                start=start_dt,
                confirmed=True,
                final_volunteer_time=d["closes_at"],
            )
            new_showing.save()
            new_showing.reset_rota_to_default()

            messages.success(
                request,
                f"Building open session created for {d['date'].strftime('%-d %b')},"
                f" {d['opens_at'].strftime('%H:%M')}–{d['closes_at'].strftime('%H:%M')}.",
            )
            return HttpResponseRedirect(
                reverse("edit-event-details-view", kwargs={"event_id": new_event.pk})
            )
    else:
        form = diary_forms.QuickCreateOpenSessionForm(
            initial={"date": today.strftime("%Y-%m-%d")}
        )

    return render(request, "quick_create_open_session.html", {"form": form})


def _template_data():
    """Dict of per-template preview data (roles, rooms, tags, flags) for the new-event form.

    Passed to the template via json_script for safe embedding in JS.
    """
    result = {}
    for t in EventTemplate.objects.prefetch_related(
        "role_slots__role", "default_rooms__room", "tags"
    ).all():
        rooms = [
            {
                "room": rb.room.name,
                "colour": rb.room.colour,
                "start": rb.start_delta_minutes,
                "end": rb.end_delta_minutes,
            }
            for rb in t.default_rooms.all()
        ]
        result[str(t.pk)] = {
            "roles": [
                {"name": r.role.name, "count": r.count} for r in t.role_slots.all()
            ],
            "rooms": rooms,
            "tags": list(t.tags.values_list("name", flat=True)),
            "private": t.private,
            "outside_hire": t.outside_hire,
            "pricing": t.pricing or "",
            "rota_notes": t.rota_notes or "",
        }
    return result


@write_required
@require_http_methods(["GET", "POST"])
def add_event(request):
    # Called GET, with a "date" parameter of the form day-month-year:
    #     returns 'form_new_event_and_showing' with given date filled in.
    # Called POST, with various data in request:
    #     creates new event, and number_of_showings, calls return_to_editindex
    #

    if request.method == "POST":
        # Get event data, plus template and showing time and number of showing
        # days from form. Uses template to set rota roles and tags.
        form = diary_forms.NewEventForm(request.POST)
        if form.is_valid():
            # Event constructor will pull things from the template as
            # appropriate (excluding many/many relation which can only be set
            # after saving)
            entry_mode = form.cleaned_data["entry_mode"]
            new_event = Event(
                name=form.cleaned_data["event_name"],
                template=form.cleaned_data["event_template"],
                duration=form.cleaned_data["duration"],
                outside_hire=form.cleaned_data["outside_hire"],
                private=form.cleaned_data["private"],
                programming_status=(
                    "draft" if entry_mode == "queue" else "active"
                ),
                approval_type=(
                    Event.APPROVAL_STANDING if entry_mode == "standing" else ""
                ),
                target_month=form.cleaned_data.get("target_month"),
            )
            # Set event tags and template links from its template:
            new_event.save()
            new_event.reset_tags_to_default()
            if form.cleaned_data["event_template"]:
                for tl in form.cleaned_data["event_template"].links.all():
                    EventLink.objects.create(
                        event=new_event,
                        label=tl.label,
                        url=tl.url,
                        order=tl.order,
                    )
            # Create one Showing per selected date at the given start time.
            start_time = form.cleaned_data["start_time"]
            new_showing = None
            for d in form.cleaned_data["dates"]:
                aware_dt = timezone.make_aware(datetime.datetime.combine(d, start_time))
                new_showing = Showing(
                    event=new_event,
                    start=aware_dt,
                    discounted=form.cleaned_data["discounted"],
                    booked_by=form.cleaned_data["booked_by"],
                )
                new_showing.save()
                new_showing.reset_rota_to_default()
                new_showing.create_room_bookings_from_template()

            cfg = get_site_config()
            dates = form.cleaned_data["dates"]
            if dates:
                n_dates = len(dates)
                noun = cfg.occurrence_noun if n_dates == 1 else cfg.occurrence_noun_plural
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Added event '{}' with {} {} starting {}".format(
                        new_event.name,
                        n_dates,
                        noun,
                        dates[0].strftime("%-d %b %Y"),
                    ),
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    "Added event '{}' — no date set yet. Add dates from the Event Hub when ready.".format(
                        new_event.name,
                    ),
                )
            if entry_mode == "queue":
                return HttpResponseRedirect(reverse("programming-queue"))
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": new_event.pk},
                )
            )
        else:
            # If form was not valid, re-render the form (which will highlight
            # errors)
            context = {
                "form": form,
                "template_data": _template_data(),
            }
            return render(request, "form_new_event_and_showing.html", context)

    elif request.method == "GET":
        # GET: Show form with date/time pre-filled from query params.
        default_date = django.utils.timezone.now().date() + datetime.timedelta(1)
        date = request.GET.get("date", default_date.strftime("%d-%m-%Y"))
        date = date.split("-")

        # Default start time is 8pm.
        time = request.GET.get("time", "20:00")
        time = time.split(":")
        # Default duration is one hour:
        duration = request.GET.get("duration", "3600")

        if len(time) != 2 or len(date) != 3:
            return HttpResponse(
                "Invalid start date or time",
                status=400,
                content_type="text/plain",
            )
        try:
            date = [int(n, 10) for n in date]
            time = [int(n, 10) for n in time]
            duration = datetime.timedelta(seconds=int(duration, 10))
            initial_date = datetime.date(day=date[0], month=date[1], year=date[2])
            initial_time = datetime.time(hour=time[0], minute=time[1])
        except (ValueError, TypeError):
            return HttpResponse(
                "Illegal time, date or duration",
                status=400,
                content_type="text/plain",
            )

        # Pre-select template if ?template=<pk> was passed (e.g. from template list page)
        template_pk = request.GET.get("template")
        initial_template = None
        if template_pk:
            try:
                initial_template = EventTemplate.objects.get(pk=int(template_pk))
            except (ValueError, EventTemplate.DoesNotExist):
                pass

        # Create form, render template:
        form = diary_forms.NewEventForm(
            initial={
                "dates": initial_date.isoformat(),
                "start_time": initial_time,
                "duration": duration,
                "booked_by": request.user.get_full_name() or request.user.username,
                "event_template": initial_template,
            }
        )
        context = {
            "form": form,
            "template_data": _template_data(),
        }
        return render(request, "form_new_event_and_showing.html", context)


def _get_oneshot_roles_for_showing(showing):
    """Return a list of {pk, name, description, current_count} dicts for one-shot roles on this showing."""
    from django.db.models import Count as _Count

    return list(
        Role.objects.filter(rotaentry__showing=showing, is_one_shot=True)
        .annotate(current_count=_Count("rotaentry"))
        .values("pk", "name", "description", "current_count")
        .distinct()
    )


def _parse_oneshot_roles(post_data, showing):
    """
    Parse oneshot_id_N / oneshot_name_N / oneshot_count_N fields from POST data.
    Returns a dict {role_pk: count} to merge into the rota update dict.
    Existing one-shot roles not present in the submission are included at count=0
    so update_rota() removes their RotaEntries.
    """
    result = {}
    # Seed with 0 for any existing one-shots so omitted rows get cleared
    for role_id in (
        showing.rotaentry_set.filter(role__is_one_shot=True)
        .values_list("role_id", flat=True)
        .distinct()
    ):
        result[role_id] = 0

    i = 0
    while True:
        name_key = f"oneshot_name_{i}"
        if name_key not in post_data:
            break
        name = post_data.get(name_key, "").strip()
        desc = post_data.get(f"oneshot_desc_{i}", "").strip()
        try:
            count = max(0, int(post_data.get(f"oneshot_count_{i}", 0) or 0))
        except (ValueError, TypeError):
            count = 0
        role_id_str = post_data.get(f"oneshot_id_{i}", "")

        if role_id_str.isdigit():
            # Existing one-shot role — update by its PK; persist any description edit
            role_pk = int(role_id_str)
            result[role_pk] = count
            if desc:
                Role.objects.filter(pk=role_pk, is_one_shot=True).update(description=desc)
        elif name and count > 0:
            # New one-shot — find or create by name
            role, _ = Role.objects.get_or_create(
                name=name,
                defaults={"is_one_shot": True, "standard": False, "description": desc},
            )
            if desc and not role.description:
                role.description = desc
                role.save(update_fields=["description"])
            result[role.pk] = count
        i += 1

    return result


@write_required
@require_http_methods(["GET", "POST"])
def edit_showing(request, showing_id=None):
    from toolkit.diary.clash import find_clashes

    showing = get_object_or_404(Showing, pk=showing_id)

    RotaForm = diary_forms.rota_form_factory(showing)
    showing_date = timezone.localtime(showing.start).date()
    rb_form_kwargs = {"showing_date": showing_date}

    if request.method == "POST":
        form = diary_forms.ShowingForm(request.POST, instance=showing)
        rota_form = RotaForm(request.POST)
        rota_notes_form = diary_forms.ShowingRotaNotesForm(
            request.POST, instance=showing
        )
        room_booking_formset = diary_forms.RoomBookingInlineFormSet(
            request.POST, instance=showing, form_kwargs=rb_form_kwargs
        )

        if (
            form.is_valid()
            and rota_form.is_valid()
            and rota_notes_form.is_valid()
            and room_booking_formset.is_valid()
        ):
            modified_showing = form.save()
            rota = rota_form.get_rota()
            rota.update(_parse_oneshot_roles(request.POST, showing))
            modified_showing.update_rota(rota)
            rota_notes_form.save()
            room_booking_formset.save()

            # Clash detection: check all active bookings for this showing
            clashes = []
            for rb in modified_showing.room_bookings.select_related("room").all():
                clashes.extend(find_clashes(rb))

            if clashes:
                # Re-render with clash warnings — don't redirect yet
                room_booking_formset = diary_forms.RoomBookingInlineFormSet(
                    instance=modified_showing, form_kwargs=rb_form_kwargs
                )
                context = {
                    "showing": modified_showing,
                    "form": diary_forms.ShowingForm(instance=modified_showing),
                    "rota_form": RotaForm(),
                    "rota_notes_form": diary_forms.ShowingRotaNotesForm(
                        instance=modified_showing
                    ),
                    "room_booking_formset": room_booking_formset,
                    "clashes": clashes,
                    "max_role_assignment_count": get_site_config().max_count_per_role,
                    "rooms_json": _rooms_json(),
                    "oneshot_roles": _get_oneshot_roles_for_showing(modified_showing),
                }
                return render(request, "form_showing.html", context)

            messages.add_message(
                request,
                messages.SUCCESS,
                "Updated booking for '{}' at {}".format(
                    showing.event.name,
                    showing.start.strftime("%H:%M on %d/%m/%y"),
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": showing.event_id},
                )
            )
    else:
        form = diary_forms.ShowingForm(instance=showing)
        rota_form = RotaForm()
        rota_notes_form = diary_forms.ShowingRotaNotesForm(instance=showing)
        room_booking_formset = diary_forms.RoomBookingInlineFormSet(
            instance=showing, form_kwargs=rb_form_kwargs
        )

    context = {
        "showing": showing,
        "form": form,
        "rota_form": rota_form,
        "rota_notes_form": rota_notes_form,
        "room_booking_formset": room_booking_formset,
        "max_role_assignment_count": get_site_config().max_count_per_role,
        "rooms_json": _rooms_json(),
        "oneshot_roles": _get_oneshot_roles_for_showing(showing),
    }

    return render(request, "form_showing.html", context)


def _rooms_json():
    """Return a JSON-serialisable list of room dicts for the booking map JS."""
    import json

    rooms = Room.objects.all().values("id", "name", "colour", "map_slug")
    return json.dumps(list(rooms))


class EditEventView(PermissionRequiredMixin, View):
    """Handle the "edit event" form."""

    # Quite complex, so a class based view

    permission_required = "toolkit.write"

    def _save(self, event, media_item, form, media_form, generated_media_id=None):
        # Some factored out code: method is passed valid event and media form,
        # and commits the data.

        # When the form was created the copy was converted to HTML, so when
        # saved always clear the "legacy" flag:
        event.legacy_copy = False
        # Then save the main form:
        form.save()

        # Handle generated poster (from AJAX generation) - takes priority
        if generated_media_id:
            try:
                generated_media = MediaItem.objects.get(pk=generated_media_id)
                # Update alt_text from form if provided
                alt_text = media_form.cleaned_data.get("alt_text", "")
                if alt_text:
                    generated_media.alt_text = alt_text
                    generated_media.save()
                event.set_main_mediaitem(generated_media)
                return
            except MediaItem.DoesNotExist:
                pass  # Fall through to normal handling

        # Handle the media item form:
        if media_form.cleaned_data["media_file"] is False:
            # We get here if the "clear" checkbox was ticked.
            #
            # If we just call media_form.save then the MediaItem will have the
            # image removed - we're slightly repurposing the "clear" checkbox
            # to mean "remove the MediaItem from the event", NOT "remove the
            # image from the MediaItem":
            event.clear_main_mediaitem()
        elif media_form.cleaned_data["media_file"] is not None:
            # Get here if the form was submitted with the 'file' field not
            # blank
            #
            # Note that if the image is changed the old image is not deleted
            # from disk. This is Django's default behaviour, and matches what
            # the old toolkit used to do. No image thrown away!
            media_form.save()
            event.set_main_mediaitem(media_item)
        # If the media_form was submitted with blank file name/no data then
        # don't save it (caption is ignored)

    def post(self, request, event_id):
        # Handle POSTing of the "edit event" form. The slightly higher than
        # expected complexity is because there can be more than one media items
        # for an event (even though this isn't currently reflected in the UI).
        #
        # This means that there are two forms: one for the event, and one for
        # the media item. The extra logic is to cover the fact that both
        # records need to be updated.

        # Event object
        event = get_object_or_404(Event, pk=event_id)

        # Get the event's media item, or start a new one:
        media_item = event.get_main_mediaitem() or MediaItem()

        logger.info(
            f"{request.user.last_name} updated booking {event_id} for event '{event.name}'"
        )
        # Create and populate forms:
        form = diary_forms.EventForm(request.POST, instance=event)
        media_form = diary_forms.MediaItemForm(
            request.POST, request.FILES, instance=media_item
        )

        # Validate
        if form.is_valid() and media_form.is_valid():
            event._saved_by = request.user
            generated_media_id = request.POST.get("generated_media_id")
            self._save(event, media_item, form, media_form, generated_media_id)
            messages.add_message(
                request,
                messages.SUCCESS,
                f"Updated details for event '{event.name}'",
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": event_id},
                )
            )

        # Got here if there's a form validation error:
        cfg = get_site_config()
        context = {
            "event": event,
            "event_form": form,
            "media_form": media_form,
            "programme_copy_summary_max_chars": cfg.programme_copy_summary_max_chars,
            "breakeven_guidance_note": cfg.breakeven_guidance_note,
            "breakeven_fc_standard_threshold": cfg.breakeven_fc_standard_threshold,
            "breakeven_fc_music_threshold": cfg.breakeven_fc_music_threshold,
            "thumbnail_crop_width": cfg.thumbnail_crop_width,
            "thumbnail_crop_height": cfg.thumbnail_crop_height,
            "programme_accent_colour": cfg.programme_accent_colour,
            "ticket_link_guidance_html": cfg.ticket_link_guidance_html,
            "film_programming_guide_url": cfg.film_programming_guide_url,
            "omdb_configured": bool(_get_omdb_api_key()),
            "certificate_lookup_url": cfg.certificate_lookup_url,
            "film_cert_lookup_url": _build_cert_lookup_url(cfg.certificate_lookup_url, event.film),
            "structured_cost_terms_enabled": cfg.structured_cost_terms_enabled,
            "has_film_tag": event.tags.filter(slug="film").exists(),
            "event_film_json": json.dumps(_film_json(event.film)) if event.film else "null",
        }
        return render(request, "form_event.html", context)

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)
        # For now only support a single media item:
        media_item = event.get_main_mediaitem() or MediaItem()

        # If the event has "legacy" (ie. non-html) copy then convert it to
        # HTML;
        if event.legacy_copy:
            event.copy = event.copy_html

        form = diary_forms.EventForm(instance=event)
        media_form = diary_forms.MediaItemForm(instance=media_item)

        cfg = get_site_config()

        tag_descriptions = {
            str(t["pk"]): t["description"]
            for t in EventTag.objects.filter(archived=False)
            .exclude(description="")
            .exclude(description__isnull=True)
            .values("pk", "description")
        }

        top_5_tag_pks = list(
            EventTag.objects.filter(archived=False)
            .annotate(event_count=Count("event"))
            .order_by("-event_count")
            .values_list("pk", flat=True)[:5]
        )

        context = {
            "event": event,
            "event_form": form,
            "media_form": media_form,
            "programme_copy_summary_max_chars": cfg.programme_copy_summary_max_chars,
            "breakeven_guidance_note": cfg.breakeven_guidance_note,
            "breakeven_fc_standard_threshold": cfg.breakeven_fc_standard_threshold,
            "breakeven_fc_music_threshold": cfg.breakeven_fc_music_threshold,
            "tag_descriptions_json": mark_safe(_safe_json(tag_descriptions)),
            "top_5_tag_pks_json": mark_safe(json.dumps(top_5_tag_pks)),
            "thumbnail_crop_width": cfg.thumbnail_crop_width,
            "thumbnail_crop_height": cfg.thumbnail_crop_height,
            "programme_accent_colour": cfg.programme_accent_colour,
            "ticket_link_guidance_html": cfg.ticket_link_guidance_html,
            "film_programming_guide_url": cfg.film_programming_guide_url,
            "omdb_configured": bool(_get_omdb_api_key()),
            "certificate_lookup_url": cfg.certificate_lookup_url,
            "film_cert_lookup_url": _build_cert_lookup_url(cfg.certificate_lookup_url, event.film),
            "structured_cost_terms_enabled": cfg.structured_cost_terms_enabled,
            "suggested_film_information": (
                event.film.generate_film_information() if event.film else ""
            ),
            "has_film_tag": event.tags.filter(slug="film").exists(),
            "event_film_json": json.dumps(_film_json(event.film)) if event.film else "null",
        }

        return render(request, "form_event.html", context)


@write_required
def edit_ideas(request, year=None, month=None):
    # GET: return form for editing event for given month/year
    # POST: store editied idea, go back to edit list

    context = {}
    year = int(year)
    month = int(month)

    # Use get or create in order to silently create the ideas entry if it
    # didn't already exist:
    instance, _ = DiaryIdea.objects.get_or_create(
        month=datetime.date(year=year, month=month, day=1)
    )

    if request.method == "POST":
        form = diary_forms.DiaryIdeaForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            if request.POST.get("source") == "inline":
                return HttpResponse(
                    escape(form.cleaned_data["ideas"]),
                    content_type="text/plain",
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Updated ideas for {month}/{year}",
                )
                return _return_to_editindex(request)
    else:
        form = diary_forms.DiaryIdeaForm(instance=instance)

    context["form"] = form
    context["month"] = instance.month

    http_accept = request.META.get("HTTP_ACCEPT", "")
    # This is technically incorrect, as they could be listed with q=0, but
    # in practice it's goog enough:
    if "application/json" in http_accept or "text/javascript" in http_accept:
        response = {
            "month": instance.month.isoformat(),
            "ideas": escape(instance.ideas) if instance.ideas else None,
        }
        return HttpResponse(
            json.dumps(response),
            content_type="application/json; charset=utf-8",
        )
    else:
        return render(request, "form_idea.html", context)


@write_required
@require_POST
def delete_showing(request, showing_id):
    # Delete the given showing

    showing = Showing.objects.get(pk=showing_id)
    event_id = showing.event_id
    if showing.in_past():
        logger.error(
            f"Attempted to delete showing id {showing_id} that has already "
            "started/finished"
        )
        messages.add_message(
            request,
            messages.ERROR,
            "Can't delete bookings that are in the past",
        )
        return HttpResponseRedirect(
            reverse("edit-showing", kwargs={"showing_id": showing_id})
        )
    else:
        logging.info(
            f"Deleting showing id {showing_id} (for event id {showing.event_id})"
        )
        messages.add_message(
            request,
            messages.SUCCESS,
            f"Deleted booking for '{showing.event.name}' on {showing.start.strftime('%d/%m/%y')}",
        )
        showing.delete()

    return HttpResponseRedirect(
        reverse("edit-event-details-view", kwargs={"event_id": event_id})
    )


@feature_required("diary_reports")
def view_terms_report_csv(request, year: int, month: int, day: int) -> HttpResponse:
    query_days_ahead = request.GET.get("daysahead", None)
    start_date, days_ahead = get_date_range(year, month, day, query_days_ahead)
    if start_date is None:
        raise Http404(days_ahead)

    end_date = start_date + datetime.timedelta(days=int(days_ahead))

    showings = (
        Showing.objects.not_cancelled()
        .confirmed()
        .start_in_range(start_date, end_date)
        .order_by("start")
        .select_related()
    )

    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="terms-{start_date.date().isoformat()}.csv"'
        },
    )
    writer = csv.writer(response)
    writer.writerow(["date", "time", "title", "terms"])
    for showing in showings:
        writer.writerow(
            [
                showing.start.date().isoformat(),
                showing.start.time().isoformat(timespec="minutes"),
                showing.event.name,
                showing.event.terms,
            ]
        )

    return response


@feature_required("diary_reports")
def view_event_field(request, field, year=None, month=None, day=None):
    # Method shared across various (slightly primitive) views into event data;
    # the copy, terms and rota reports.
    #
    # This method gets the list of events for the given date range (using the
    # same shared logic for parsing the parameters as the public list / edit
    # list) and then uses the appropriate template to render the results.

    assert field in ("copy", "terms", "rota", "copy_summary")

    query_days_ahead = request.GET.get("daysahead", None)
    start_date, days_ahead = get_date_range(year, month, day, query_days_ahead)
    if start_date is None:
        raise Http404(days_ahead)
    end_date = start_date + datetime.timedelta(days=days_ahead)
    # The rota view should include cancelled showings so volunteers can see what's off.
    # Copy/terms/copy_summary reports only care about active, non-private events.
    showings_qs = Showing.objects.confirmed().start_in_range(start_date, end_date)
    if field != "rota":
        showings_qs = showings_qs.not_cancelled().filter(event__private=False)
    showings = (
        showings_qs
        .order_by("start")
        #              following prefetch is for the rota view
        .prefetch_related("rotaentry_set__role__required_qualification", "rotaentry_set__volunteer__member")
        .select_related()
    )

    search = request.GET.get("search")
    if search:
        logging.info(f"Search term: {search}")
        # Note slightly sneaky use of **; this effectively results in a method
        # call like: showings.filter(event__copy__icontains=search)
        showings = showings.filter(
            Q(**{f"event__{field}__icontains": search})
            | Q(event__name__icontains=search)
        )

    context = {
        "start_date": start_date,
        "end_date": end_date,
        "days_ahead": days_ahead,
        "showings": showings,
        "event_field": field,
        "search": search,
    }

    return render(request, f"view_{field}.html", context)


@feature_required("event_templates")
def edit_event_templates(request):
    """List all event templates with links to per-template edit pages."""
    templates = EventTemplate.objects.prefetch_related("role_slots__role", "tags").all()
    return render(request, "edit_event_templates.html", {"templates": templates})


@feature_required("event_templates")
def edit_event_template_detail(request, template_id=None):
    """Create or edit a single event template."""
    if template_id is not None:
        event_template = get_object_or_404(EventTemplate, pk=template_id)
    else:
        event_template = None

    if request.method == "POST":
        if "delete" in request.POST and event_template is not None:
            name = event_template.name
            event_template.delete()
            logger.info("Event template '%s' deleted", name)
            messages.add_message(
                request, messages.SUCCESS, f"Deleted template '{name}'"
            )
            return HttpResponseRedirect(reverse("edit_event_templates"))

        form = diary_forms.EventTemplateForm(request.POST, instance=event_template)
        roles_formset = diary_forms.EventTemplateRoleFormSet(
            request.POST, instance=event_template or EventTemplate()
        )
        links_formset = diary_forms.EventTemplateLinkFormSet(
            request.POST, instance=event_template or EventTemplate()
        )
        rooms_formset = diary_forms.EventTemplateRoomFormSet(
            request.POST, instance=event_template or EventTemplate()
        )

        if (
            form.is_valid()
            and roles_formset.is_valid()
            and links_formset.is_valid()
            and rooms_formset.is_valid()
        ):
            saved = form.save()
            roles_formset.instance = saved
            roles_formset.save()
            links_formset.instance = saved
            links_formset.save()
            rooms_formset.instance = saved
            rooms_formset.save()
            logger.info("Event template '%s' saved", saved.name)
            messages.add_message(
                request, messages.SUCCESS, f"Saved template '{saved.name}'"
            )
            return HttpResponseRedirect(reverse("edit_event_templates"))
    else:
        form = diary_forms.EventTemplateForm(instance=event_template)
        roles_formset = diary_forms.EventTemplateRoleFormSet(instance=event_template)
        links_formset = diary_forms.EventTemplateLinkFormSet(instance=event_template)
        rooms_formset = diary_forms.EventTemplateRoomFormSet(instance=event_template)

    export_json = None
    if event_template is not None:
        export_json = _export_template_json(event_template)

    context = {
        "form": form,
        "roles_formset": roles_formset,
        "links_formset": links_formset,
        "rooms_formset": rooms_formset,
        "event_template": event_template,
        "export_json": export_json,
        "allowed_domains": diary_validators.get_eventlink_allowed_domains(),
    }
    return render(request, "edit_event_template_detail.html", context)


def _export_template_json(template):
    """Serialise an EventTemplate to a JSON string suitable for copy-paste export."""
    data = {
        "name": template.name,
        "pricing": template.pricing or "",
        "film_information": template.film_information or "",
        "copy_summary": template.copy_summary or "",
        "copy": template.copy or "",
        "terms": template.terms or "",
        "rota_notes": template.rota_notes or "",
        "private": template.private,
        "outside_hire": template.outside_hire,
        "tags": [t.name for t in template.tags.order_by("name")],
        "role_slots": [
            {"role": slot.role.name, "count": slot.count}
            for slot in template.role_slots.select_related("role").order_by("role__name")
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET", "POST"])
def import_event_template(request):
    """Import a template from JSON (Panopticon only).

    Handles same-name conflict via an 'overwrite' checkbox.  When unchecked
    and a template with the given name exists, the import creates a copy
    suffixed with " (copy)".
    """
    if request.method == "POST":
        json_text = request.POST.get("json_text", "").strip()
        overwrite = request.POST.get("overwrite") == "1"
        errors = []
        template = None

        if not json_text:
            errors.append("Paste a JSON template to import.")
        else:
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON: {exc}")
                data = None

            if data is not None:
                name = (data.get("name") or "").strip()
                if not name:
                    errors.append("Template JSON must contain a non-empty 'name' field.")
                else:
                    existing = EventTemplate.objects.filter(name=name).first()
                    if existing and overwrite:
                        template = existing
                        template.role_slots.all().delete()
                        template.tags.clear()
                    elif existing and not overwrite:
                        name = f"{name} (copy)"
                        template = EventTemplate(name=name)
                    else:
                        template = EventTemplate(name=name)

                    if not errors:
                        template.pricing = data.get("pricing") or ""
                        template.film_information = data.get("film_information") or ""
                        template.copy_summary = data.get("copy_summary") or ""
                        template.copy = data.get("copy") or ""
                        template.terms = data.get("terms") or ""
                        template.rota_notes = data.get("rota_notes") or ""
                        template.private = bool(data.get("private", False))
                        template.outside_hire = bool(data.get("outside_hire", False))
                        template.save()

                        tag_warnings = []
                        for tag_name in data.get("tags") or []:
                            try:
                                tag = EventTag.objects.get(name=tag_name)
                                template.tags.add(tag)
                            except EventTag.DoesNotExist:
                                tag_warnings.append(tag_name)

                        role_warnings = []
                        for slot in data.get("role_slots") or []:
                            role_name = (slot.get("role") or "").strip()
                            count = slot.get("count", 1)
                            try:
                                role = Role.objects.get(name=role_name)
                                EventTemplateRole = template.role_slots.model
                                EventTemplateRole.objects.create(
                                    template=template, role=role, count=count
                                )
                            except Role.DoesNotExist:
                                role_warnings.append(role_name)

                        msg = f"Imported template '{template.name}'."
                        if tag_warnings:
                            msg += f" Unknown tags skipped: {', '.join(tag_warnings)}."
                        if role_warnings:
                            msg += f" Unknown roles skipped: {', '.join(role_warnings)}."
                        messages.success(request, msg)
                        return HttpResponseRedirect(
                            reverse("edit_event_template_detail", kwargs={"template_id": template.pk})
                        )

        return render(
            request,
            "import_event_template.html",
            {
                "errors": errors,
                "json_text": json_text,
                "overwrite": overwrite,
            },
        )

    return render(request, "import_event_template.html", {})


@feature_required("event_tags")
def edit_event_tags(request):
    active_qs = EventTag.objects.filter(archived=False)
    archived_qs = EventTag.objects.filter(archived=True)

    _filter_group_choices = [("", "—")] + [
        (slug, label) for slug, label in settings.PROGRAMME_FILTER_GROUPS
    ]

    class EventTagForm(django_forms.ModelForm):
        filter_group = django_forms.ChoiceField(
            choices=_filter_group_choices,
            required=False,
            label="Filter group",
        )
        description = django_forms.CharField(
            required=False,
            label="When to use",
            widget=django_forms.TextInput(
                attrs={"placeholder": "e.g. Use for hands-on learning sessions."}
            ),
        )

        class Meta:
            model = EventTag
            fields = ("name", "promoted", "sort_order", "filter_group", "description")

        def clean_filter_group(self):
            return self.cleaned_data["filter_group"] or None

        def clean_description(self):
            return self.cleaned_data["description"] or None

    event_tag_formset = modelformset_factory(
        EventTag,
        form=EventTagForm,
        fields=("name", "promoted", "sort_order", "filter_group", "description"),
        can_delete=False,
    )

    if request.method == "POST":
        action = request.POST.get("_action")
        if action == "archive":
            tag_id = request.POST.get("tag_id")
            try:
                tag = EventTag.objects.get(pk=tag_id)
                tag.delete()  # model.delete() archives if used, deletes if unused
                messages.add_message(request, messages.SUCCESS, f"Tag '{tag.name}' archived.")
            except EventTag.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_event_tags"))
        elif action == "restore":
            tag_id = request.POST.get("tag_id")
            try:
                tag = EventTag.objects.get(pk=tag_id)
                tag.archived = False
                tag.save()
                messages.add_message(request, messages.SUCCESS, f"Tag '{tag.name}' restored.")
            except EventTag.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_event_tags"))
        else:
            formset = event_tag_formset(request.POST, queryset=active_qs)
            if formset.is_valid():
                logger.info("Event tags updated")
                formset.save()
                messages.add_message(request, messages.SUCCESS, "Event tags updated")
                return HttpResponseRedirect(reverse("edit_event_tags"))
    else:
        formset = event_tag_formset(queryset=active_qs)

    context = {"formset": formset, "archived_tags": archived_qs}
    return render(request, "edit_event_tags.html", context)


@feature_required("roles")
def edit_roles(request):
    # This is pretty slow, but it's not a commonly used bit of the UI.
    active_qs = (
        Role.objects.filter(archived=False, is_one_shot=False)
        .select_related("required_qualification")
        .annotate(rota_count=Count("rotaentry"))
    )
    archived_qs = Role.objects.filter(archived=True, is_one_shot=False)

    RoleFormset = modelformset_factory(
        Role,
        diary_forms.RoleForm,
        fields=(
            "name",
            "standard",
            "description",
            "beginner_friendly",
            "wheelchair_accessible",
            "keyholder_only",
            "required_qualification",
            "qualification_gate",
        ),
        can_delete=False,
    )

    if request.method == "POST":
        action = request.POST.get("_action")
        if action == "archive":
            role_id = request.POST.get("role_id")
            try:
                role = Role.objects.get(pk=role_id)
                role.delete()  # model.delete() archives if used, deletes if unused
                messages.add_message(request, messages.SUCCESS, f"Role '{role.name}' archived.")
            except Role.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "restore":
            role_id = request.POST.get("role_id")
            try:
                role = Role.objects.get(pk=role_id)
                role.archived = False
                role.save()
                messages.add_message(request, messages.SUCCESS, f"Role '{role.name}' restored.")
            except Role.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "add_qualification":
            qual_name = request.POST.get("qualification_name", "").strip()
            qual_notes = request.POST.get("qualification_notes", "").strip()
            if qual_name:
                qual, created = Qualification.objects.get_or_create(name=qual_name)
                if created:
                    qual.notes = qual_notes
                    qual.save()
                    messages.add_message(request, messages.SUCCESS, f"Qualification '{qual_name}' added.")
                else:
                    messages.add_message(request, messages.WARNING, f"Qualification '{qual_name}' already exists.")
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "edit_qualification":
            qual_id = request.POST.get("qualification_id")
            try:
                qual = Qualification.objects.get(pk=qual_id)
                new_name = request.POST.get("qualification_name", "").strip()
                new_notes = request.POST.get("qualification_notes", "").strip()
                if not new_name:
                    messages.add_message(request, messages.ERROR, "Qualification name cannot be blank.")
                elif new_name != qual.name and Qualification.objects.filter(name=new_name).exists():
                    messages.add_message(request, messages.ERROR, f"A qualification named '{new_name}' already exists.")
                else:
                    qual.name = new_name
                    qual.notes = new_notes
                    qual.save()
                    messages.add_message(request, messages.SUCCESS, f"Qualification '{qual.name}' updated.")
            except Qualification.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "delete_qualification":
            qual_id = request.POST.get("qualification_id")
            try:
                qual = Qualification.objects.get(pk=qual_id)
                if qual.required_for_roles.exists():
                    messages.add_message(
                        request, messages.ERROR,
                        f"Cannot delete '{qual.name}' — it is required by one or more roles. "
                        "Remove the requirement from those roles first."
                    )
                else:
                    qual.delete()
                    messages.add_message(request, messages.SUCCESS, f"Qualification '{qual.name}' deleted.")
            except Qualification.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        else:
            formset = RoleFormset(request.POST, queryset=active_qs)
            if formset.is_valid():
                logger.info("Roles updated")
                formset.save()
                messages.add_message(request, messages.SUCCESS, "Roles updated")
                return HttpResponseRedirect(reverse("edit_roles"))
    else:
        formset = RoleFormset(queryset=active_qs)

    return render(request, "form_edit_roles.html", {
        "formset": formset,
        "archived_roles": archived_qs,
        "all_qualifications": Qualification.objects.all(),
    })


@feature_required("printed_programmes")
def printed_programme_edit(request, operation):
    assert operation in ("edit", "add")

    programme_queryset = PrintedProgramme.objects.order_by("month")
    programme_formset = modelformset_factory(
        PrintedProgramme,
        fields=("programme", "designer", "notes"),
        can_delete=True,
        extra=0,
    )

    # Blank forms, for use in GET or for whichever form hasn't been POSTed
    formset = programme_formset(queryset=programme_queryset)
    new_programme_form = diary_forms.NewPrintedProgrammeForm()

    if request.method == "POST":
        if operation == "edit":
            formset = programme_formset(
                request.POST, request.FILES, queryset=programme_queryset
            )
            edited_form = formset
        elif operation == "add":
            new_programme_form = diary_forms.NewPrintedProgrammeForm(
                request.POST, request.FILES
            )
            edited_form = new_programme_form

        if edited_form.is_valid():
            try:
                # Without a transaction an IntegrityError will leave a broken
                # transaction
                with django.db.transaction.atomic():
                    edited_form.save()
            except django.db.IntegrityError:
                edited_form.add_error(
                    "form_month",
                    "Printed programme with this month/year already exists.",
                )
            else:
                logger.info("Printed programme archive updated")
                return HttpResponseRedirect(reverse("edit-printed-programmes"))

    context = {
        "formset": formset,
        "new_programme_form": new_programme_form,
    }

    return render(request, "form_printedprogramme_archive.html", context)


@feature_required("rota_vacancies")
def view_rota_vacancies(request):
    try:
        days_ahead = int(request.GET.get("daysahead"))
    except (ValueError, TypeError):
        days_ahead = None
    if not days_ahead or days_ahead < 1 or days_ahead > 60:
        days_ahead = 30

    start = timezone.now()
    end_date = start + datetime.timedelta(days=days_ahead)
    showings = (
        Showing.objects.not_cancelled()
        .confirmed()
        .start_in_range(start, end_date)
        .order_by("start")
        .prefetch_related("rotaentry_set__role")
        .select_related("event")
    )
    showings_vacant_roles = OrderedDict(
        (
            showing,
            list(showing.rotaentry_set.filter(Q(name="") | Q(name__isnull=True))),
        )
        for showing in showings
    )

    # Collect all distinct role names across all vacancies for the filter UI.
    all_role_names = sorted(
        {
            entry.role.name
            for entries in showings_vacant_roles.values()
            for entry in entries
        }
    )

    # Surprisingly round-about way to get tomorrow's date:
    now_local = django.utils.timezone.localtime(django.utils.timezone.now())

    context = {
        "days_ahead": days_ahead,
        "now": now_local,
        "now_plus_1d": now_local + datetime.timedelta(days=1),
        "rota_edit_url": request.build_absolute_uri(reverse("rota-edit")),
        "showings_vacant_roles": showings_vacant_roles,
        "all_role_names": all_role_names,
    }

    return render(request, "view_rota_vacancies.html", context)


class EditRotaView(PermissionRequiredMixin, View):
    """Handle the "edit rota" page."""

    permission_required = "diary.change_rotaentry"

    def get(self, request, year=None, day=None, month=None):
        # Fiddly way to set startdate to the start of the local day:
        # Get current UTC time and convert to local time:
        now_local = django.utils.timezone.localtime(django.utils.timezone.now())
        # Create a new local time with hour/min/sec set to zero:
        current_tz = django.utils.timezone.get_current_timezone()
        today_local_date = datetime.datetime(
            now_local.year, now_local.month, now_local.day, tzinfo=current_tz
        )
        yesterday_local_date = today_local_date - datetime.timedelta(days=1)

        query_days_ahead = request.GET.get("daysahead", None)
        start_date, days_ahead = get_date_range(
            year, month, day, query_days_ahead, default_days_ahead=92
        )

        if not request.user.is_superuser:
            # Allow up to 1 month back (past entries are display-only; POST
            # handler blocks edits to in-past showings server-side).
            one_month_ago = today_local_date - datetime.timedelta(days=31)
            if start_date < one_month_ago:
                start_date = one_month_ago

        end_date = start_date + datetime.timedelta(days=days_ahead)
        showings = (
            Showing.objects.confirmed()
            .start_in_range(start_date, end_date)
            .order_by("start")
            #              force sane number of queries:
            .prefetch_related(
            "rotaentry_set__role",
            "rotaentry_set__volunteer__member",
            "event__tags",
        )
            .select_related()
        )

        # Used by per-showing rota notes click to edit control:
        url_with_id = reverse("edit-showing-rota-notes", kwargs={"showing_id": 999})
        showing_notes_url_prefix = url_with_id[: url_with_id.find("999")]

        # Load the current user's event marks (one per event) for JS serialisation.
        # Keyed by event_id -> mark_type string ("star" or "shadow").
        rota_marks: dict[int, str] = {}
        can_mark_events = False
        current_volunteer_pk = ""
        # Returning (Dormant) volunteers get the beginner-friendly role highlight
        # forced on, overriding their stored localStorage preference, to help them
        # ease back in. Everyone else keeps their own toggle state.
        force_beginner_highlight = False
        from toolkit.members.models import Volunteer as _Volunteer
        try:
            volunteer = request.user.volunteer
            can_mark_events = True
            current_volunteer_pk = str(volunteer.pk)
            force_beginner_highlight = (
                volunteer.status == _Volunteer.STATUS_DORMANT
            )
            event_ids = [s.event_id for s in showings]
            for mark in VolunteerEventMark.objects.filter(
                volunteer=volunteer, event_id__in=event_ids
            ):
                rota_marks[mark.event_id] = mark.mark_type
        except Exception:
            pass

        # Pronouns tooltip on rota names: build a lookup from active volunteers
        # whose Member record has personal_pronouns set, then attach a `pronouns`
        # attribute to each prefetched rota entry. Match on case-insensitive
        # full name. (Not visible to the public — this view is permission-gated.)
        pronouns_by_name: dict[str, str] = {}
        for v in _Volunteer.objects.active().select_related("member"):
            if v.member.personal_pronouns:
                key = v.member.name.strip().lower()
                if key:
                    pronouns_by_name[key] = v.member.personal_pronouns
        for showing in showings:
            for entry in showing.rotaentry_set.all():
                if entry.volunteer_id and entry.volunteer.member.personal_pronouns:
                    entry.pronouns = entry.volunteer.member.personal_pronouns
                else:
                    entry.pronouns = pronouns_by_name.get(
                        (entry.name or "").strip().lower(), ""
                    )

        site_config = get_site_config()
        context = {
            "start_date": start_date,
            "end_date": end_date,
            "days_ahead": days_ahead,
            "showings": showings,
            "edit_showing_notes_url_prefix": showing_notes_url_prefix,
            "rota_clear_email_prompt_enabled": site_config.rota_clear_email_prompt_enabled,
            "rota_clear_email_prompt_text": site_config.rota_clear_email_prompt_text,
            "rota_vols_email": site_config.vols_email or settings.VENUE.get("vols_email", ""),
            "rota_show_tags": site_config.rota_show_tags,
            "can_mark_events": can_mark_events,
            "rota_marks_json": json.dumps(rota_marks),
            "current_volunteer_pk": current_volunteer_pk,
            "force_beginner_highlight": force_beginner_highlight,
        }

        return render(request, "edit_rota.html", context)

    def post(self, request, year=None, day=None, month=None):
        # Get rota entry
        try:
            entry_id = int(request.POST["id"])
        except (ValueError, KeyError):
            logger.error("Invalid entry_id")
            return HttpResponse(
                "Invalid entry id", status=400, content_type="text/plain"
            )
        rota_entry = get_object_or_404(RotaEntry, pk=entry_id)

        # Check associated showing:
        if rota_entry.showing.in_past():
            return HttpResponse(
                "Can't change rota for showings in the past", status=403
            )

        # Get entered name, and store in rota entry:
        try:
            name = request.POST["value"]
        except KeyError:
            return HttpResponse(
                "Invalid request", status=400, content_type="text/plain"
            )

        # Resolve the current user's volunteer record (all users are volunteers).
        linked_volunteer = None
        try:
            linked_volunteer = request.user.volunteer
        except Exception:
            pass

        # Track whether this sign-up triggers an advisory qualification notice.
        qualification_advisory: str | None = None

        if name == "signup":
            # Tap-to-toggle self-signup for any user tier (superusers included).
            # Superusers use their [e] button for free-text edits, which sends the
            # typed name rather than the 'signup' sentinel.
            if not linked_volunteer:
                return HttpResponse("No volunteer account linked", status=400)

            # Qualification gate: check only when signing up (not clearing).
            # Superusers bypass so coordinators can always place someone manually.
            if not request.user.is_superuser:
                role = rota_entry.role
                if role and role.required_qualification and role.qualification_gate != Role.GATE_OFF:
                    has_qual = VolunteerQualification.objects.filter(
                        volunteer=linked_volunteer,
                        qualification=role.required_qualification,
                    ).exists()
                    if not has_qual:
                        if role.qualification_gate == Role.GATE_BLOCKING:
                            return HttpResponse(
                                f"This role requires the '{role.required_qualification.name}' qualification. "
                                "Please speak to a coordinator if you believe you're qualified.",
                                status=403,
                                content_type="text/plain",
                            )
                        # advisory: allow but attach a notice header the JS will surface
                        qualification_advisory = (
                            f"This role normally requires the '{role.required_qualification.name}' "
                            "qualification. If you haven't done it yet, please speak to a coordinator."
                        )

            rota_entry.volunteer = linked_volunteer
            rota_entry.name = linked_volunteer.member.name
        elif linked_volunteer and name and not request.user.is_superuser:
            # Non-superuser volunteer submitting text (e.g. direct API call):
            # coerce to canonical name regardless of what was typed.
            rota_entry.volunteer = linked_volunteer
            rota_entry.name = linked_volunteer.member.name
        elif name:
            # Superuser free-text edit via [e] button, or non-volunteer account.
            rota_entry.volunteer = None
            rota_entry.name = name
        else:
            # Clearing a slot.
            rota_entry.volunteer = None
            rota_entry.name = ""

        logger.info(
            "Update role id {0} (#{1}) for showing {2} '{3}' -> '{4}' ({5})".format(
                rota_entry.role_id,
                rota_entry.rank,
                rota_entry.showing_id,
                rota_entry.name,
                name,
                rota_entry.pk,
            )
        )

        rota_entry.save()

        response = HttpResponse(escape(rota_entry.name), content_type="text/plain")
        if qualification_advisory:
            response["X-Qualification-Advisory"] = qualification_advisory
        return response


@permission_required("diary.change_rotaentry")
@require_POST
def edit_showing_rota_notes(request, showing_id):
    showing = get_object_or_404(Showing, pk=showing_id)
    form = diary_forms.ShowingRotaNotesForm(request.POST, instance=showing)

    if showing.in_past():
        return HttpResponse("Can't change rota for showings in the past", status=403)
    elif form.is_valid():
        form.save()
    else:
        logger.error("Rota notes edit form not valid!")
        return HttpResponse("Unknown error", status=500, content_type="text/plain")

    return HttpResponse(showing.rota_notes, content_type="text/plain")


# Doesn't need permission check, as will only return messages for the current
# user:
def get_messages(request):
    message_list = [
        {"message": m.message, "tags": m.tags, "level": m.level}
        for m in messages.get_messages(request)
    ]

    return HttpResponse(json.dumps(message_list), content_type="application/json")


@require_POST
@permission_required("diary.change_rotaentry")
def toggle_event_mark(request):
    """Set or clear the ★/☽ mark for the current user on an event. Returns JSON.

    Accepts mark_type: "star", "shadow", or "" (clear).
    One mark per (volunteer, event) — setting a new type replaces any existing one.
    """
    mark_type = request.POST.get("mark_type", "")
    event_id = request.POST.get("event_id")

    if mark_type not in ("", VolunteerEventMark.MARK_STAR, VolunteerEventMark.MARK_SHADOW):
        return JsonResponse({"error": "Invalid mark type"}, status=400)

    try:
        event = Event.objects.get(pk=event_id)
    except (Event.DoesNotExist, ValueError):
        return JsonResponse({"error": "Event not found"}, status=404)

    try:
        volunteer = request.user.volunteer
    except Exception:
        return JsonResponse({"error": "No volunteer record for this user"}, status=403)

    if not mark_type:
        VolunteerEventMark.objects.filter(volunteer=volunteer, event=event).delete()
    else:
        VolunteerEventMark.objects.update_or_create(
            volunteer=volunteer,
            event=event,
            defaults={"mark_type": mark_type},
        )

    return JsonResponse({"mark_type": mark_type})


@write_required
def view_force_error(request):
    raise AssertionError("Forced exception")


@user_passes_test(lambda u: u.is_superuser)
def edit_site_configuration(request):
    """Panopticon-only page for editing the SiteConfiguration singleton."""

    config = get_site_config()

    field_groups = [
        (
            "Display & UX",
            [
                "films_start_on_time",
                "films_start_on_time_banner_text",
                "rota_show_tags",
                "rota_clear_email_prompt_enabled",
                "rota_clear_email_prompt_text",
                "vols_email",
                "show_archive_images",
                "images_start_date",
            ],
        ),
        (
            "Terminology",
            [
                "occurrence_noun",
                "occurrence_noun_plural",
                "confirm_label",
            ],
        ),
        (
            "Age ratings",
            ["age_rating_choices"],
        ),
        (
            "Break-even calculator",
            [
                "breakeven_guidance_note",
                "breakeven_fc_standard_threshold",
                "breakeven_fc_music_threshold",
            ],
        ),
        (
            "Calendar",
            ["calendar_slot_min_hour"],
        ),
        (
            "Programme limits",
            [
                "max_count_per_role",
                "max_showing_dates_shown",
                "programme_copy_summary_max_chars",
                "programme_event_terms_min_words",
                "programme_media_max_size_mb",
                "thumbnail_crop_width",
                "thumbnail_crop_height",
                "programme_accent_colour",
            ],
        ),
        (
            "Mailout",
            ["mailout_details_days_ahead", "mailout_listings_days_ahead"],
        ),
        (
            "Membership & volunteers",
            [
                "membership_length_days",
                "default_training_expiry_months",
                "general_training_enabled",
                "volunteer_dormancy_days",
                "volunteer_never_logged_in_grace_days",
                "volunteer_purge_days",
                "volunteer_digest_day",
            ],
        ),
        (
            "Last-gasp re-engagement email",
            [
                "last_gasp_email_enabled",
                "last_gasp_email_subject",
                "last_gasp_email_body",
                "last_gasp_cooldown_days",
            ],
        ),
        (
            "Suspension email",
            [
                "suspension_email_subject",
                "suspension_email_body",
            ],
        ),
        (
            "Dashboard",
            ["rota_gap_min_missing", "rota_gap_min_pct"],
        ),
        (
            "Volunteer stats",
            ["programming_min_event_shifts", "stats_programming_note", "stats_training_tag_slugs"],
        ),
        (
            "Guidance URLs",
            [
                "image_copyright_guidance_url",
                "alt_text_guidance_url",
                "access_rider_guidance_url",
                "ticket_link_guidance_html",
                "film_programming_guide_url",
            ],
        ),
        (
            "Structured cost terms",
            ["structured_cost_terms_enabled", "structured_cost_required"],
        ),
        (
            "Community exchange",
            ["community_exchange_enabled"],
        ),
        (
            "Lost & found",
            ["lost_and_found_retain_days"],
        ),
        (
            "Bulletins",
            ["bulletin_default_expiry_days", "bulletin_guidance", "bulletin_post_permission"],
        ),
        (
            "Event links",
            ["eventlink_extra_allowed_domains"],
        ),
        (
            "Collectives",
            ["collectives_intro", "collectives_mailing_list_signup_url"],
        ),
        (
            "Donations page",
            ["donations_intro", "show_donations_in_public_nav"],
        ),
        (
            "Site-wide banner",
            [
                "banner_active",
                "banner_level",
                "banner_text",
                "banner_dismissible",
            ],
        ),
        (
            "External APIs",
            ["omdb_api_key", "certificate_lookup_url"],
        ),
    ]

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
        (label, [form[name] for name in names]) for label, names in field_groups
    ]

    # Permission table: configurable rows carry the bound form field so the template
    # can render a dropdown; fixed rows carry only a display string.
    from toolkit.diary.models import SiteConfiguration
    _level_labels = dict(SiteConfiguration.PERMISSION_LEVEL_CHOICES)
    def _fixed(label):
        return {"field": None, "display": label}
    def _configurable(field_name):
        return {"field": form[field_name], "display": _level_labels.get(getattr(config, field_name), "?")}
    permission_rows = [
        ("Diary — view diary list", _configurable("perm_diary_read")),
        ("Diary — create / edit events", _fixed("Programmer+")),
        ("Diary — calendar", _configurable("perm_diary_calendar")),
        ("Diary — programming queue (view)", _configurable("perm_programming_queue_read")),
        ("Diary — programming queue (change status)", _configurable("perm_programming_queue_write")),
        ("Diary — event templates (list & detail)", _configurable("perm_event_templates")),
        ("Diary — event templates (import)", _fixed("Panopticon only")),
        ("Diary — event tags", _configurable("perm_event_tags")),
        ("Diary — roles", _configurable("perm_roles")),
        ("Diary — rooms", _configurable("perm_rooms")),
        ("Diary — copy / terms / text reports", _configurable("perm_diary_reports")),
        ("Diary — upload printed programmes", _configurable("perm_printed_programmes")),
        ("Rota — view and sign up", _fixed("All volunteers")),
        ("Rota — vacancies page", _configurable("perm_rota_vacancies")),
        ("Community — post bulletins", _fixed("Configurable (see Bulletins section)")),
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
        media_item = generate_event_placeholder(event, colour_hex=colour_hex or None)
        return JsonResponse({
            "success": True,
            "media_id": media_item.id,
            "url": media_item.media_file.url,
            "filename": os.path.basename(media_item.media_file.name),
        })
    except Exception as exc:
        logger.exception("Failed to generate poster for event %s", event_id)
        return JsonResponse(
            {"success": False, "error": str(exc)},
            status=500
        )


@feature_required("rooms")
@require_http_methods(["GET", "POST"])
def edit_rooms(request):
    """List all rooms; handle create-new-room POST."""
    if request.method == "POST":
        form = diary_forms.RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            logger.info("Room '%s' created", room.name)
            messages.success(request, f"Room '{room.name}' created.")
            return HttpResponseRedirect(reverse("edit_rooms"))
    else:
        form = diary_forms.RoomForm()

    rooms = Room.objects.all().order_by("-is_primary", "name")
    return render(request, "edit_rooms.html", {"rooms": rooms, "form": form})


@feature_required("rooms")
@require_http_methods(["GET", "POST"])
def edit_room_detail(request, room_id):
    """Edit or delete a single room."""
    room = get_object_or_404(Room, pk=room_id)

    if request.method == "POST":
        if "delete" in request.POST:
            if room.bookings.exists():
                messages.error(
                    request,
                    f"Cannot delete '{room.name}' — it is still used by one or more showings.",
                )
                return HttpResponseRedirect(reverse("edit_rooms"))
            name = room.name
            room.delete()
            logger.info("Room '%s' deleted", name)
            messages.success(request, f"Room '{name}' deleted.")
            return HttpResponseRedirect(reverse("edit_rooms"))

        form = diary_forms.RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            logger.info("Room '%s' updated", room.name)
            messages.success(request, f"Room '{room.name}' updated.")
            return HttpResponseRedirect(reverse("edit_rooms"))
    else:
        form = diary_forms.RoomForm(instance=room)

    return render(request, "edit_room_detail.html", {"room": room, "form": form})


@feature_required("programming_queue_read")
def programming_queue(request):
    """Show all events in the programming queue (draft, proposed, or returned for changes)."""
    queue = (
        Event.objects.filter(programming_status__in=["draft", "proposed", "rejected"])
        .prefetch_related("showings", "showings__room_bookings__room", "tags", "template__tags")
        .select_related("template")
        .annotate(first_showing_start=Min("showings__start"))
        .order_by("first_showing_start")
    )
    # Attach epoch timestamps for client-side sorting.
    # Django templates block attributes starting with underscores, so we use
    # plain attribute names via a wrapper list of dicts.
    queue_items = []
    for event in queue:
        queue_items.append({
            "event": event,
            "sort_event_date": (
                int(event.first_showing_start.timestamp()) if event.first_showing_start else 9999999999
            ),
            "sort_submitted": int(event.created_at.timestamp()),
            "sort_status_changed": (
                int(event.programming_status_changed_at.timestamp())
                if event.programming_status_changed_at
                else int(event.created_at.timestamp())
            ),
        })
    cfg = get_site_config()
    return render(request, "programming_queue.html", {
        "queue": queue_items,
        "fc_standard_threshold": cfg.breakeven_fc_standard_threshold,
        "fc_music_threshold": cfg.breakeven_fc_music_threshold,
        "can_write": request.user.has_perm("toolkit.write"),
    })


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
        messages.success(request, f"'{event.name}' added to the programming queue.")
    elif action == "withdraw":
        event.programming_status = "draft"
        status_changed = True
        messages.info(request, f"'{event.name}' withdrawn from the queue — back to draft.")
    elif action == "make_active":
        event.programming_status = "active"
        status_changed = True
        messages.success(request, f"'{event.name}' marked as active.")
    elif action == "return_for_changes":
        event.programming_status = "rejected"
        status_changed = True
        messages.warning(request, f"'{event.name}' returned to the proposer for changes.")
    elif action == "approve_at_meeting":
        event.programming_status = "active"
        event.approval_type = "meeting"
        event.approved_at_meeting_date = timezone.now().date()
        status_changed = True
        messages.success(request, f"'{event.name}' approved at today's meeting.")
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
    if not next_url or not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("edit-event-details-view", kwargs={"event_id": event_id})
    return HttpResponseRedirect(next_url)


# ---------------------------------------------------------------------------
# Film metadata views (TMDB integration — 9.66)
# ---------------------------------------------------------------------------


def _build_cert_lookup_url(url_template: str, film) -> str:
    """Substitute {title} and {year} into the certificate lookup URL template."""
    if not url_template or not film:
        return ""
    from urllib.parse import quote
    return (
        url_template
        .replace("{title}", quote(film.title or ""))
        .replace("{year}", quote(str(film.year or "")))
    )


def _get_omdb_api_key() -> str:
    """Return the active OMDb API key: DB setting takes precedence over env var."""
    from toolkit.diary.models import get_site_config
    db_key = get_site_config().omdb_api_key.strip()
    return db_key or settings.OMDB_API_KEY


@write_required
def omdb_search(request):
    """AJAX: search OMDb for films and TV shows.

    GET /diary/edit/omdb/search/?q=...
    Returns JSON list of results or {"error": "..."}.
    """
    from toolkit.diary.omdb import search_works
    import urllib.error

    api_key = _get_omdb_api_key()
    if not api_key:
        return JsonResponse({"error": "OMDb not configured"}, status=503)

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse([], safe=False)

    try:
        results = search_works(query, api_key)
    except urllib.error.URLError as exc:
        logger.warning("OMDb search failed: %s", exc)
        return JsonResponse({"error": "OMDb request failed"}, status=502)
    except Exception as exc:
        logger.error("Unexpected OMDb error: %s", exc)
        return JsonResponse({"error": "Unexpected error"}, status=500)

    return JsonResponse(results, safe=False)


def _post_int_or_none(val):
    """Return val coerced to int, or None if blank or non-numeric."""
    if not val or not str(val).strip():
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


@write_required
@require_http_methods(["POST"])
def link_film(request, event_id):
    """AJAX: link a Film record to an Event.

    POST body fields:
      imdb_id + media_type  — look up OMDb and create/fetch Film
      title + year + ...    — manual entry (imdb_id absent or empty)

    Returns JSON with the film summary and a suggested film_information string.
    """
    from toolkit.diary.models import Film
    from toolkit.diary.omdb import fetch_film_details
    import urllib.error

    event = get_object_or_404(Event, pk=event_id)
    imdb_id_raw = request.POST.get("imdb_id", "").strip()
    media_type = request.POST.get("media_type", Film.MEDIA_TYPE_FILM)

    if imdb_id_raw:
        # OMDb-sourced path
        api_key = _get_omdb_api_key()
        if not api_key:
            return JsonResponse({"error": "OMDb not configured"}, status=503)

        try:
            details = fetch_film_details(imdb_id_raw, api_key)
        except urllib.error.URLError as exc:
            logger.warning("OMDb detail fetch failed: %s", exc)
            return JsonResponse({"error": "OMDb request failed"}, status=502)
        except Exception as exc:
            logger.error("Unexpected OMDb error: %s", exc)
            return JsonResponse({"error": "Unexpected error"}, status=500)

        film, _ = Film.objects.update_or_create(
            imdb_id=imdb_id_raw,
            defaults={k: v for k, v in details.items() if k != "imdb_id"},
        )
    else:
        # Manual entry path — update the existing manually-entered Film if present,
        # otherwise create a new one. Never update an OMDb-linked record this way.
        if event.film and not event.film.imdb_id:
            film = event.film
            film.media_type = media_type
            film.title = request.POST.get("title", "").strip()
            film.year = _post_int_or_none(request.POST.get("year"))
            film.director = request.POST.get("director", "").strip()
            film.runtime_minutes = _post_int_or_none(request.POST.get("runtime_minutes"))
            film.countries = request.POST.get("countries", "").strip()
            film.languages = request.POST.get("languages", "").strip()
            film.overview = request.POST.get("overview", "").strip()
            film.notes = request.POST.get("notes", "").strip()
            film.save()
        else:
            film = Film.objects.create(
                media_type=media_type,
                title=request.POST.get("title", "").strip(),
                year=_post_int_or_none(request.POST.get("year")),
                director=request.POST.get("director", "").strip(),
                runtime_minutes=_post_int_or_none(request.POST.get("runtime_minutes")),
                countries=request.POST.get("countries", "").strip(),
                languages=request.POST.get("languages", "").strip(),
                overview=request.POST.get("overview", "").strip(),
                notes=request.POST.get("notes", "").strip(),
            )

    event.film = film
    event.save(update_fields=["film"])

    return JsonResponse(
        {
            "success": True,
            "film": _film_json(film),
            "suggested_film_information": film.generate_film_information(),
        }
    )


@write_required
@require_POST
def unlink_film(request, event_id):
    """AJAX: remove the film link from an event."""
    event = get_object_or_404(Event, pk=event_id)
    event.film = None
    event.save(update_fields=["film"])
    return JsonResponse({"success": True})


def _film_json(film) -> dict:
    """Serialise a Film instance to a JSON-safe dict for AJAX responses."""
    return {
        "id": film.pk,
        "imdb_id": film.imdb_id,
        "media_type": film.media_type,
        "title": film.title,
        "original_title": film.original_title,
        "year": film.year,
        "director": film.director,
        "runtime_minutes": film.runtime_minutes,
        "countries": film.countries,
        "languages": film.languages,
        "overview": film.overview,
        "poster_url": film.poster_url,
        "imdb_url": f"https://www.imdb.com/title/{film.imdb_id}/" if film.imdb_id else "",
    }
