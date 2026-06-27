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

from ._common import _user_volunteer

# ── Shopping list (consumables) ────────────────────────────────────────────────


@login_required
def shopping_list(request):
    cutoff = timezone.now() - datetime.timedelta(days=30)
    items = (
        ConsumableItem.objects.filter(active=True)
        .prefetch_related(
            models.Prefetch(
                "need_flags",
                queryset=NeedFlag.objects.filter(
                    resolved_at__isnull=True
                ).select_related(
                    "flagged_by__member", "pledge__pledged_by__member"
                ),
                to_attr="open_flags",
            )
        )
        .order_by("category", "name")
    )
    recently_resolved = (
        NeedFlag.objects.filter(resolved_at__gte=cutoff)
        .select_related("item", "flagged_by__member", "resolved_by__member")
        .prefetch_related("pledge")
        .order_by("-resolved_at")[:30]
    )
    current_volunteer = _user_volunteer(request.user)
    return render(
        request,
        "labs/shopping.html",
        {
            "items": items,
            "recently_resolved": recently_resolved,
            "current_volunteer": current_volunteer,
            "CATEGORY_CHOICES": ConsumableItem.CATEGORY_CHOICES,
        },
    )


@login_required
def shopping_item(request, item_id):
    item = get_object_or_404(ConsumableItem, pk=item_id, active=True)
    suppliers = item.suppliers.all()
    open_flag = (
        item.need_flags.filter(resolved_at__isnull=True)
        .select_related("flagged_by__member", "pledge__pledged_by__member")
        .first()
    )
    history = (
        item.need_flags.filter(resolved_at__isnull=False)
        .select_related("flagged_by__member", "resolved_by__member")
        .prefetch_related("pledge__pledged_by__member")
        .order_by("-resolved_at")[:20]
    )
    current_volunteer = _user_volunteer(request.user)
    return render(
        request,
        "labs/shopping_item.html",
        {
            "item": item,
            "suppliers": suppliers,
            "open_flag": open_flag,
            "history": history,
            "current_volunteer": current_volunteer,
        },
    )


@login_required
@require_POST
def shopping_flag(request, item_id):
    item = get_object_or_404(ConsumableItem, pk=item_id, active=True)
    volunteer = _user_volunteer(request.user)
    existing = NeedFlag.objects.filter(
        item=item, resolved_at__isnull=True
    ).first()
    if existing:
        messages.info(request, f"'{item.name}' is already flagged as needed.")
    else:
        notes = request.POST.get("notes", "").strip()[:300]
        NeedFlag.objects.create(item=item, flagged_by=volunteer, notes=notes)
        messages.success(request, f"'{item.name}' flagged as needed.")
    return redirect("labs-shopping")


@login_required
@require_POST
def shopping_resolve(request, flag_id):
    flag = get_object_or_404(NeedFlag, pk=flag_id, resolved_at__isnull=True)
    volunteer = _user_volunteer(request.user)
    flag.resolved_at = timezone.now()
    flag.resolved_by = volunteer
    flag.save()
    try:
        pledge = flag.pledge
        if pledge.fulfilled_at is None:
            pledge.fulfilled_at = timezone.now()
            pledge.save()
    except ProcurementPledge.DoesNotExist:
        pass
    messages.success(request, f"'{flag.item.name}' marked as restocked.")
    return redirect("labs-shopping")


@login_required
@require_POST
def shopping_pledge(request, flag_id):
    flag = get_object_or_404(NeedFlag, pk=flag_id, resolved_at__isnull=True)
    volunteer = _user_volunteer(request.user)
    existing = getattr(flag, "pledge", None)
    if existing and existing.fulfilled_at is None:
        messages.info(
            request, f"Someone has already pledged to get '{flag.item.name}'."
        )
        return redirect("labs-shopping")
    eta_date = request.POST.get("eta_date") or None
    eta_notes = request.POST.get("eta_notes", "").strip()[:200]
    if existing:
        existing.pledged_by = volunteer
        existing.pledged_at = timezone.now()
        existing.eta_date = eta_date
        existing.eta_notes = eta_notes
        existing.fulfilled_at = None
        existing.save()
    else:
        ProcurementPledge.objects.create(
            need_flag=flag,
            pledged_by=volunteer,
            eta_date=eta_date,
            eta_notes=eta_notes,
        )
    messages.success(request, f"You've pledged to get '{flag.item.name}'.")
    return redirect("labs-shopping")


@login_required
def shopping_item_add(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()[:100]
        category = request.POST.get("category", ConsumableItem.CATEGORY_OTHER)
        notes = request.POST.get("notes", "").strip()
        valid_categories = [c[0] for c in ConsumableItem.CATEGORY_CHOICES]
        if not category or category not in valid_categories:
            category = ConsumableItem.CATEGORY_OTHER
        if name:
            item, created = ConsumableItem.objects.get_or_create(
                name__iexact=name,
                defaults={"name": name, "category": category, "notes": notes},
            )
            if created:
                messages.success(
                    request, f"'{name}' added to the shopping list."
                )
            else:
                messages.info(request, f"'{name}' is already in the list.")
        return redirect("labs-shopping")
    return render(
        request,
        "labs/shopping_item_add.html",
        {
            "CATEGORY_CHOICES": ConsumableItem.CATEGORY_CHOICES,
        },
    )


@login_required
@require_POST
def shopping_supplier_add(request, item_id):
    item = get_object_or_404(ConsumableItem, pk=item_id, active=True)
    supplier_name = request.POST.get("supplier_name", "").strip()
    if not supplier_name:
        messages.error(request, "Supplier name is required.")
        return redirect("labs-shopping-item", item_id=item_id)
    try:
        approx_price = request.POST.get("approx_price", "").strip() or None
        if approx_price:
            approx_price = float(approx_price)
    except ValueError:
        approx_price = None
    SupplierRecord.objects.create(
        item=item,
        supplier_name=supplier_name,
        ordering_notes=request.POST.get("ordering_notes", "").strip(),
        account_notes=request.POST.get("account_notes", "").strip(),
        product_url=request.POST.get("product_url", "").strip(),
        product_code=request.POST.get("product_code", "").strip(),
        unit_desc=request.POST.get("unit_desc", "").strip(),
        approx_price=approx_price,
    )
    messages.success(request, f"Supplier '{supplier_name}' added.")
    return redirect("labs-shopping-item", item_id=item_id)


@login_required
@require_POST
def shopping_supplier_delete(request, supplier_id):
    supplier = get_object_or_404(SupplierRecord, pk=supplier_id)
    item_id = supplier.item_id
    supplier.delete()
    messages.success(request, "Supplier record removed.")
    return redirect("labs-shopping-item", item_id=item_id)


@login_required
@require_POST
def shopping_pledge_cancel(request, flag_id):
    flag = get_object_or_404(NeedFlag, pk=flag_id, resolved_at__isnull=True)
    try:
        pledge = flag.pledge
    except ProcurementPledge.DoesNotExist:
        return redirect("labs-shopping")
    pledge.delete()
    messages.success(request, f"Pledge for '{flag.item.name}' cancelled.")
    return redirect("labs-shopping")


# ── Buyer views ────────────────────────────────────────────────────────────────


@login_required
def shopping_buy(request):
    """Supplier picker — entry point for someone about to do a shop."""
    open_flags_qs = NeedFlag.objects.filter(resolved_at__isnull=True)

    suppliers = Supplier.objects.filter(active=True).prefetch_related(
        "records__item"
    )

    supplier_cards = []
    for supplier in suppliers:
        item_ids = supplier.records.values_list("item_id", flat=True)
        needed_total = open_flags_qs.filter(item_id__in=item_ids).count()
        covered = (
            open_flags_qs.filter(
                item_id__in=item_ids,
                pledge__intended_supplier=supplier,
            )
            .exclude(pledge__status=ProcurementPledge.STATUS_OUT_OF_STOCK)
            .count()
        )
        supplier_cards.append(
            {
                "supplier": supplier,
                "needed_total": needed_total,
                "covered": covered,
            }
        )

    # "Needs sorting" bucket — open flags with no SupplierRecord at all
    items_with_suppliers = SupplierRecord.objects.values_list(
        "item_id", flat=True
    )
    unsorted_count = open_flags_qs.exclude(
        item_id__in=items_with_suppliers
    ).count()

    return render(
        request,
        "labs/shopping_buy.html",
        {
            "supplier_cards": supplier_cards,
            "unsorted_count": unsorted_count,
        },
    )


@login_required
def shopping_buy_supplier(request, supplier_id):
    """The core buyer sheet for a given supplier."""
    supplier = get_object_or_404(Supplier, pk=supplier_id, active=True)
    open_flags_qs = NeedFlag.objects.filter(resolved_at__isnull=True)

    # All records for this supplier with their items
    records = supplier.records.select_related("item").prefetch_related(
        models.Prefetch(
            "item__need_flags",
            queryset=open_flags_qs.select_related(
                "flagged_by__member",
                "pledge__pledged_by__member",
                "pledge__intended_supplier",
            ),
            to_attr="open_flags",
        ),
        "item__suppliers__supplier",
    )

    rows = []
    for record in records:
        item = record.item
        open_flags = item.open_flags
        if not open_flags:
            continue
        flag = open_flags[0]
        pledge = (
            getattr(flag, "pledge", None) if hasattr(flag, "pledge") else None
        )
        try:
            pledge = flag.pledge
        except ProcurementPledge.DoesNotExist:
            pledge = None

        # Other suppliers that stock this item (excluding the current one)
        other_suppliers = [
            sr.supplier
            for sr in item.suppliers.all()
            if sr.supplier_id and sr.supplier_id != supplier.pk
        ]

        rows.append(
            {
                "item": item,
                "record": record,
                "flag": flag,
                "pledge": pledge,
                "other_suppliers": other_suppliers,
            }
        )

    current_volunteer = _user_volunteer(request.user)

    return render(
        request,
        "labs/shopping_buy_supplier.html",
        {
            "supplier": supplier,
            "rows": rows,
            "current_volunteer": current_volunteer,
            "STATUS_ORDERED": ProcurementPledge.STATUS_ORDERED,
            "STATUS_OUT_OF_STOCK": ProcurementPledge.STATUS_OUT_OF_STOCK,
            "STATUS_FULFILLED": ProcurementPledge.STATUS_FULFILLED,
        },
    )


@login_required
def shopping_buy_unsorted(request):
    """Enrichment workbench — open needs with no supplier attached yet."""
    items_with_suppliers = SupplierRecord.objects.values_list(
        "item_id", flat=True
    )
    open_flags = (
        NeedFlag.objects.filter(resolved_at__isnull=True)
        .exclude(item_id__in=items_with_suppliers)
        .select_related("item", "flagged_by__member")
        .prefetch_related("item__suppliers")
        .order_by("item__category", "item__name")
    )
    active_suppliers = Supplier.objects.filter(active=True)
    return render(
        request,
        "labs/shopping_buy_unsorted.html",
        {
            "open_flags": open_flags,
            "active_suppliers": active_suppliers,
            "CATEGORY_CHOICES": ConsumableItem.CATEGORY_CHOICES,
        },
    )


@login_required
@require_POST
def shopping_item_enrich(request, item_id):
    """Attach a supplier (existing or new) to an item from the unsorted workbench."""
    item = get_object_or_404(ConsumableItem, pk=item_id, active=True)
    supplier_name = request.POST.get("supplier_name", "").strip()
    supplier_id = request.POST.get("supplier_id", "").strip()

    supplier = None
    if supplier_id:
        try:
            supplier = Supplier.objects.get(pk=int(supplier_id), active=True)
        except (Supplier.DoesNotExist, ValueError):
            pass

    if supplier is None and supplier_name:
        supplier, _ = Supplier.objects.get_or_create(
            name__iexact=supplier_name,
            defaults={"name": supplier_name},
        )
    elif supplier is None:
        messages.error(request, "Choose or type a supplier name.")
        return redirect("labs-shopping-buy-unsorted")

    try:
        approx_price = request.POST.get("approx_price", "").strip() or None
        if approx_price:
            approx_price = float(approx_price)
    except ValueError:
        approx_price = None

    SupplierRecord.objects.create(
        item=item,
        supplier=supplier,
        supplier_name=supplier.name,
        product_code=request.POST.get("product_code", "").strip(),
        unit_desc=request.POST.get("unit_desc", "").strip(),
        approx_price=approx_price,
        ordering_notes=request.POST.get("ordering_notes", "").strip(),
    )
    messages.success(request, f"'{item.name}' linked to {supplier.name}.")
    return redirect("labs-shopping-buy-unsorted")


@login_required
@require_POST
def shopping_buy_add(request, flag_id):
    """Add an item to a supplier's order (create/update pledge with supplier + status=ordered)."""
    flag = get_object_or_404(NeedFlag, pk=flag_id, resolved_at__isnull=True)
    supplier_id = request.POST.get("supplier_id")
    supplier = (
        get_object_or_404(Supplier, pk=supplier_id) if supplier_id else None
    )

    volunteer = _user_volunteer(request.user)

    existing = getattr(flag, "pledge", None)
    try:
        existing = flag.pledge
    except ProcurementPledge.DoesNotExist:
        existing = None

    if existing and existing.fulfilled_at is None:
        existing.intended_supplier = supplier
        existing.status = ProcurementPledge.STATUS_ORDERED
        existing.pledged_by = volunteer
        existing.save()
    else:
        ProcurementPledge.objects.create(
            need_flag=flag,
            pledged_by=volunteer,
            intended_supplier=supplier,
            status=ProcurementPledge.STATUS_ORDERED,
        )
    messages.success(request, f"'{flag.item.name}' added to order.")
    if supplier_id:
        return redirect("labs-shopping-buy-supplier", supplier_id=supplier_id)
    return redirect("labs-shopping-buy")


@login_required
@require_POST
def shopping_out_of_stock(request, flag_id):
    """Mark an item as out of stock at a supplier — keeps the need open."""
    flag = get_object_or_404(NeedFlag, pk=flag_id, resolved_at__isnull=True)
    supplier_id = request.POST.get("supplier_id")
    supplier = (
        get_object_or_404(Supplier, pk=supplier_id) if supplier_id else None
    )

    volunteer = _user_volunteer(request.user)

    note = f"Out of stock at {supplier.name}" if supplier else "Out of stock"

    existing = None
    try:
        existing = flag.pledge
    except ProcurementPledge.DoesNotExist:
        pass

    if existing and existing.fulfilled_at is None:
        existing.status = ProcurementPledge.STATUS_OUT_OF_STOCK
        existing.intended_supplier = supplier
        existing.status_notes = note
        existing.save()
    else:
        ProcurementPledge.objects.create(
            need_flag=flag,
            pledged_by=volunteer,
            intended_supplier=supplier,
            status=ProcurementPledge.STATUS_OUT_OF_STOCK,
            status_notes=note,
        )
    messages.warning(
        request,
        f"'{flag.item.name}' marked out of stock at {supplier.name if supplier else 'supplier'}.",
    )
    if supplier_id:
        return redirect("labs-shopping-buy-supplier", supplier_id=supplier_id)
    return redirect("labs-shopping-buy")
