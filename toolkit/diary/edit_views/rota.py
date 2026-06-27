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
            list(
                showing.rotaentry_set.filter(Q(name="") | Q(name__isnull=True))
            ),
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
        now_local = django.utils.timezone.localtime(
            django.utils.timezone.now()
        )
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
        url_with_id = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": 999}
        )
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
                if (
                    entry.volunteer_id
                    and entry.volunteer.member.personal_pronouns
                ):
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
            "rota_vols_email": site_config.vols_email
            or settings.VENUE.get("vols_email", ""),
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
                if (
                    role
                    and role.required_qualification
                    and role.qualification_gate != Role.GATE_OFF
                ):
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

        response = HttpResponse(
            escape(rota_entry.name), content_type="text/plain"
        )
        if qualification_advisory:
            response["X-Qualification-Advisory"] = qualification_advisory
        return response


@permission_required("diary.change_rotaentry")
@require_POST
def edit_showing_rota_notes(request, showing_id):
    showing = get_object_or_404(Showing, pk=showing_id)
    form = diary_forms.ShowingRotaNotesForm(request.POST, instance=showing)

    if showing.in_past():
        return HttpResponse(
            "Can't change rota for showings in the past", status=403
        )
    elif form.is_valid():
        form.save()
    else:
        logger.error("Rota notes edit form not valid!")
        return HttpResponse(
            "Unknown error", status=500, content_type="text/plain"
        )

    return HttpResponse(showing.rota_notes, content_type="text/plain")


# Doesn't need permission check, as will only return messages for the current
# user:
