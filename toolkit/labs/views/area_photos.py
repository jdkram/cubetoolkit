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

# ── Area photos (one per room / loft zone) ────────────────────────────────────


@login_required
@require_POST
def area_photo_upload(request, area_id):
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file"}, status=400)
    form = lab_forms.AreaPhotoForm(request.POST, request.FILES)
    if not form.is_valid():
        errors = "; ".join(
            f"{field}: {', '.join(errs)}"
            for field, errs in form.errors.items()
        )
        return JsonResponse({"error": errors}, status=400)
    try:
        existing = AreaPhoto.objects.get(area_id=area_id)
        existing.image.delete(save=False)
        existing.delete()
    except AreaPhoto.DoesNotExist:
        pass
    photo = form.save(commit=False)
    photo.area_id = area_id
    photo.uploaded_by = request.user
    photo.save()
    return JsonResponse(
        {"url": photo.image.url, "uploaded_at": photo.uploaded_at.isoformat()},
        status=201,
    )


@login_required
@require_POST
def area_photo_delete(request, area_id):
    photo = get_object_or_404(AreaPhoto, area_id=area_id)
    photo.image.delete(save=False)
    photo.delete()
    return JsonResponse({"deleted": True})
