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

# ── Lost & found ──────────────────────────────────────────────────────────────


@login_required
def found_item_log(request):
    initial = {}
    name = request.user.get_full_name() or request.user.username
    if name:
        initial["logged_by"] = name

    if request.method == "POST":
        form = lab_forms.FoundItemLogForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(
                request,
                f"Item logged as {item.label_id}. Write '{item.label_id}' on a sticky and attach it to the item.",
            )
            return redirect("labs-found-item-log")
    else:
        form = lab_forms.FoundItemLogForm(initial=initial)

    return render(request, "labs/found_item_log.html", {"form": form})


@login_required
def found_item_list(request):
    tab = request.GET.get("tab", "unclaimed")
    if tab not in ("unclaimed", "claimed", "disposed"):
        tab = "unclaimed"

    items = FoundItem.objects.filter(status=tab)

    return render(
        request,
        "labs/found_items.html",
        {
            "items": items,
            "tab": tab,
            "STATUS_UNCLAIMED": FoundItem.STATUS_UNCLAIMED,
            "STATUS_CLAIMED": FoundItem.STATUS_CLAIMED,
            "STATUS_DISPOSED": FoundItem.STATUS_DISPOSED,
        },
    )


@login_required
def found_item_detail(request, item_id):
    item = get_object_or_404(FoundItem, pk=item_id)
    claim_form = lab_forms.FoundItemClaimForm()
    dispose_form = lab_forms.FoundItemDisposeForm()

    return render(
        request,
        "labs/found_item.html",
        {
            "item": item,
            "claim_form": claim_form,
            "dispose_form": dispose_form,
        },
    )


@login_required
@require_POST
def found_item_claim(request, item_id):
    item = get_object_or_404(
        FoundItem, pk=item_id, status=FoundItem.STATUS_UNCLAIMED
    )
    form = lab_forms.FoundItemClaimForm(request.POST)
    if form.is_valid():
        item.status = FoundItem.STATUS_CLAIMED
        item.claimed_by = form.cleaned_data["claimed_by"]
        item.claimed_on = datetime.date.today()
        item.save()
        messages.success(
            request, f"{item.label_id} marked as claimed by {item.claimed_by}."
        )
    return redirect("labs-found-item", item_id=item.pk)


@login_required
@require_POST
def found_item_dispose(request, item_id):
    item = get_object_or_404(
        FoundItem, pk=item_id, status=FoundItem.STATUS_UNCLAIMED
    )
    form = lab_forms.FoundItemDisposeForm(request.POST)
    if form.is_valid():
        item.status = FoundItem.STATUS_DISPOSED
        item.disposal_method = form.cleaned_data["disposal_method"]
        item.disposed_on = datetime.date.today()
        item.save()
        messages.success(
            request,
            f"{item.label_id} marked as disposed ({item.get_disposal_method_display()}).",
        )
    return redirect("labs-found-items")


@login_required
def found_item_label(request, item_id):
    item = get_object_or_404(FoundItem, pk=item_id)
    return render(request, "labs/found_item_label.html", {"item": item})
