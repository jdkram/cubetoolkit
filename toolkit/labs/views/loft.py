import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from toolkit.toolkit_auth.decorators import (
    feature_required,
    write_required,
    write_required_strict,
)
from django.db import models
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Exists, OuterRef

from ..models import (
    AreaPhoto,
    Bulletin,
    BulletinRead,
    Collective,
    ConsumableItem,
    ExchangeItem,
    FoundItem,
    NeedFlag,
    ProcurementPledge,
    Supplier,
    SupplierRecord,
    RoomNote,
    DonationItem,
    Job,
    LoftItem,
    LoftItemPhoto,
)
from toolkit.diary.models import SiteConfiguration, get_site_config
from .. import forms as lab_forms

_LOFT_ZONES = [
    # (zone_id, display_name, section_key)
    ("loft-raised-west", "Raised West", "raised"),
    ("loft-raised-mid", "Raised Mid", "raised"),
    ("loft-raised-east", "Raised East", "raised"),
    ("loft-low-west", "Low West", "low"),
    ("loft-low-mid", "Low Mid", "low"),
    ("loft-low-east", "Low East", "low"),
]

_LOFT_ZONE_IDS = {z[0] for z in _LOFT_ZONES}

_LOFT_ZONE_SECTIONS = [
    {"key": "raised", "label": "Raised section (ladder access)"},
    {"key": "low", "label": "Low section (direct access)"},
]


def _serialize_loft_items():
    items_qs = (
        LoftItem.objects.filter(zone_id__in=_LOFT_ZONE_IDS)
        .prefetch_related("photos")
        .select_related("added_by")
    )
    result = {z: [] for z in _LOFT_ZONE_IDS}
    for item in items_qs:
        result[item.zone_id].append(
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "added_by": (
                    item.added_by.get_full_name() or item.added_by.username
                    if item.added_by
                    else None
                ),
                "added_at": item.added_at.isoformat(),
                "photos": [
                    {"id": p.id, "url": p.image.url, "caption": p.caption}
                    for p in item.photos.all()
                ],
            }
        )
    return result


# ── Loft inventory ────────────────────────────────────────────────────────────


@login_required
@require_POST
def loft_item_create(request, zone_id):
    if zone_id not in _LOFT_ZONE_IDS:
        return JsonResponse({"error": "Unknown zone"}, status=404)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)
    item = LoftItem.objects.create(
        zone_id=zone_id,
        name=name,
        description=data.get("description", "").strip(),
        added_by=request.user,
    )
    return JsonResponse(
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "added_by": item.added_by.get_full_name()
            or item.added_by.username,
            "added_at": item.added_at.isoformat(),
            "photos": [],
        },
        status=201,
    )


@login_required
@require_http_methods(["POST", "DELETE"])
def loft_item(request, item_id):
    item = get_object_or_404(LoftItem, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"deleted": True})
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    item.name = data.get("name", item.name).strip() or item.name
    item.description = data.get("description", item.description).strip()
    item.save()
    return JsonResponse(
        {"id": item.id, "name": item.name, "description": item.description}
    )


@login_required
@require_POST
def loft_item_photo_upload(request, item_id):
    item = get_object_or_404(LoftItem, pk=item_id)
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file"}, status=400)
    form = lab_forms.LoftItemPhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(errs)}"
            for field, errs in form.errors.items()
        )
        return JsonResponse({"error": errors}, status=400)
    photo = form.save(commit=False)
    photo.item = item
    photo.uploaded_by = request.user
    photo.save()
    return JsonResponse(
        {"id": photo.id, "url": photo.image.url, "caption": photo.caption},
        status=201,
    )


@login_required
@require_POST
def loft_photo_delete(request, photo_id):
    photo = get_object_or_404(LoftItemPhoto, pk=photo_id)
    photo.image.delete(save=False)
    photo.delete()
    return JsonResponse({"deleted": True})
