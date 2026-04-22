import json
import datetime
import logging
import csv

from collections import OrderedDict

from django.http import (
    HttpResponse,
    Http404,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.conf import settings
from django.forms.models import modelformset_factory
from django.contrib import messages
from django.views.generic import View
import django.template
import django.db
from django.db.models import Q
import django.utils.timezone as timezone
from django.contrib.auth.decorators import permission_required, user_passes_test
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.html import escape

from toolkit.diary.models import (
    Showing,
    Event,
    EventLink,
    DiaryIdea,
    MediaItem,
    EventTemplate,
    EventTag,
    Role,
    RotaEntry,
    PrintedProgramme,
    Room,
    get_site_config,
)
import toolkit.diary.forms as diary_forms
import toolkit.diary.edit_prefs as edit_prefs
from toolkit.util.image import adjust_colour

# Shared utility method:
from toolkit.diary.daterange import get_date_range

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _return_to_editindex(request):
    return HttpResponseRedirect(reverse("default-edit"))


@permission_required("toolkit.write")
def cancel_edit(request):
    # Again, a dirty hack, used with the above method, used for the "Cancel"
    # link in forms, to either close the popup or just redirect to the edit
    # page
    return _return_to_editindex(request)


@permission_required("toolkit.read")
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

    if query_days_ahead:
        edit_prefs.set_preference(request.session, "daysahead", query_days_ahead)
        default_days_ahead = query_days_ahead
    else:
        default_days_ahead = int(
            edit_prefs.get_preference(request.session, "daysahead")
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
    # Group each day's showings by start time so the template can render
    # same-time events in different rooms on a single row (multiroom mode).
    dates_by_time: OrderedDict = OrderedDict()
    for day, day_showings in dates.items():
        time_groups: OrderedDict = OrderedDict()
        for showing in day_showings:
            if showing.start not in time_groups:
                time_groups[showing.start] = []
            time_groups[showing.start].append(showing)
        dates_by_time[day] = time_groups
    context["dates"] = dates_by_time
    # Page title:
    context["event_list_name"] = "Diary for {} to {}".format(
        startdatetime.strftime("%d-%m-%Y"), enddatetime.strftime("%d-%m-%Y")
    )
    context["start"] = startdatetime
    context["end"] = enddatetime
    context["edit_prefs"] = edit_prefs.get_preferences(request.session)
    context["rooms"] = list(Room.objects.all())
    context["multiroom_enabled"] = settings.MULTIROOM_ENABLED
    return render(request, "edit_event_index.html", context)


def _adjust_colour_historic(colour):
    return adjust_colour(
        colour,
        settings.CALENDAR_HISTORIC_LIGHTER,
        settings.CALENDAR_HISTORIC_SHADIER,
    )


def _is_light_colour(hex_colour):
    """Return True if the hex colour is perceptually light (needs dark text)."""
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return False
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5


@permission_required("toolkit.read")
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
        .prefetch_related("event__tags")
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

        # Initially set colour to "confirmed" colour for the room:
        if settings.MULTIROOM_ENABLED and showing.room:
            colour = showing.room.colour
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
        if settings.MULTIROOM_ENABLED and showing.room and not showing.room.is_primary:
            styles.append("s_auxiliary_room")

        # Extract hour for time-of-day filtering (0-23)
        local_start = timezone.localtime(showing.start)
        hour = local_start.hour

        # Build tag list for filtering
        tag_slugs = [tag.slug for tag in showing.event.tags.all()]

        showing_data = {
            "id": showing.pk,
            "title": showing.event.name,
            "start": local_start.isoformat(),
            "end": timezone.localtime(showing.end_time).isoformat(),
            "url": url,
            "className": styles,
            "color": colour,
            "hour": hour,
            "tags": tag_slugs,
        }
        if _is_light_colour(colour):
            showing_data["textColor"] = "#111111"

        if settings.MULTIROOM_ENABLED:
            showing_data["resourceId"] = showing.room_id

        results.append(showing_data)

    return HttpResponse(
        json.dumps(results), content_type="application/json; charset=utf-8"
    )


@permission_required("toolkit.read")
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
        "rooms_and_colours": (Room.objects.all() if settings.MULTIROOM_ENABLED else []),
        "all_tags": EventTag.objects.all(),
    }

    return render(request, "edit_event_calendar_index.html", context)


@permission_required("toolkit.read")
def set_edit_preferences(request):
    # Store user preferences as specified in the request's GET variables,
    # and return a JSON object containing all current user preferences

    # Store updated prefs
    edit_prefs.set_preferences(request.session, request.GET)
    # Retrieve and return prefs:
    prefs = edit_prefs.get_preferences(request.session)
    return HttpResponse(json.dumps(prefs), content_type="application/json")


@permission_required("toolkit.write")
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
                "Added showing on {}".format(
                    timezone.localtime(new_showing.start).strftime("%d %b %Y, %H:%M")
                ),
            )
            return HttpResponseRedirect(
                reverse("edit-event-details-view", kwargs={"event_id": event_id})
            )

    completeness = {
        "has_copy": bool(event.copy and event.copy.strip()),
        "has_copy_summary": bool(event.copy_summary and event.copy_summary.strip()),
        "has_image": event.media.exists(),
        "terms_ok": not event.terms_required() or event.terms_long_enough(),
        "terms_required": event.terms_required(),
        "has_future_showing": bool(future_showings),
    }

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
        },
    )


@permission_required("toolkit.write")
@require_POST
def update_showing_status(request, showing_id):
    showing = get_object_or_404(Showing, pk=showing_id)
    if showing.in_past():
        messages.error(request, "Can't change status of a past showing")
    else:
        action = request.POST.get("action", "")
        if action == "confirm":
            if showing.event.terms_required() and not showing.event.terms_long_enough():
                messages.error(
                    request,
                    "Add terms to the event before confirming — "
                    "the event page needs them.",
                )
            else:
                showing.confirmed = True
                showing.save()
                messages.success(request, "Showing confirmed.")
        elif action == "unconfirm":
            showing.confirmed = False
            showing.save()
            messages.success(request, "Showing unconfirmed.")
        elif action == "cancel":
            showing.cancelled = True
            showing.confirmed = False
            showing.save()
            messages.success(request, "Showing cancelled.")
        elif action == "uncancel":
            showing.cancelled = False
            showing.save()
            messages.success(request, "Showing reinstated.")
        else:
            messages.error(request, "Unknown action.")
    return HttpResponseRedirect(
        reverse("edit-event-details-view", kwargs={"event_id": showing.event_id})
    )


@permission_required("toolkit.write")
@require_http_methods(["GET", "POST"])
def clone_event(request, event_id):
    """Clone an existing event as a brand-new event.

    Copies all text/config fields (copy, copy_summary, terms, notes,
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
                notes=source_event.notes,
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
            if settings.MULTIROOM_ENABLED:
                new_showing.room = form.cleaned_data["room"]
            new_showing.save()
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
            if settings.MULTIROOM_ENABLED:
                suggested_room = latest_showing.room_id
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


@permission_required("toolkit.write")
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
        },
    )


@permission_required("toolkit.write")
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
            new_event = Event(
                name=form.cleaned_data["event_name"],
                template=form.cleaned_data["event_template"],
                duration=form.cleaned_data["duration"],
                outside_hire=form.cleaned_data["outside_hire"],
                private=form.cleaned_data["private"],
            )
            # Set event tags to those from its template:
            new_event.save()
            new_event.reset_tags_to_default()
            # create number_of_bookings showings, each offset by one more from
            # the date/time given in start parameter, and each with rota roles
            # from the template
            start = form.cleaned_data["start"]
            for day_count in range(0, form.cleaned_data["number_of_bookings"]):
                day_offset = datetime.timedelta(days=day_count)
                new_showing = Showing(
                    event=new_event,
                    start=(start + day_offset),
                    discounted=form.cleaned_data["discounted"],
                    # confirmed=form.cleaned_data['confirmed'],
                    booked_by=form.cleaned_data["booked_by"],
                )
                if settings.MULTIROOM_ENABLED:
                    new_showing.room = form.cleaned_data["room"]
                new_showing.save()
                # Set showing roles to those from its template:
                new_showing.reset_rota_to_default()

            messages.add_message(
                request,
                messages.SUCCESS,
                "Added event '{}' with booking on {}".format(
                    new_event.name,
                    new_showing.start.strftime("%d/%m/%y at %H:%M"),
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": new_event.pk},
                )
            )
        else:
            # If form was not valid, re-render the form (which will highlight
            # errors)
            context = {"form": form}
            return render(request, "form_new_event_and_showing.html", context)

    elif request.method == "GET":
        # GET: Show form blank, with date filled in from GET date and start
        # parameters:
        # Marshal date and time out of the GET request:
        default_date = django.utils.timezone.now().date() + datetime.timedelta(1)
        date = request.GET.get("date", default_date.strftime("%d-%m-%Y"))
        date = date.split("-")

        # Default start time is 8pm (shouldn't this be a setting?)
        time = request.GET.get("time", "20:00")
        time = time.split(":")
        # Default duration is one hour:
        duration = request.GET.get("duration", "3600")

        room = request.GET.get("room", None)

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
            event_start = datetime.datetime(
                hour=time[0],
                minute=time[1],
                day=date[0],
                month=date[1],
                year=date[2],
                tzinfo=timezone.get_current_timezone(),
            )
            if settings.MULTIROOM_ENABLED and room:
                room = Room.objects.get(id=room)
        except (ValueError, TypeError, Room.DoesNotExist):
            return HttpResponse(
                "Illegal time, date, duration or room",
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
                "start": event_start,
                "duration": duration,
                "room": room,
                "booked_by": request.user.get_full_name() or request.user.username,
                "event_template": initial_template,
            }
        )
        context = {"form": form}
        return render(request, "form_new_event_and_showing.html", context)


@permission_required("toolkit.write")
@require_http_methods(["GET", "POST"])
def edit_showing(request, showing_id=None):
    showing = get_object_or_404(Showing, pk=showing_id)

    RotaForm = diary_forms.rota_form_factory(showing)

    if request.method == "POST":
        form = diary_forms.ShowingForm(request.POST, instance=showing)
        rota_form = RotaForm(request.POST)
        rota_notes_form = diary_forms.ShowingRotaNotesForm(
            request.POST, instance=showing
        )

        if form.is_valid() and rota_form.is_valid() and rota_notes_form.is_valid():
            # The rota form is separate; first save the updated showing
            modified_showing = form.save()
            # Then update the rota with the returned data:
            rota = rota_form.get_rota()
            modified_showing.update_rota(rota)
            # Save rota notes (a second save on the same instance is fine)
            rota_notes_form.save()

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

    context = {
        "showing": showing,
        "form": form,
        "rota_form": rota_form,
        "rota_notes_form": rota_notes_form,
        "max_role_assignment_count": get_site_config().max_count_per_role,
    }

    return render(request, "form_showing.html", context)


class EditEventView(PermissionRequiredMixin, View):
    """Handle the "edit event" form."""

    # Quite complex, so a class based view

    permission_required = "toolkit.write"

    def _save(self, event, media_item, form, media_form):
        # Some factored out code: method is passed valid event and media form,
        # and commits the data.

        # When the form was created the copy was converted to HTML, so when
        # saved always clear the "legacy" flag:
        event.legacy_copy = False
        # Then save the main form:
        form.save()
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
            self._save(event, media_item, form, media_form)
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
        context = {
            "event": event,
            "event_form": form,
            "media_form": media_form,
            "programme_copy_summary_max_chars": get_site_config().programme_copy_summary_max_chars,
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

        context = {
            "event": event,
            "event_form": form,
            "media_form": media_form,
            "programme_copy_summary_max_chars": get_site_config().programme_copy_summary_max_chars,
        }

        return render(request, "form_event.html", context)


@permission_required("toolkit.write")
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


@permission_required("toolkit.write")
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


@permission_required("toolkit.read")
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


@permission_required("toolkit.read")
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
    showings = (
        Showing.objects.not_cancelled()
        .confirmed()
        .start_in_range(start_date, end_date)
        .order_by("start")
        #              following prefetch is for the rota view
        .prefetch_related("rotaentry_set__role")
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


@permission_required("toolkit.write")
def edit_event_templates(request):
    """List all event templates with links to per-template edit pages."""
    templates = EventTemplate.objects.prefetch_related("role_slots__role", "tags").all()
    return render(request, "edit_event_templates.html", {"templates": templates})


@permission_required("toolkit.write")
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

        if form.is_valid() and roles_formset.is_valid():
            saved = form.save()
            roles_formset.instance = saved
            roles_formset.save()
            logger.info("Event template '%s' saved", saved.name)
            messages.add_message(
                request, messages.SUCCESS, f"Saved template '{saved.name}'"
            )
            return HttpResponseRedirect(reverse("edit_event_templates"))
    else:
        form = diary_forms.EventTemplateForm(instance=event_template)
        roles_formset = diary_forms.EventTemplateRoleFormSet(instance=event_template)

    context = {
        "form": form,
        "roles_formset": roles_formset,
        "event_template": event_template,
    }
    return render(request, "edit_event_template_detail.html", context)


@permission_required("toolkit.write")
def edit_event_tags(request):
    event_tag_formset = modelformset_factory(
        EventTag, fields=("name", "promoted", "sort_order"), can_delete=True
    )

    if request.method == "POST":
        formset = event_tag_formset(request.POST)
        if formset.is_valid():
            logger.info("Event tags updated")
            formset.save()
            # Reset formset, so get another blank one at the
            # end, deleted ones disappear, etc.
            formset = event_tag_formset()
            messages.add_message(request, messages.SUCCESS, "Event tags updated")
    else:
        formset = event_tag_formset()
    context = {"formset": formset}
    return render(request, "edit_event_tags.html", context)


@user_passes_test(lambda u: u.is_superuser)
def edit_roles(request):
    # This is pretty slow,but it's not a commonly used bit of the UI...
    # (To be precise, save involves >120 queries. This is because I've been
    # lazy and used the formset save method)

    RoleFormset = modelformset_factory(
        Role,
        diary_forms.RoleForm,
        fields=(
            "name",
            "standard",
            "description",
            "beginner_friendly",
            "not_wheelchair_accessible",
            "keyholder_only",
        ),
        can_delete=True,
    )

    if request.method == "POST":
        formset = RoleFormset(request.POST)
        if formset.is_valid():
            logger.info("Roles updated")
            formset.save()
            # Reset formset, so get another blank one at the
            # end, deleted ones disappear, etc.
            formset = RoleFormset()
            messages.add_message(request, messages.SUCCESS, "Roles updated")
    else:
        formset = RoleFormset()

    return render(request, "form_edit_roles.html", {"formset": formset})


@permission_required("toolkit.write")
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


@permission_required("diary.change_rotaentry")
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
        .select_related()
    )
    showings_vacant_roles = OrderedDict(
        (
            showing,
            showing.rotaentry_set.filter(Q(name="") | Q(name__isnull=True)),
        )
        for showing in showings
    )

    # Surprisingly round-about way to get tomorrow's date:
    now_local = django.utils.timezone.localtime(django.utils.timezone.now())

    context = {
        "days_ahead": days_ahead,
        "now": now_local,
        "now_plus_1d": now_local + datetime.timedelta(days=1),
        "rota_edit_url": request.build_absolute_uri(reverse("rota-edit")),
        "showings_vacant_roles": showings_vacant_roles,
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
            year, month, day, query_days_ahead, default_days_ahead=30
        )

        if not request.user.is_superuser:
            # Don't allow data from before yesterday to be displayed:
            # TODO datepicker is still nobbled to yesterday
            if start_date < yesterday_local_date:
                start_date = yesterday_local_date

        end_date = start_date + datetime.timedelta(days=days_ahead)
        showings = (
            Showing.objects.not_cancelled()
            .confirmed()
            .start_in_range(start_date, end_date)
            .order_by("start")
            #              force sane number of queries:
            .prefetch_related("rotaentry_set__role", "event__tags")
            .select_related()
        )

        # Used by per-showing rota notes click to edit control:
        url_with_id = reverse("edit-showing-rota-notes", kwargs={"showing_id": 999})
        showing_notes_url_prefix = url_with_id[: url_with_id.find("999")]

        context = {
            "start_date": start_date,
            "end_date": end_date,
            "days_ahead": days_ahead,
            "showings": showings,
            "edit_showing_notes_url_prefix": showing_notes_url_prefix,
            "rota_clear_email_prompt_enabled": get_site_config().rota_clear_email_prompt_enabled,
            "rota_show_tags": get_site_config().rota_show_tags,
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

        rota_entry.name = name
        rota_entry.save()

        response = escape(name)

        # Returned text is displayed as the rota entry:
        return HttpResponse(response, content_type="text/plain")


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


@permission_required("toolkit.write")
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
                "show_archive_images",
                "images_start_date",
            ],
        ),
        (
            "Programme limits",
            [
                "max_count_per_role",
                "programme_copy_summary_max_chars",
                "programme_event_terms_min_words",
                "programme_media_max_size_mb",
            ],
        ),
        (
            "Mailout",
            ["mailout_details_days_ahead", "mailout_listings_days_ahead"],
        ),
        (
            "Membership",
            ["membership_length_days", "default_training_expiry_months"],
        ),
        (
            "Guidance URLs",
            ["image_copyright_guidance_url", "alt_text_guidance_url"],
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

    return render(
        request,
        "edit_site_configuration.html",
        {"form": form, "grouped_fields": grouped_fields},
    )
