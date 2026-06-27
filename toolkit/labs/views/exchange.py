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

# ── Community exchange ────────────────────────────────────────────────────────


@login_required
def exchange_list(request):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    items = ExchangeItem.objects.filter(active=True).select_related(
        "owner_volunteer__member"
    )

    listing_type = request.GET.get("type", "")
    category = request.GET.get("category", "")
    show_unavailable = request.GET.get("unavailable", "") == "1"

    if listing_type in (
        ExchangeItem.TYPE_LEND,
        ExchangeItem.TYPE_GIVE,
        ExchangeItem.TYPE_SHARE,
    ):
        items = items.filter(listing_type=listing_type)
    if category:
        items = items.filter(category=category)
    if not show_unavailable:
        items = items.exclude(
            status__in=[
                ExchangeItem.STATUS_WITHDRAWN,
                ExchangeItem.STATUS_ALL_GONE,
            ]
        )

    return render(
        request,
        "labs/exchange.html",
        {
            "items": items,
            "listing_type": listing_type,
            "category": category,
            "show_unavailable": show_unavailable,
            "type_choices": ExchangeItem.TYPE_CHOICES,
            "category_choices": ExchangeItem.CATEGORY_CHOICES,
        },
    )


@login_required
def exchange_item(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    can_edit = request.user.is_superuser or (
        item.owner_volunteer
        and hasattr(request.user, "volunteer")
        and item.owner_volunteer == request.user.volunteer
    )
    can_see_contact = request.user.is_superuser or (
        item.added_by_id and item.added_by_id == request.user.pk
    )
    return render(
        request,
        "labs/exchange_item.html",
        {
            "item": item,
            "can_edit": can_edit,
            "can_see_contact": can_see_contact,
        },
    )


@login_required
def exchange_add(request):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    if request.method == "POST":
        form = lab_forms.ExchangeItemForm(
            request.POST, request.FILES, user=request.user
        )
        if form.is_valid():
            item = form.save(commit=False)
            item.added_by = request.user
            if (
                item.owner_type == ExchangeItem.OWNER_VOLUNTEER
                and not item.owner_volunteer
            ):
                if hasattr(request.user, "volunteer"):
                    item.owner_volunteer = request.user.volunteer
            item.save()
            messages.success(
                request, f"'{item.name}' added to the community exchange."
            )
            return redirect("labs-exchange-item", item_id=item.pk)
    else:
        initial = {}
        if hasattr(request.user, "volunteer"):
            initial["owner_volunteer"] = request.user.volunteer
        form = lab_forms.ExchangeItemForm(initial=initial, user=request.user)

    return render(
        request, "labs/exchange_form.html", {"form": form, "editing": False}
    )


@login_required
def exchange_edit(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    can_edit = request.user.is_superuser or (
        item.owner_volunteer
        and hasattr(request.user, "volunteer")
        and item.owner_volunteer == request.user.volunteer
    )
    if not can_edit:
        return HttpResponseForbidden(
            "You can only edit items you listed yourself."
        )

    if request.method == "POST":
        form = lab_forms.ExchangeItemForm(
            request.POST, request.FILES, instance=item, user=request.user
        )
        if form.is_valid():
            form.save()
            messages.success(request, f"'{item.name}' updated.")
            return redirect("labs-exchange-item", item_id=item.pk)
    else:
        form = lab_forms.ExchangeItemForm(instance=item, user=request.user)

    return render(
        request,
        "labs/exchange_form.html",
        {"form": form, "item": item, "editing": True},
    )


@login_required
@require_POST
def exchange_withdraw(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    can_edit = request.user.is_superuser or (
        item.owner_volunteer
        and hasattr(request.user, "volunteer")
        and item.owner_volunteer == request.user.volunteer
    )
    if not can_edit:
        return HttpResponseForbidden()

    item.active = False
    item.status = ExchangeItem.STATUS_WITHDRAWN
    item.save()
    messages.success(request, f"'{item.name}' withdrawn from the exchange.")
    return redirect("labs-exchange")


@login_required
@require_POST
def exchange_mark_on_loan(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    if item.listing_type != ExchangeItem.TYPE_LEND:
        return HttpResponseForbidden()
    if item.status != ExchangeItem.STATUS_AVAILABLE:
        messages.warning(
            request, f"'{item.name}' isn't available to borrow right now."
        )
        return redirect("labs-exchange-item", item_id=item.pk)
    borrowed_by_name = request.POST.get("borrowed_by_name", "").strip()
    borrowed_by_contact = request.POST.get("borrowed_by_contact", "").strip()
    if not borrowed_by_name:
        messages.error(
            request,
            "Please enter your name so the owner knows who has the item.",
        )
        return redirect("labs-exchange-item", item_id=item.pk)
    if not borrowed_by_contact:
        messages.error(
            request,
            "Please enter a phone number or email so the owner can reach you if needed.",
        )
        return redirect("labs-exchange-item", item_id=item.pk)
    item.status = ExchangeItem.STATUS_ON_LOAN
    item.borrowed_by = request.user
    item.borrowed_by_name = borrowed_by_name
    item.borrowed_by_contact = borrowed_by_contact
    item.save()
    messages.success(request, f"'{item.name}' marked as on loan.")
    return redirect("labs-exchange-item", item_id=item.pk)


@login_required
@require_POST
def exchange_mark_returned(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    if item.listing_type != ExchangeItem.TYPE_LEND:
        return HttpResponseForbidden()
    if item.status not in (
        ExchangeItem.STATUS_ON_LOAN,
        ExchangeItem.STATUS_MISSING,
    ):
        messages.warning(
            request,
            f"'{item.name}' isn't currently marked as on loan or missing.",
        )
        return redirect("labs-exchange-item", item_id=item.pk)
    was_missing = item.status == ExchangeItem.STATUS_MISSING
    item.status = ExchangeItem.STATUS_AVAILABLE
    item.borrowed_by = None
    item.borrowed_by_name = ""
    item.borrowed_by_contact = ""
    item.save()
    if was_missing:
        messages.success(
            request,
            f"'{item.name}' marked as found — available to borrow again.",
        )
    else:
        messages.success(
            request,
            f"'{item.name}' marked as returned — available to borrow again.",
        )
    return redirect("labs-exchange-item", item_id=item.pk)


@login_required
@require_POST
def exchange_mark_all_gone(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    if item.listing_type != ExchangeItem.TYPE_SHARE:
        return HttpResponseForbidden()
    can_edit = request.user.is_superuser or (
        item.owner_volunteer
        and hasattr(request.user, "volunteer")
        and item.owner_volunteer == request.user.volunteer
    )
    if not can_edit:
        return HttpResponseForbidden()
    item.status = ExchangeItem.STATUS_ALL_GONE
    item.save()
    messages.success(request, f"'{item.name}' marked as all gone.")
    return redirect("labs-exchange")


@login_required
@require_POST
def exchange_mark_missing(request, item_id):
    cfg = get_site_config()
    if not cfg.community_exchange_enabled:
        from django.http import Http404

        raise Http404

    item = get_object_or_404(ExchangeItem, pk=item_id, active=True)
    can_edit = request.user.is_superuser or (
        item.owner_volunteer
        and hasattr(request.user, "volunteer")
        and item.owner_volunteer == request.user.volunteer
    )
    if not can_edit:
        return HttpResponseForbidden()
    item.status = ExchangeItem.STATUS_MISSING
    item.save()
    messages.warning(request, f"'{item.name}' marked as missing.")
    return redirect("labs-exchange-item", item_id=item.pk)
