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


def _user_can_post_bulletin(user):
    cfg = get_site_config()
    level = cfg.bulletin_post_permission
    if level == SiteConfiguration.BULLETIN_POST_ALL:
        return True
    if level == SiteConfiguration.BULLETIN_POST_PROGRAMMER:
        return user.has_perm("toolkit.write")
    if level == SiteConfiguration.BULLETIN_POST_PANOPTICON:
        return user.is_superuser
    return False


# ── Bulletins ──────────────────────────────────────────────────────────────────


def _active_bulletins_qs():
    """Bulletins that are still active (not past their effective expiry).

    Combines explicit expiries (`expires_at` > now or NULL) with the site
    default (`bulletin_default_expiry_days`). The site default is applied in
    Python because comparing `created_at + interval(days)` against `now` in a
    DB-agnostic way is awkward; the relevant set is small.
    """
    now = timezone.now()
    qs = Bulletin.objects.filter(
        models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)
    ).select_related("author")
    cfg = get_site_config()
    default_days = cfg.bulletin_default_expiry_days
    if default_days == 0:
        return qs
    cutoff = now - datetime.timedelta(days=default_days)
    return qs.filter(
        models.Q(expires_at__isnull=False) | models.Q(created_at__gt=cutoff)
    )


def _unread_bulletins_for(user):
    """Active bulletins not yet read by `user`, pinned first, newest first.

    Used by both the dashboard banner and the bulletin board's unread badge.
    """
    if not user.is_authenticated:
        return Bulletin.objects.none()
    read_subq = BulletinRead.objects.filter(bulletin=OuterRef("pk"), user=user)
    return (
        _active_bulletins_qs()
        .annotate(is_read=Exists(read_subq))
        .filter(is_read=False)
        .order_by("-pinned", "-created_at")
    )


@login_required
def bulletin_list(request):
    bulletins = list(_active_bulletins_qs().order_by("-pinned", "-created_at"))
    read_ids = set(
        BulletinRead.objects.filter(
            user=request.user, bulletin__in=bulletins
        ).values_list("bulletin_id", flat=True)
    )
    for b in bulletins:
        b.is_read = b.id in read_ids
    cfg = get_site_config()
    return render(
        request,
        "labs/bulletins.html",
        {
            "bulletins": bulletins,
            "guidance": cfg.bulletin_guidance,
            "is_archive": False,
            "can_post": _user_can_post_bulletin(request.user),
            "can_curate": request.user.has_perm("toolkit.write"),
            "can_delete": request.user.is_superuser,
        },
    )


@login_required
def bulletin_archive(request):
    """Bulletins that have passed their effective expiry."""
    now = timezone.now()
    cfg = get_site_config()
    default_days = cfg.bulletin_default_expiry_days
    qs = Bulletin.objects.select_related("author")
    if default_days == 0:
        bulletins = list(qs.filter(expires_at__lte=now))
    else:
        cutoff = now - datetime.timedelta(days=default_days)
        bulletins = list(
            qs.filter(
                models.Q(expires_at__lte=now)
                | (
                    models.Q(expires_at__isnull=True)
                    & models.Q(created_at__lte=cutoff)
                )
            )
        )
    bulletins.sort(key=lambda b: b.created_at, reverse=True)
    return render(
        request,
        "labs/bulletins.html",
        {
            "bulletins": bulletins,
            "guidance": "",
            "is_archive": True,
            "can_post": _user_can_post_bulletin(request.user),
            "can_curate": request.user.has_perm("toolkit.write"),
            "can_delete": request.user.is_superuser,
        },
    )


BULLETIN_RATE_LIMIT_PER_HOUR = 5


@login_required
@require_http_methods(["GET", "POST"])
def bulletin_add(request):
    if not _user_can_post_bulletin(request.user):
        return HttpResponseForbidden(
            "You don't have permission to post bulletins."
        )
    if request.method == "POST":
        form = lab_forms.BulletinForm(request.POST)
        # Rate limit: cap recent posts per author to defend against a
        # compromised account flooding the board / dashboard.
        recent = Bulletin.objects.filter(
            author=request.user,
            created_at__gte=timezone.now() - datetime.timedelta(hours=1),
        ).count()
        if recent >= BULLETIN_RATE_LIMIT_PER_HOUR:
            messages.error(
                request,
                f"You've already posted {recent} bulletins in the last hour. "
                "Wait a bit before posting more.",
            )
            return redirect("labs-bulletins")
        if form.is_valid():
            bulletin = form.save(commit=False)
            bulletin.author = request.user
            bulletin.save()
            messages.success(request, "Bulletin posted.")
            return redirect("labs-bulletins")
    else:
        form = lab_forms.BulletinForm()
    cfg = get_site_config()
    return render(
        request,
        "labs/bulletin_form.html",
        {
            "form": form,
            "guidance": cfg.bulletin_guidance,
        },
    )


@login_required
@require_POST
def bulletin_read_all(request):
    """Mark every currently-active bulletin as read for the current user."""
    active = list(_active_bulletins_qs().values_list("id", flat=True))
    if active:
        existing = set(
            BulletinRead.objects.filter(
                user=request.user, bulletin_id__in=active
            ).values_list("bulletin_id", flat=True)
        )
        BulletinRead.objects.bulk_create(
            [
                BulletinRead(bulletin_id=b, user=request.user)
                for b in active
                if b not in existing
            ]
        )
    return redirect(request.META.get("HTTP_REFERER") or "toolkit-index")


@login_required
@require_POST
def bulletin_read(request, bulletin_id):
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    BulletinRead.objects.get_or_create(bulletin=bulletin, user=request.user)
    # 204 keeps htmx / fetch callers simple; redirect for vanilla form POSTs.
    if (
        request.headers.get("HX-Request")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    ):
        return HttpResponse(status=204)
    return redirect(request.META.get("HTTP_REFERER") or "toolkit-index")


@login_required
@write_required_strict
@require_POST
def bulletin_pin(request, bulletin_id):
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    bulletin.pinned = not bulletin.pinned
    bulletin.save(update_fields=["pinned"])
    messages.success(
        request, f"Bulletin {'pinned' if bulletin.pinned else 'unpinned'}."
    )
    return redirect("labs-bulletins")


@login_required
@write_required_strict
@require_http_methods(["GET", "POST"])
def bulletin_expire(request, bulletin_id):
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    if request.method == "POST":
        form = lab_forms.BulletinExpiryForm(request.POST, instance=bulletin)
        if form.is_valid():
            form.save()
            messages.success(request, "Expiry updated.")
            return redirect("labs-bulletins")
    else:
        form = lab_forms.BulletinExpiryForm(instance=bulletin)
    return render(
        request,
        "labs/bulletin_form.html",
        {
            "form": form,
            "bulletin": bulletin,
            "expiry_mode": True,
        },
    )


@login_required
@require_POST
def bulletin_delete(request, bulletin_id):
    if not request.user.is_superuser:
        return HttpResponseForbidden("Panopticon only.")
    bulletin = get_object_or_404(Bulletin, pk=bulletin_id)
    title = bulletin.title
    bulletin.delete()
    messages.success(request, f"Bulletin '{title}' deleted.")
    return redirect("labs-bulletins")
