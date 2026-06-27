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


def donation_list(request):
    items = DonationItem.objects.filter(active=True)
    categories = {}
    for item in items:
        cat = item.category or "General"
        categories.setdefault(cat, []).append(item)
    cfg = get_site_config()
    return render(
        request,
        "labs/donations.html",
        {
            "categories": categories,
            "donations_intro": cfg.donations_intro,
            "STATUS_WANTED": DonationItem.STATUS_WANTED,
            "STATUS_CHECK_FIRST": DonationItem.STATUS_CHECK_FIRST,
            "STATUS_NOT_NEEDED": DonationItem.STATUS_NOT_NEEDED,
        },
    )


@feature_required("donations_manage")
def donation_manage(request):
    items = DonationItem.objects.select_related("last_edited_by").order_by(
        "category", "display_order", "name"
    )
    cfg = get_site_config()

    if request.method == "POST":
        action = request.POST.get("_action")

        if action == "save_intro":
            intro_form = lab_forms.DonationsIntroForm(request.POST)
            if intro_form.is_valid():
                cfg.donations_intro = intro_form.cleaned_data["intro"]
                cfg.save()
                messages.success(request, "Page introduction updated.")
            return redirect("labs-donations-manage")

        elif action == "add":
            form = lab_forms.DonationItemForm(request.POST)
            if form.is_valid():
                item = form.save(commit=False)
                item.last_edited_by = request.user
                item.save()
                messages.success(request, f"'{item.name}' added.")
                return redirect("labs-donations-manage")
            else:
                add_form = form
                intro_form = lab_forms.DonationsIntroForm(
                    initial={"intro": cfg.donations_intro}
                )
                return render(
                    request,
                    "labs/donations_manage.html",
                    {
                        "items": items,
                        "intro_form": intro_form,
                        "add_form": add_form,
                        "STATUS_CHOICES": DonationItem.STATUS_CHOICES,
                    },
                )

        elif action == "edit":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(DonationItem, pk=item_id)
            form = lab_forms.DonationItemForm(request.POST, instance=item)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.last_edited_by = request.user
                obj.save()
                messages.success(request, f"'{obj.name}' updated.")
            return redirect("labs-donations-manage")

        elif action == "delete":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(DonationItem, pk=item_id)
            name = item.name
            item.delete()
            messages.success(request, f"'{name}' removed.")
            return redirect("labs-donations-manage")

    add_form = lab_forms.DonationItemForm()
    intro_form = lab_forms.DonationsIntroForm(
        initial={"intro": cfg.donations_intro}
    )
    return render(
        request,
        "labs/donations_manage.html",
        {
            "items": items,
            "intro_form": intro_form,
            "add_form": add_form,
            "STATUS_CHOICES": DonationItem.STATUS_CHOICES,
            "STATUS_WANTED": DonationItem.STATUS_WANTED,
            "STATUS_CHECK_FIRST": DonationItem.STATUS_CHECK_FIRST,
            "STATUS_NOT_NEEDED": DonationItem.STATUS_NOT_NEEDED,
        },
    )
