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


def get_messages(request):
    message_list = [
        {"message": m.message, "tags": m.tags, "level": m.level}
        for m in messages.get_messages(request)
    ]

    return HttpResponse(
        json.dumps(message_list), content_type="application/json"
    )


@require_POST
@permission_required("diary.change_rotaentry")
def toggle_event_mark(request):
    """Set or clear the ★/☽ mark for the current user on an event. Returns JSON.

    Accepts mark_type: "star", "shadow", or "" (clear).
    One mark per (volunteer, event) — setting a new type replaces any existing one.
    """
    mark_type = request.POST.get("mark_type", "")
    event_id = request.POST.get("event_id")

    if mark_type not in (
        "",
        VolunteerEventMark.MARK_STAR,
        VolunteerEventMark.MARK_SHADOW,
    ):
        return JsonResponse({"error": "Invalid mark type"}, status=400)

    try:
        event = Event.objects.get(pk=event_id)
    except (Event.DoesNotExist, ValueError):
        return JsonResponse({"error": "Event not found"}, status=404)

    try:
        volunteer = request.user.volunteer
    except Exception:
        return JsonResponse(
            {"error": "No volunteer record for this user"}, status=403
        )

    if not mark_type:
        VolunteerEventMark.objects.filter(
            volunteer=volunteer, event=event
        ).delete()
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
