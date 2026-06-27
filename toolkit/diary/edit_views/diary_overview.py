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


def _return_to_editindex(request):
    return HttpResponseRedirect(reverse("default-edit"))


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
        edit_prefs.set_preference(
            request.session,
            "daysahead",
            query_days_ahead,
            volunteer=_volunteer,
        )
        default_days_ahead = query_days_ahead
    else:
        default_days_ahead = int(
            edit_prefs.get_preference(
                request.session, "daysahead", volunteer=_volunteer
            )
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
    idea_startdate = datetime.date(
        day=1, month=startdate.month, year=startdate.year
    )
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
    dateless_events = Event.objects.filter(
        target_month__range=[idea_startdate, enddatetime],
        showings__isnull=True,
    ).order_by("target_month", "name")
    # Build lookup: (year, month) -> the key used in the ideas dict for that month.
    # The ideas dict uses startdate as the key for the first month (which may not
    # be the 1st), and the literal 1st-of-month date for all subsequent months.
    month_to_ideas_key = {(k.year, k.month): k for k in ideas}
    dateless_by_month = {}
    for ev in dateless_events:
        key = month_to_ideas_key.get(
            (ev.target_month.year, ev.target_month.month)
        )
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
                showing.visible_room_bookings
                if settings.MULTIROOM_ENABLED
                else []
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
    context["edit_prefs"] = edit_prefs.get_preferences(
        request.session, volunteer=_volunteer
    )
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
        if (
            settings.MULTIROOM_ENABLED
            and primary_room
            and not primary_room.is_primary
        ):
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
                    rb_end = (
                        timezone.localtime(rb.end).isoformat()
                        if rb.end
                        else showing_end
                    )
                    results.append(
                        {
                            **base,
                            "id": f"rb-{rb.pk}",
                            "start": rb_start.isoformat(),
                            "end": rb_end,
                            "hour": rb_start.hour,
                            "resourceIds": [rb.room_id],
                        }
                    )
            else:
                # No room bookings: place in the virtual "unroomed" resource lane.
                results.append(
                    {
                        **base,
                        "id": showing.pk,
                        "start": local_start.isoformat(),
                        "end": timezone.localtime(
                            showing.end_time
                        ).isoformat(),
                        "hour": hour,
                        "color": settings.CALENDAR_DEFAULT_COLOUR,
                        "resourceIds": ["unroomed"],
                    }
                )
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
                    "text_colour": (
                        "#111111" if _is_light_colour(r.colour) else "#ffffff"
                    ),
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
    edit_prefs.set_preferences(
        request.session, request.GET, volunteer=volunteer
    )
    prefs = edit_prefs.get_preferences(request.session, volunteer=volunteer)
    return HttpResponse(json.dumps(prefs), content_type="application/json")


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
