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


def collectives_public(request):
    from toolkit.diary.models import get_site_config

    items = (
        Collective.objects.filter(active=True, listed_publicly=True)
        .exclude(public_copy="")
        .order_by("display_order", "name")
    )
    config = get_site_config()
    return render(
        request,
        "collectives_public.html",
        {
            "collectives": items,
            "collectives_intro": config.collectives_intro,
        },
    )


@login_required
def collectives(request):
    items = (
        Collective.objects.filter(active=True)
        .select_related("updated_by")
        .prefetch_related("links")
    )
    current_volunteer = _user_volunteer(request.user)
    if current_volunteer is not None:
        user_collective_slugs = frozenset(
            current_volunteer.collectives.values_list("slug", flat=True)
        )
        user_is_volunteer = True
    else:
        user_collective_slugs = frozenset()
        user_is_volunteer = False
    config = get_site_config()
    return render(
        request,
        "labs/collectives.html",
        {
            "collectives": items,
            "user_collective_slugs": user_collective_slugs,
            "user_is_volunteer": user_is_volunteer,
            "mailing_list_signup_url": config.collectives_mailing_list_signup_url,
        },
    )


@login_required
@require_POST
def collective_join(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    if collective.invite_only:
        messages.error(
            request,
            f"{collective.name} is invite-only — membership is managed by admins.",
        )
        return redirect("labs-collectives")
    if hasattr(request.user, "volunteer"):
        request.user.volunteer.collectives.add(collective)
        messages.success(request, f"You've joined {collective.name}.")
    else:
        messages.error(
            request, "You need a volunteer profile to join a collective."
        )
    return redirect("labs-collectives")


@login_required
@require_POST
def collective_leave(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    if hasattr(request.user, "volunteer"):
        request.user.volunteer.collectives.remove(collective)
        messages.success(request, f"You've left {collective.name}.")
    else:
        messages.error(
            request, "You need a volunteer profile to leave a collective."
        )
    return redirect("labs-collectives")


@login_required
def collectives_print(request):
    items = Collective.objects.filter(active=True)
    return render(
        request, "labs/collectives_print.html", {"collectives": items}
    )


@login_required
@require_http_methods(["GET", "POST"])
def collective_edit(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    if request.method == "POST":
        form = lab_forms.CollectiveForm(request.POST, instance=collective)
        links_formset = lab_forms.CollectiveLinkFormSet(
            request.POST, instance=collective
        )
        roles_formset = lab_forms.CollectiveRoleFormSet(
            request.POST, instance=collective
        )
        if (
            form.is_valid()
            and links_formset.is_valid()
            and roles_formset.is_valid()
        ):
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            links_formset.save()
            roles_formset.save()
            messages.success(request, f"'{collective.name}' updated.")
            return redirect("labs-collectives")
    else:
        form = lab_forms.CollectiveForm(instance=collective)
        links_formset = lab_forms.CollectiveLinkFormSet(instance=collective)
        roles_formset = lab_forms.CollectiveRoleFormSet(instance=collective)
    return render(
        request,
        "labs/collective_edit.html",
        {
            "collective": collective,
            "form": form,
            "links_formset": links_formset,
            "roles_formset": roles_formset,
        },
    )
