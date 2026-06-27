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


def _get_omdb_api_key() -> str:
    """Return the active OMDb API key: DB setting takes precedence over env var."""
    from toolkit.diary.models import get_site_config

    db_key = get_site_config().omdb_api_key.strip()
    return db_key or settings.OMDB_API_KEY


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
        "imdb_url": (
            f"https://www.imdb.com/title/{film.imdb_id}/"
            if film.imdb_id
            else ""
        ),
    }
