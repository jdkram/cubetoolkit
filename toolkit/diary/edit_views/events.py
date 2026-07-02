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
from django.db.models import Count, Q, Min, Max, Sum
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
    EventBudgetLine,
    VolunteerEventMark,
    get_site_config,
    sync_budget_lines_for_event,
)
import toolkit.diary.forms as diary_forms
import toolkit.diary.validators as diary_validators
import toolkit.diary.edit_prefs as edit_prefs
from toolkit.diary.poster import generate_event_placeholder
from toolkit.members.models import Qualification, VolunteerQualification
from toolkit.util.image import adjust_colour

# Shared utility method:
from toolkit.diary.daterange import get_date_range, safe_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from ._common import _film_json, _get_omdb_api_key


@write_required
@require_http_methods(["GET"])
def past_events_search(request):
    """Find a past event by name/date range, linking to its edit page.

    edit_diary_list() (diary_overview.py) redirects the calendar day/month/
    year views away from any date before today, which makes past events
    hard to *reach* via the calendar once their date has gone by -- but
    EditEventView has no date guard, so a specific event's edit page is
    already reachable once you have its URL. This view is that missing
    entry point: a simple search, not a calendar, so it isn't subject to
    the same "don't allow viewing of dates before today" redirect. Exists
    for task 9.149's post-event budget reconciliation workflow -- a
    programmer filling in actuals days or weeks after an event needs a way
    to find it again without knowing its ID.
    """
    now = timezone.now()
    q = request.GET.get("q", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    def _parse_date(value):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None

    events = Event.objects.annotate(
        latest_showing_start=Max("showings__start")
    ).filter(latest_showing_start__lte=now)
    if q:
        events = events.filter(name__icontains=q)
    parsed_from = _parse_date(date_from) if date_from else None
    if parsed_from:
        events = events.filter(latest_showing_start__date__gte=parsed_from)
    parsed_to = _parse_date(date_to) if date_to else None
    if parsed_to:
        events = events.filter(latest_showing_start__date__lte=parsed_to)
    events = events.order_by("-latest_showing_start")[:200]

    return render(
        request,
        "past_events_search.html",
        {
            "events": events,
            "q": q,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


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
                    timezone.localtime(new_showing.start).strftime(
                        "%d %b %Y, %H:%M"
                    ),
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view", kwargs={"event_id": event_id}
                )
            )

    has_film_tag = event.tags.filter(slug="film").exists()
    completeness = {
        "has_copy": bool(event.copy and event.copy.strip()),
        "has_copy_summary": bool(
            event.copy_summary and event.copy_summary.strip()
        ),
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
        messages.error(
            request, f"Can't change status of a past {noun.lower()}"
        )
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
                messages.success(
                    request,
                    f"{noun} confirmed — it's now public and on the rota.",
                )
        elif action == "unconfirm":
            showing.confirmed = False
            showing.save()
            messages.success(
                request,
                f"{noun} unconfirmed — removed from the programme and rota.",
            )
        elif action == "cancel":
            showing.cancelled = True
            showing.confirmed = False
            showing.save()
            messages.success(
                request, f"{noun} cancelled — its room bookings are freed."
            )
        elif action == "uncancel":
            showing.cancelled = False
            showing.save()
            messages.success(request, f"{noun} reinstated.")
        else:
            messages.error(request, "Unknown action.")
    return HttpResponseRedirect(
        reverse(
            "edit-event-details-view", kwargs={"event_id": showing.event_id}
        )
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
    updated = event.showings.filter(
        confirmed=False, cancelled=False, start__gt=now
    ).update(confirmed=True)
    if updated:
        messages.success(
            request,
            f"{updated} showing{'s' if updated != 1 else ''} confirmed.",
        )
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
                    timezone.localtime(new_showing.start).strftime(
                        "%d %b %Y, %H:%M"
                    ),
                ),
            )
            return HttpResponseRedirect(
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": new_event.pk},
                )
            )
    else:
        # Pre-fill the form with sensible defaults from the source event
        suggested_start = None
        suggested_room = None
        suggested_booked_by = ""
        if latest_showing:
            # Source event may be long in the past (9.131 - cloning from
            # past events) - anchor to "today + a week" too, so an old
            # source event doesn't suggest a start date that's still in
            # the past and gets rejected by validate_in_future.
            suggested_start = max(
                latest_showing.start + datetime.timedelta(weeks=1),
                timezone.now() + datetime.timedelta(weeks=1),
            )
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
                reverse(
                    "edit-event-details-view", kwargs={"event_id": event.pk}
                )
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
            template = EventTemplate.objects.filter(
                name="Building Open"
            ).first()

            note = d["note"].strip()
            event_name = f"Building open — {d['date'].strftime('%-d %b')}"

            new_event = Event(
                name=event_name,
                private=True,
                **({"template": template} if template else {}),
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
                reverse(
                    "edit-event-details-view",
                    kwargs={"event_id": new_event.pk},
                )
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
                {"name": r.role.name, "count": r.count}
                for r in t.role_slots.all()
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
                aware_dt = timezone.make_aware(
                    datetime.datetime.combine(d, start_time)
                )
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
                noun = (
                    cfg.occurrence_noun
                    if n_dates == 1
                    else cfg.occurrence_noun_plural
                )
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
        default_date = django.utils.timezone.now().date() + datetime.timedelta(
            1
        )
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
            initial_date = datetime.date(
                day=date[0], month=date[1], year=date[2]
            )
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
                initial_template = EventTemplate.objects.get(
                    pk=int(template_pk)
                )
            except (ValueError, EventTemplate.DoesNotExist):
                pass

        # Create form, render template:
        form = diary_forms.NewEventForm(
            initial={
                "dates": initial_date.isoformat(),
                "start_time": initial_time,
                "duration": duration,
                "booked_by": request.user.get_full_name()
                or request.user.username,
                "event_template": initial_template,
            }
        )
        context = {
            "form": form,
            "template_data": _template_data(),
        }
        return render(request, "form_new_event_and_showing.html", context)


def _create_room_booking(showing, room, event):
    """Create a single RoomBooking for showing in room, deriving end from event.duration."""
    end = None
    if event.duration is not None:
        end = showing.start + datetime.timedelta(
            hours=event.duration.hour, minutes=event.duration.minute
        )
    RoomBooking.objects.create(
        showing=showing, room=room, start=showing.start, end=end
    )


def _build_cert_lookup_url(url_template: str, film) -> str:
    """Substitute {title} and {year} into the certificate lookup URL template."""
    if not url_template or not film:
        return ""
    from urllib.parse import quote

    return url_template.replace("{title}", quote(film.title or "")).replace(
        "{year}", quote(str(film.year or ""))
    )


def _budget_grid_context(event, budget_formset):
    """Group a budget formset's forms by category, and compute totals.

    Grouping is done here (not via the {% regroup %} template tag) so
    category order doesn't depend on the model's Meta.ordering (which
    sorts by direction/order/pk, not category) -- rows are grouped by
    first appearance of their category, which matches template order
    since sync_budget_lines_for_event() assigns `order` category-block by
    category-block. Totals are always a fresh read-time aggregate over the
    DB, never a stored value, so there's nothing to reconcile against
    client-side JS sums -- recomputing on every render *is* the
    "server-side re-check" the spec asks for.
    """
    categories = OrderedDict()
    for bform in budget_formset.forms:
        categories.setdefault(bform.instance.category, []).append(bform)

    totals = event.budget_lines.aggregate(
        estimate_outgoing=Sum(
            "estimate_gbp",
            filter=Q(direction=EventBudgetLine.DIRECTION_OUTGOING),
        ),
        estimate_incoming=Sum(
            "estimate_gbp",
            filter=Q(direction=EventBudgetLine.DIRECTION_INCOME),
        ),
        actual_outgoing=Sum(
            "actual_gbp",
            filter=Q(direction=EventBudgetLine.DIRECTION_OUTGOING),
        ),
        actual_incoming=Sum(
            "actual_gbp",
            filter=Q(direction=EventBudgetLine.DIRECTION_INCOME),
        ),
    )
    return {
        "budget_categories": [
            {"name": name, "forms": forms} for name, forms in categories.items()
        ],
        "budget_totals": totals,
    }


class EditEventView(PermissionRequiredMixin, View):
    """Handle the "edit event" form."""

    # Quite complex, so a class based view

    permission_required = "toolkit.write"

    def _save(
        self, event, media_item, form, media_form, generated_media_id=None
    ):
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

        cfg = get_site_config()
        budget_formset = None
        if cfg.budget_lines_enabled:
            # Bound to whatever budget_lines existed as of the GET that
            # rendered this form -- deliberately NOT re-running
            # sync_budget_lines_for_event() here first: the inline formset
            # binds POST data to existing rows *positionally* (by queryset
            # index), so inserting a new row via sync between GET and POST
            # would shift every later row's index and silently misassign
            # submitted values to the wrong row. Sync only runs on GET.
            budget_formset = diary_forms.EventBudgetLineInlineFormSet(
                request.POST, instance=event
            )

        # Validate
        if (
            form.is_valid()
            and media_form.is_valid()
            and (budget_formset is None or budget_formset.is_valid())
        ):
            event._saved_by = request.user
            generated_media_id = request.POST.get("generated_media_id")
            self._save(event, media_item, form, media_form, generated_media_id)
            if budget_formset is not None:
                budget_formset.save()
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
            "film_cert_lookup_url": _build_cert_lookup_url(
                cfg.certificate_lookup_url, event.film
            ),
            "structured_cost_terms_enabled": cfg.structured_cost_terms_enabled,
            "has_film_tag": event.tags.filter(slug="film").exists(),
            "event_film_json": (
                json.dumps(_film_json(event.film)) if event.film else "null"
            ),
            "budget_lines_enabled": cfg.budget_lines_enabled,
        }
        if budget_formset is not None:
            context["budget_formset"] = budget_formset
            context.update(_budget_grid_context(event, budget_formset))
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

        budget_formset = None
        if cfg.budget_lines_enabled:
            sync_budget_lines_for_event(event)
            budget_formset = diary_forms.EventBudgetLineInlineFormSet(
                instance=event
            )

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
            "tag_descriptions_json": mark_safe(safe_json(tag_descriptions)),
            "top_5_tag_pks_json": mark_safe(json.dumps(top_5_tag_pks)),
            "thumbnail_crop_width": cfg.thumbnail_crop_width,
            "thumbnail_crop_height": cfg.thumbnail_crop_height,
            "programme_accent_colour": cfg.programme_accent_colour,
            "ticket_link_guidance_html": cfg.ticket_link_guidance_html,
            "film_programming_guide_url": cfg.film_programming_guide_url,
            "omdb_configured": bool(_get_omdb_api_key()),
            "certificate_lookup_url": cfg.certificate_lookup_url,
            "film_cert_lookup_url": _build_cert_lookup_url(
                cfg.certificate_lookup_url, event.film
            ),
            "structured_cost_terms_enabled": cfg.structured_cost_terms_enabled,
            "suggested_film_information": (
                event.film.generate_film_information() if event.film else ""
            ),
            "has_film_tag": event.tags.filter(slug="film").exists(),
            "event_film_json": (
                json.dumps(_film_json(event.film)) if event.film else "null"
            ),
            "budget_lines_enabled": cfg.budget_lines_enabled,
        }
        if budget_formset is not None:
            context["budget_formset"] = budget_formset
            context.update(_budget_grid_context(event, budget_formset))

        return render(request, "form_event.html", context)
