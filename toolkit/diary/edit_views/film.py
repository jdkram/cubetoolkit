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

from ._common import _film_json, _get_omdb_api_key


@write_required
def omdb_search(request):
    """AJAX: search OMDb for films and TV shows.

    GET /diary/edit/omdb/search/?q=...
    Returns JSON list of results or {"error": "..."}.
    """
    from toolkit.diary.omdb import OmdbAuthError, OmdbRateLimitError, search_works
    import urllib.error

    api_key = _get_omdb_api_key()
    if not api_key:
        return JsonResponse({"error": "OMDb not configured"}, status=503)

    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse([], safe=False)

    try:
        results = search_works(query, api_key)
    except OmdbRateLimitError as exc:
        logger.warning("OMDb search hit daily request limit: %s", exc)
        return JsonResponse(
            {
                "error": (
                    "OMDb's daily search limit has been reached. Film search "
                    "will work again once it resets (midnight UTC) — for now, "
                    "you can enter the details manually."
                )
            },
            status=503,
        )
    except OmdbAuthError as exc:
        logger.error("OMDb rejected the configured API key: %s", exc)
        return JsonResponse(
            {
                "error": (
                    "OMDb rejected the configured API key. A Panopticon needs "
                    "to fix this in Site Settings → External APIs."
                )
            },
            status=503,
        )
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
    from toolkit.diary.omdb import OmdbAuthError, OmdbRateLimitError, fetch_film_details
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
        except OmdbRateLimitError as exc:
            logger.warning("OMDb link fetch hit daily request limit: %s", exc)
            return JsonResponse(
                {
                    "error": (
                        "OMDb's daily request limit has been reached, so this "
                        "film's details can't be fetched right now. Try again "
                        "tomorrow, or use “Enter manually instead” for now."
                    )
                },
                status=503,
            )
        except OmdbAuthError as exc:
            logger.error("OMDb rejected the configured API key: %s", exc)
            return JsonResponse(
                {
                    "error": (
                        "OMDb rejected the configured API key. A Panopticon "
                        "needs to fix this in Site Settings → External APIs."
                    )
                },
                status=503,
            )
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
            film.runtime_minutes = _post_int_or_none(
                request.POST.get("runtime_minutes")
            )
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
                runtime_minutes=_post_int_or_none(
                    request.POST.get("runtime_minutes")
                ),
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
