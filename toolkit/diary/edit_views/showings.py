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


def _get_oneshot_roles_for_showing(showing):
    """Return a list of {pk, name, description, current_count, signed_up_count}
    dicts for one-shot roles on this showing.

    ``current_count`` is the total number of RotaEntry slots for the role on
    this showing; ``signed_up_count`` is how many of those have a volunteer
    FK (a real sign-up). The template uses the difference to warn before the
    programmer drops volunteer sign-ups by lowering the count.
    """
    from django.db.models import Count as _Count, Q as _Q

    return list(
        Role.objects.filter(rotaentry__showing=showing, is_one_shot=True)
        .annotate(
            current_count=_Count("rotaentry"),
            signed_up_count=_Count(
                "rotaentry", filter=_Q(rotaentry__volunteer__isnull=False)
            ),
        )
        .values("pk", "name", "description", "current_count", "signed_up_count")
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
                Role.objects.filter(pk=role_pk, is_one_shot=True).update(
                    description=desc
                )
        elif name and count > 0:
            # New one-shot — find or create by name
            role, _ = Role.objects.get_or_create(
                name=name,
                defaults={
                    "is_one_shot": True,
                    "standard": False,
                    "description": desc,
                },
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
            for rb in modified_showing.room_bookings.select_related(
                "room"
            ).all():
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
                    "oneshot_roles": _get_oneshot_roles_for_showing(
                        modified_showing
                    ),
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
