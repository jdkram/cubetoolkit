import logging
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
from django.db import transaction
from django.contrib.auth.tokens import default_token_generator
from django.core.signing import BadSignature, Signer
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required, permission_required
from toolkit.toolkit_auth.decorators import panopticon_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils.text import slugify
from django.views.decorators.http import require_POST, require_safe
from django.db.models import (
    Count,
    Exists,
    F,
    Max,
    OuterRef,
    Prefetch,
    Value,
)
from django.db.models.functions import Coalesce, NullIf
from django.utils import timezone
import csv

from toolkit.members.forms import (
    UserForm,
    VolunteerForm,
    MemberFormWithoutNotes,
    TrainingRecordForm,
    GroupTrainingForm,
)
from toolkit.members.models import Member, Volunteer, TrainingRecord, ExportAuditLog, LastGaspEmailLog
from toolkit.diary.models import Role, RotaEntry, get_site_config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@panopticon_required
@require_safe
def view_volunteer_list(request):
    show_retired = request.GET.get("show-retired", None) is not None
    show_dormant = request.GET.get("show-dormant", None) is not None
    gst_enabled = get_site_config().general_training_enabled

    volunteers = (
        Volunteer.objects.order_by("member__name")
        .select_related()
        .prefetch_related("member")
    )

    if gst_enabled:
        qs = TrainingRecord.objects.filter(
            training_type=TrainingRecord.GENERAL_TRAINING
        ).order_by("-training_date")
        volunteers = volunteers.prefetch_related(
            Prefetch("training_records", queryset=qs, to_attr="general_training")
        )

    if show_retired:
        pass  # show everything
    elif show_dormant:
        volunteers = volunteers.filter(status__in=[Volunteer.STATUS_ACTIVE, Volunteer.STATUS_DORMANT])
    else:
        volunteers = volunteers.filter(status=Volunteer.STATUS_ACTIVE)
    active_count = sum(1 for v in volunteers if v.is_active)
    context = {
        "volunteers": volunteers,
        "default_mugshot": settings.DEFAULT_MUGSHOT,
        "retired_data_included": show_retired,
        "dormant_data_included": show_dormant,
        "active_count": active_count,
        "general_training_enabled": gst_enabled,
        "general_training_desc": TrainingRecord.GENERAL_TRAINING_DESC,
    }
    return render(request, "volunteer_list.html", context)


# Field-group definitions for the volunteer CSV export.
# Each group: (group_id, label, is_sensitive, fields)
# fields: list of (column_header, lambda volunteer -> value)
_EXPORT_FIELD_GROUPS = [
    (
        "basic",
        "Basic (name, email, status)",
        False,
        [
            ("Name", lambda v: v.member.name),
            ("Email", lambda v: v.member.email),
            ("Status", lambda v: v.status),
            ("Collectives", lambda v: ", ".join(c.name for c in v.collectives.all())),
        ],
    ),
    (
        "contact",
        "Contact details (phone numbers)",
        True,
        [
            ("Phone", lambda v: v.member.phone),
            ("Alternate phone", lambda v: v.member.altphone),
        ],
    ),
    (
        "address",
        "Home address",
        True,
        [
            ("Address", lambda v: v.member.address.replace("\r\n", ", ")),
            ("City", lambda v: v.member.posttown),
            ("Postcode", lambda v: v.member.postcode),
        ],
    ),
    (
        "notes",
        "Internal notes",
        False,
        [
            ("Member notes", lambda v: v.member.notes),
            ("Volunteer notes", lambda v: v.notes),
        ],
    ),
    (
        "dates",
        "Dates (inducted, last update)",
        False,
        [
            (
                "Inducted",
                lambda v: (
                    "Pre-toolkit"
                    if v.is_old()
                    else v.member.created_at.strftime("%d %b %Y")
                ),
            ),
            ("Last update", lambda v: v.member.updated_at.strftime("%d %b %Y")),
        ],
    ),
]
_EXPORT_GROUP_IDS = {g[0] for g in _EXPORT_FIELD_GROUPS}
_SENSITIVE_GROUP_IDS = {g[0] for g in _EXPORT_FIELD_GROUPS if g[2]}


@panopticon_required
def export_volunteers_as_csv(request):
    """Full export page: field-group selector + PII warning + audit log."""
    if request.method == "POST":
        selected_ids = [
            gid for gid in _EXPORT_GROUP_IDS
            if request.POST.get(f"group_{gid}")
        ]
        if not selected_ids:
            selected_ids = ["basic"]

        # Build flat list of (header, accessor) for selected groups.
        columns = []
        for gid, _label, _sensitive, fields in _EXPORT_FIELD_GROUPS:
            if gid in selected_ids:
                columns.extend(fields)

        volunteers = (
            Volunteer.objects.active()
            .select_related("member")
            .prefetch_related("collectives")
            .order_by("member__name")
        )
        rows = list(volunteers)

        # Log the export.
        export_reason = request.POST.get("export_reason", "").strip()
        is_sensitive = bool(set(selected_ids) & _SENSITIVE_GROUP_IDS)
        logger.info(
            f"User {request.user} exported {len(rows)} volunteers "
            f"(fields: {selected_ids}, sensitive={is_sensitive}, reason={export_reason!r})"
        )
        ExportAuditLog.objects.create(
            exported_by=request.user,
            fields_included=selected_ids,
            recipient_count=len(rows),
            export_reason=export_reason,
        )

        now = datetime.now().strftime("%d %b %Y %I-%M %p")
        file_name = f"{settings.VENUE['name']} Volunteers {now}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        writer = csv.writer(response)
        writer.writerow([col[0] for col in columns])
        for volunteer in rows:
            writer.writerow([col[1](volunteer) for col in columns])
        return response

    # GET: render the field selection page.
    return render(request, "volunteer_export.html", {
        "field_groups": _EXPORT_FIELD_GROUPS,
        "sensitive_ids": _SENSITIVE_GROUP_IDS,
    })


@panopticon_required
@require_safe
def export_audit_log(request):
    """Audit log of all volunteer CSV exports."""
    logs = ExportAuditLog.objects.select_related("exported_by").all()[:200]
    return render(request, "volunteer_export_audit.html", {"logs": logs})


@panopticon_required
@require_safe
def view_volunteer_summary(request):
    order = request.GET.get("order", "name")

    base_qs = (
        Volunteer.objects.exclude(
            status__in=[Volunteer.STATUS_RETIRED, Volunteer.STATUS_ANONYMISED]
        )
        .select_related("member", "user")
        .annotate(
            is_programmer=Exists(
                Volunteer.objects.filter(
                    pk=OuterRef("pk"),
                    user__groups__name="Programmers",
                )
            )
        )
    )

    if "name" in order:
        volunteers = base_qs.order_by("member__name")
        sort_type = "name"
    elif "logged" in order:
        volunteers = base_qs.order_by("-user__last_login")
        sort_type = "last logged in date"
    else:
        volunteers = base_qs.order_by("-member__created_at")
        sort_type = "induction date"

    active_count = volunteers.filter(status=Volunteer.STATUS_ACTIVE).count()
    dormant_count = volunteers.filter(status=Volunteer.STATUS_DORMANT).count()

    now = timezone.now()
    logged_in_last_30_days = base_qs.filter(user__last_login__gte=now - timedelta(days=30)).count()
    logged_in_last_365_days = base_qs.filter(user__last_login__gte=now - timedelta(days=365)).count()

    context = {
        "volunteers": volunteers,
        "active_count": active_count,
        "dormant_count": dormant_count,
        "sort_type": sort_type,
        "dawn_of_toolkit": settings.DAWN_OF_TOOLKIT,
        "logged_in_last_30_days": logged_in_last_30_days,
        "logged_in_last_365_days": logged_in_last_365_days,
    }
    return render(request, "volunteer_summary.html", context)


@panopticon_required
@require_safe
def view_volunteer_pool_health(request):
    """Read-only Panopticon view of volunteers needing attention.

    Surfaces three tiers ordered by how safe it is to anonymise them:

      1. Never onboarded — past retention window, never logged in. These accounts
         have no engagement history; safest to remove.
      2. Long inactive — past retention window, previously logged in. They used to
         participate; still clearly eligible under data-minimisation.
      3. Recently dormant — marked dormant but within the retention window. May
         still return; no bulk action available here.

    The dormant section (tier 3) excludes any volunteer already in tiers 1/2 to
    avoid double-counting.
    """
    config = get_site_config()

    all_purge = Volunteer.objects.purge_candidates(config.volunteer_purge_days)

    never_onboarded = (
        all_purge.filter(user__last_login__isnull=True)
        .select_related("member", "user")
        .annotate(last_gasp_sent_at=Max("last_gasp_emails__sent_at"))
        .order_by("last_activity", "member__name")
    )
    long_inactive = (
        all_purge.filter(user__last_login__isnull=False)
        .select_related("member", "user")
        .order_by("last_activity", "member__name")
    )

    purge_pks = all_purge.values_list("pk", flat=True)
    recently_dormant = (
        Volunteer.objects.filter(status=Volunteer.STATUS_DORMANT)
        .exclude(pk__in=purge_pks)
        .select_related("member", "user")
        .order_by("user__last_login", "member__name")
    )

    retention_exempt = (
        Volunteer.objects.filter(retention_exempt=True)
        .select_related("member", "user")
        .order_by("member__name")
    )

    suspended = (
        Volunteer.objects.filter(status=Volunteer.STATUS_SUSPENDED)
        .select_related("member", "user")
        .order_by("member__name")
    )

    status_counts = {
        row["status"]: row["count"]
        for row in Volunteer.objects.values("status").annotate(count=Count("pk"))
    }

    context = {
        "never_onboarded": never_onboarded,
        "never_onboarded_count": never_onboarded.count(),
        "long_inactive": long_inactive,
        "long_inactive_count": long_inactive.count(),
        "recently_dormant": recently_dormant,
        "recently_dormant_count": recently_dormant.count(),
        "retention_exempt": retention_exempt,
        "retention_exempt_count": retention_exempt.count(),
        "suspended": suspended,
        "suspended_count": suspended.count(),
        "status_counts": status_counts,
        "dormancy_days": config.volunteer_dormancy_days,
        "never_logged_in_grace_days": config.volunteer_never_logged_in_grace_days,
        "purge_days": config.volunteer_purge_days,
        "last_gasp_email_enabled": config.last_gasp_email_enabled,
        "last_gasp_cooldown_days": config.last_gasp_cooldown_days,
    }
    return render(request, "volunteer_pool_health.html", context)


@panopticon_required
def bulk_anonymise_volunteers(request):
    """Two-step bulk anonymisation for purge candidates.

    Step 1 (POST from pool-health page): receive selected volunteer IDs, re-validate
    that each is still a purge candidate, show a confirmation page with a typed-phrase
    guard.

    Step 2 (POST from confirmation page): execute anonymise() on each. Passing the IDs
    through hidden fields avoids any session state.

    Only purge candidates (dormant/retired past the retention window) can be bulk-
    anonymised here. Volunteers outside that cohort are silently skipped so a stale
    selection (e.g. one record was edited between page load and confirm) never errors.
    """
    config = get_site_config()
    purge_days = config.volunteer_purge_days

    if request.method == "POST":
        action = request.POST.get("action", "select")

        if action == "select":
            raw_ids = request.POST.getlist("volunteer_ids")
            try:
                selected_ids = [int(i) for i in raw_ids if i]
            except ValueError:
                messages.error(request, "Invalid volunteer selection.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            if not selected_ids:
                messages.warning(request, "No volunteers selected.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            candidates = (
                Volunteer.objects.purge_candidates(purge_days)
                .filter(pk__in=selected_ids)
                .select_related("member", "user")
                .order_by("member__name")
            )
            candidates = list(candidates)
            if not candidates:
                messages.warning(
                    request,
                    "None of the selected volunteers are currently purge candidates "
                    "(they may have been edited since the page loaded).",
                )
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            return render(
                request,
                "bulk_anonymise_confirm.html",
                {
                    "candidates": candidates,
                    "count": len(candidates),
                    "expected_phrase": f"anonymise {len(candidates)} volunteers",
                },
            )

        elif action == "confirm":
            raw_ids = request.POST.getlist("volunteer_ids")
            try:
                selected_ids = [int(i) for i in raw_ids if i]
            except ValueError:
                messages.error(request, "Invalid volunteer selection.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            candidates = list(
                Volunteer.objects.purge_candidates(purge_days)
                .filter(pk__in=selected_ids)
                .select_related("member", "user")
            )
            expected_phrase = f"anonymise {len(candidates)} volunteers"
            confirm_text = request.POST.get("confirm_phrase", "").strip()

            if confirm_text != expected_phrase:
                messages.error(
                    request,
                    f'Confirmation phrase did not match — type exactly: "{expected_phrase}"',
                )
                return render(
                    request,
                    "bulk_anonymise_confirm.html",
                    {
                        "candidates": candidates,
                        "count": len(candidates),
                        "expected_phrase": expected_phrase,
                    },
                )

            anonymised = 0
            for vol in candidates:
                rota_count = vol.anonymise(performed_by=request.user)
                logger.info(
                    "Volunteer pk=%s bulk-anonymised by %s (%d rota entries cleared)",
                    vol.pk,
                    request.user.username,
                    rota_count,
                )
                anonymised += 1

            messages.success(
                request,
                f"Anonymised {anonymised} volunteer record{'s' if anonymised != 1 else ''}.",
            )
            return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    return HttpResponseRedirect(reverse("view-volunteer-pool-health"))


@panopticon_required
def bulk_delete_never_onboarded(request):
    """Two-step hard-delete for never-logged-in purge candidates.

    Volunteers who never logged in almost certainly have no rota history, so
    hard deletion (Member + User + Volunteer removed entirely) is cleaner than
    anonymisation. We check for RotaEntry rows anyway — if any exist the account
    falls back to anonymise instead of delete, and the confirmation page makes
    the split visible to the panopticon.
    """
    config = get_site_config()
    purge_days = config.volunteer_purge_days

    if request.method == "POST":
        action = request.POST.get("action", "select")

        if action == "select":
            raw_ids = request.POST.getlist("volunteer_ids")
            try:
                selected_ids = [int(i) for i in raw_ids if i]
            except ValueError:
                messages.error(request, "Invalid volunteer selection.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            if not selected_ids:
                messages.warning(request, "No volunteers selected.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            candidates = list(
                Volunteer.objects.purge_candidates(purge_days)
                .filter(pk__in=selected_ids, user__last_login__isnull=True)
                .select_related("member", "user")
                .annotate(
                    rota_count=Count("rota_entries", distinct=True),
                    gasp_count=Count("last_gasp_emails", distinct=True),
                )
                .order_by("member__name")
            )
            if not candidates:
                messages.warning(request, "None of the selected volunteers are eligible for deletion.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            to_delete = [v for v in candidates if v.rota_count == 0 and v.gasp_count == 0]
            to_anonymise = [v for v in candidates if v.rota_count > 0 or v.gasp_count > 0]

            return render(
                request,
                "bulk_delete_never_onboarded_confirm.html",
                {
                    "to_delete": to_delete,
                    "to_anonymise": to_anonymise,
                    "delete_count": len(to_delete),
                    "anonymise_count": len(to_anonymise),
                    "expected_phrase": f"delete {len(to_delete)} volunteers",
                },
            )

        elif action == "confirm":
            raw_ids = request.POST.getlist("volunteer_ids")
            try:
                selected_ids = [int(i) for i in raw_ids if i]
            except ValueError:
                messages.error(request, "Invalid volunteer selection.")
                return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

            candidates = list(
                Volunteer.objects.purge_candidates(purge_days)
                .filter(pk__in=selected_ids, user__last_login__isnull=True)
                .select_related("member", "user")
                .annotate(
                    rota_count=Count("rota_entries", distinct=True),
                    gasp_count=Count("last_gasp_emails", distinct=True),
                )
            )
            to_delete = [v for v in candidates if v.rota_count == 0 and v.gasp_count == 0]
            to_anonymise = [v for v in candidates if v.rota_count > 0 or v.gasp_count > 0]

            expected_phrase = f"delete {len(to_delete)} volunteers"
            confirm_text = request.POST.get("confirm_phrase", "").strip()

            if confirm_text != expected_phrase:
                messages.error(
                    request,
                    f'Confirmation phrase did not match — type exactly: "{expected_phrase}"',
                )
                return render(
                    request,
                    "bulk_delete_never_onboarded_confirm.html",
                    {
                        "to_delete": to_delete,
                        "to_anonymise": to_anonymise,
                        "delete_count": len(to_delete),
                        "anonymise_count": len(to_anonymise),
                        "expected_phrase": expected_phrase,
                    },
                )

            deleted = 0
            anonymised = 0
            with transaction.atomic():
                for vol in to_delete:
                    logger.info(
                        "Volunteer pk=%s (never logged in, 0 rota entries) hard-deleted by %s",
                        vol.pk,
                        request.user.username,
                    )
                    if vol.portrait:
                        vol.portrait.delete(save=False)
                    member = vol.member
                    user = vol.user
                    # Delete Volunteer first (cascades EventMark etc.), then Member and User
                    vol.delete()
                    member.delete()
                    user.delete()
                    deleted += 1

                for vol in to_anonymise:
                    rota_count = vol.anonymise(performed_by=request.user)
                    logger.info(
                        "Volunteer pk=%s fell back to anonymise (had %d rota entries) by %s",
                        vol.pk,
                        rota_count,
                        request.user.username,
                    )
                    anonymised += 1

            parts = []
            if deleted:
                parts.append(f"Deleted {deleted} volunteer record{'s' if deleted != 1 else ''}")
            if anonymised:
                parts.append(f"anonymised {anonymised} (had rota history or a last-gasp email on record, so anonymised instead)")
            messages.success(request, ". ".join(parts).capitalize() + ".")
            return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    return HttpResponseRedirect(reverse("view-volunteer-pool-health"))


@panopticon_required
@require_POST
def admin_restore_volunteer(request, volunteer_id):
    """One-click restore-to-active from the pool health page (Panopticon only)."""
    volunteer = get_object_or_404(
        Volunteer.objects.select_related("member", "user"),
        pk=volunteer_id,
    )
    if volunteer.status not in (Volunteer.STATUS_DORMANT, Volunteer.STATUS_RETIRED):
        messages.warning(request, f"{volunteer.member.name} is not dormant or retired — no change made.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    volunteer.status = Volunteer.STATUS_ACTIVE
    volunteer.save()
    # Stamp last_login so auto-dormancy doesn't immediately re-dormant this account.
    # The restore is itself a form of re-engagement; treating it as a login is accurate enough.
    volunteer.user.last_login = timezone.now()
    volunteer.user.save(update_fields=["last_login"])
    _notify_vols_admin_status_change(request, volunteer, now_active=True)
    messages.success(request, f"{volunteer.member.name} restored to Active.")
    return HttpResponseRedirect(reverse("view-volunteer-pool-health"))


@panopticon_required
@require_safe
def auto_dormancy_preview(request):
    """Preview which active volunteers would be marked Dormant by auto-dormancy."""
    config = get_site_config()
    dormancy_days = config.volunteer_dormancy_days
    grace_days = config.volunteer_never_logged_in_grace_days
    now = timezone.now()

    active = Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE).select_related("member", "user")

    inactive = Volunteer.objects.none()
    if dormancy_days:
        inactive = active.filter(
            user__last_login__lt=now - timedelta(days=dormancy_days)
        )

    never_logged_in = Volunteer.objects.none()
    if grace_days:
        never_logged_in = active.filter(
            user__last_login__isnull=True,
            user__date_joined__lt=now - timedelta(days=grace_days),
        )

    return render(request, "auto_dormancy_preview.html", {
        "inactive": list(inactive),
        "never_logged_in": list(never_logged_in),
        "total": inactive.count() + never_logged_in.count(),
        "dormancy_days": dormancy_days,
        "grace_days": grace_days,
        "disabled": not dormancy_days and not grace_days,
    })


@panopticon_required
@require_POST
def auto_dormancy_apply(request):
    """Apply auto-dormancy: mark qualifying active volunteers as Dormant."""
    config = get_site_config()
    dormancy_days = config.volunteer_dormancy_days
    grace_days = config.volunteer_never_logged_in_grace_days
    now = timezone.now()

    if not dormancy_days and not grace_days:
        messages.warning(request, "Auto-dormancy is disabled — no thresholds configured.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    active = Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE)
    count = 0
    if dormancy_days:
        count += active.filter(
            user__last_login__lt=now - timedelta(days=dormancy_days)
        ).update(status=Volunteer.STATUS_DORMANT)
    if grace_days:
        count += active.filter(
            user__last_login__isnull=True,
            user__date_joined__lt=now - timedelta(days=grace_days),
        ).update(status=Volunteer.STATUS_DORMANT)

    messages.success(request, f"Marked {count} volunteer{'s' if count != 1 else ''} as Dormant.")
    return HttpResponseRedirect(reverse("view-volunteer-pool-health"))


@panopticon_required
def last_gasp_email(request, volunteer_id):
    """Preview and send a last-gasp re-engagement email to a purge candidate."""
    config = get_site_config()
    volunteer = get_object_or_404(
        Volunteer.objects.select_related("member", "user"),
        pk=volunteer_id,
    )

    subject_template = config.last_gasp_email_subject or "Are you still with us at {venue}?"
    body_template = config.last_gasp_email_body
    cooldown_days = config.last_gasp_cooldown_days

    if not config.last_gasp_email_enabled:
        messages.warning(request, "Last-gasp email is not enabled. Turn it on in Site settings.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    name = volunteer.member.name
    venue = settings.VENUE.get("longname", settings.VENUE.get("name", "the venue"))
    subject = subject_template.replace("{name}", name).replace("{venue}", venue)
    body = body_template.replace("{name}", name).replace("{venue}", venue)

    # Check cooldown
    cooldown_cutoff = timezone.now() - timedelta(days=cooldown_days)
    recent_log = (
        LastGaspEmailLog.objects
        .filter(volunteer=volunteer, sent_at__gt=cooldown_cutoff)
        .order_by("-sent_at")
        .first()
    )

    if request.method == "POST":
        if recent_log:
            messages.warning(
                request,
                f"A last-gasp email was sent to {name} {(timezone.now() - recent_log.sent_at).days} day(s) ago — cooldown not yet elapsed.",
            )
            return HttpResponseRedirect(reverse("view-volunteer-pool-health"))
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [volunteer.member.email])
        LastGaspEmailLog.objects.create(volunteer=volunteer, sent_by=request.user)
        messages.success(request, f"Last-gasp email sent to {name} ({volunteer.member.email}).")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    return render(request, "last_gasp_email_preview.html", {
        "volunteer": volunteer,
        "member": volunteer.member,
        "subject": subject,
        "body": body,
        "recent_log": recent_log,
        "cooldown_days": cooldown_days,
    })


@panopticon_required
def bulk_last_gasp_email(request):
    """Two-step bulk last-gasp email for pool-health candidates.

    Step 1 (POST from pool-health, action=compose): receive selected volunteer
    IDs, pre-populate subject and body from Site Settings, show a compose/preview
    page. Recipients already within the cooldown window are flagged but still
    listed -- the panopticon can see them and the send step skips them.

    Step 2 (POST from compose page, action=send): send one email per eligible
    recipient, create LastGaspEmailLog rows, report counts and redirect.
    """
    config = get_site_config()
    cooldown_days = config.last_gasp_cooldown_days
    default_subject = config.last_gasp_email_subject or "Are you still with us at {venue}?"
    default_body = config.last_gasp_email_body

    venue = settings.VENUE.get("longname", settings.VENUE.get("name", "the venue"))

    if not config.last_gasp_email_enabled:
        messages.warning(request, "Last-gasp email is not enabled. Turn it on in Site settings.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    if request.method != "POST":
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    # Other forms on pool-health use action="select"; treat anything other than
    # the explicit send confirmation as the compose step.
    action = "send" if request.POST.get("action") == "send" else "compose"

    raw_ids = request.POST.getlist("volunteer_ids")
    try:
        selected_ids = [int(i) for i in raw_ids if i]
    except ValueError:
        messages.error(request, "Invalid volunteer selection.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    if not selected_ids:
        messages.warning(request, "No volunteers selected.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    volunteers = list(
        Volunteer.objects.filter(pk__in=selected_ids)
        .select_related("member", "user")
        .order_by("member__name")
    )
    if not volunteers:
        messages.warning(request, "None of the selected volunteers were found.")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    cooldown_cutoff = timezone.now() - timedelta(days=cooldown_days)

    if action == "compose":
        # Annotate each volunteer with their most recent last-gasp log (if any).
        # Build a dict keyed by volunteer_id, keeping only the most recent log
        # per volunteer (ordered by sent_at desc, so first seen wins).
        _recent_logs_qs = LastGaspEmailLog.objects.filter(
            volunteer__in=volunteers,
            sent_at__gt=cooldown_cutoff,
        ).order_by("-sent_at")
        recent_logs = {}
        for log in _recent_logs_qs:
            recent_logs.setdefault(log.volunteer_id, log)
        recipients = [
            {
                "volunteer": v,
                "recent_log": recent_logs.get(v.pk),
                "in_cooldown": v.pk in recent_logs,
            }
            for v in volunteers
        ]
        ready_count = sum(1 for r in recipients if not r["in_cooldown"])

        return render(request, "bulk_last_gasp_email.html", {
            "recipients": recipients,
            "ready_count": ready_count,
            "cooldown_count": len(recipients) - ready_count,
            "volunteer_ids": selected_ids,
            "default_subject": default_subject,
            "default_body": default_body,
            "cooldown_days": cooldown_days,
            "venue": venue,
        })

    elif action == "send":
        subject_template = request.POST.get("subject", default_subject).strip() or default_subject
        body_template = request.POST.get("body", default_body).strip() or default_body

        if not body_template:
            messages.error(request, "Email body cannot be empty.")
            return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

        sent = 0
        skipped = 0
        for vol in volunteers:
            in_cooldown = LastGaspEmailLog.objects.filter(
                volunteer=vol, sent_at__gt=cooldown_cutoff
            ).exists()
            if in_cooldown:
                skipped += 1
                continue
            name = vol.member.name
            subject = subject_template.replace("{name}", name).replace("{venue}", venue)
            body = body_template.replace("{name}", name).replace("{venue}", venue)
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [vol.member.email])
            LastGaspEmailLog.objects.create(volunteer=vol, sent_by=request.user)
            logger.info(
                "Bulk last-gasp email sent to volunteer pk=%s (%s) by %s",
                vol.pk, vol.member.email, request.user.username,
            )
            sent += 1

        parts = [f"Last-gasp email sent to {sent} volunteer{'s' if sent != 1 else ''}"]
        if skipped:
            parts.append(f"{skipped} skipped (still within {cooldown_days}-day cooldown)")
        messages.success(request, ". ".join(parts) + ".")
        return HttpResponseRedirect(reverse("view-volunteer-pool-health"))

    return HttpResponseRedirect(reverse("view-volunteer-pool-health"))


@panopticon_required
@require_safe
def view_volunteer_role_report(request):
    # Role assignment was removed; redirect to the qualification report which replaced it.
    return HttpResponseRedirect(reverse("view-qualification-report"))


def _notify_vols_admin_status_change(request, vol, now_active):
    # Volunteer status (active / dormant / retired) is edited on the volunteer's
    # own profile page. When that change moves a volunteer on or off the active
    # roster, email the volunteers admin so the mailing list can be kept in step.
    # No-op when no vols_admin_address is configured.
    vols_admin = settings.VENUE.get("vols_admin_address") or []
    if not vols_admin:
        return

    status_label = vol.get_status_display()
    if now_active:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please add them back to the volunteers mailing list "
            f"at your earliest convenience."
        )
    else:
        action_line = (
            f"to {status_label}.\n\n"
            f"Please remove them from the volunteers mailing list "
            f"at your earliest convenience."
        )
    admin_body = (
        f"{request.user.last_name} has updated the status of volunteer\n\n"
        f"{vol.member.name} <{vol.member.email}>\n\n"
        f"{action_line}"
    )
    send_mail(
        f"[{settings.VENUE['longname']}] Change in volunteer status {vol.member.name}",
        admin_body,
        settings.VENUE["mailout_from_address"],
        vols_admin,
        fail_silently=False,
    )


@login_required
def edit_volunteer(request, volunteer_id, create_new=False):
    # If called from the "add" url, then create_new will be True. If called
    # from the edit url then it'll be False

    is_panopticon = request.user.is_superuser

    # Depending on which way this method was called, either create a totally
    # new volunteer object with default values (add) or load the volunteer
    # object with the given volunteer_id from the database:
    if not create_new:
        # Called from "edit" url
        volunteer = get_object_or_404(Volunteer, id=volunteer_id)
        # Panopticons can edit anyone; volunteers can only edit their own record.
        if not is_panopticon and volunteer.user != request.user:
            raise PermissionDenied
        member = volunteer.member
        user = volunteer.user
        new_training_record = TrainingRecord(volunteer=volunteer)
        # Remember whether they were on the active roster, so we can notify the
        # volunteers admin if this edit moves them on or off it (see below).
        was_active = volunteer.is_active
        # Remember suspension state so we can flag the safeguarding side-effects
        # (login disabled, shifts cleared) to the operator after saving.
        was_suspended = volunteer.status == Volunteer.STATUS_SUSPENDED
    else:
        # Called from "add" url — Panopticon only
        if not is_panopticon:
            raise PermissionDenied
        volunteer = Volunteer()
        member = Member()
        volunteer.member = Member()
        new_training_record = None
        user = None

    # Now, if the view was loaded with "GET" then display the edit form, and
    # if it was called with POST then read the updated volunteer data from the
    # form data and update and save the volunteer object:
    if request.method == "POST":
        # Three forms, one for each set of data
        vol_form = VolunteerForm(
            request.POST, request.FILES, instance=volunteer,
            is_superuser=request.user.is_superuser,
        )
        mem_form = MemberFormWithoutNotes(request.POST, instance=member)
        forms_valid = vol_form.is_valid() and mem_form.is_valid()
        if forms_valid:
            member = mem_form.save(commit=False)
            member.gdpr_opt_in = timezone.now()
            member.save()
            volunteer.member = member

            if create_new:
                # Auto-create an inactive Django user account for the new
                # volunteer. Derive a unique username from the member's name.
                base = slugify(member.name)[:40] or "volunteer"
                username = base
                n = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base}-{n}"
                    n += 1
                user = User(
                    username=username,
                    email=member.email or "",
                    first_name=member.name.split()[0] if member.name else "",
                    last_name=" ".join(member.name.split()[1:]) if member.name else "",
                )
                user.set_unusable_password()
                user.save()
                volunteer.user = user

            vol_form.save()

            if not create_new and volunteer.is_active != was_active:
                logger.info(
                    f"{request.user.last_name} set status to {volunteer.status} "
                    f"for volunteer {volunteer.member.name}"
                )
                _notify_vols_admin_status_change(
                    request, volunteer, volunteer.is_active
                )

            now_suspended = volunteer.status == Volunteer.STATUS_SUSPENDED
            if not create_new and now_suspended and not was_suspended:
                messages.add_message(
                    request,
                    messages.WARNING,
                    f"{member.name} has been suspended — their login is now "
                    f"disabled and they have been removed from all upcoming shifts.",
                )
            elif not create_new and was_suspended and not now_suspended:
                messages.add_message(
                    request,
                    messages.INFO,
                    f"{member.name}'s suspension has been lifted — their login is "
                    f"restored and they are back on the rota. Any shifts they were "
                    f"removed from were not added back automatically.",
                )

            logger.info(
                f"Saving changes to volunteer '{volunteer.member.name}' (id: {str(volunteer.pk)})"
            )

            messages.add_message(
                request,
                messages.SUCCESS,
                f"{'Created' if create_new else 'Updated'} volunteer '{member.name}'",
            )

            if create_new:
                # Send the new volunteer a welcome email with a password-set link.
                # They use it to choose their own password before first login.
                if user.email:
                    _send_password_set_email(request, user, welcome=True)
                    logger.info(
                        "Welcome email sent to new volunteer pk=%s", volunteer.pk
                    )

                # Email admin (only if vols_admin_address is configured)
                vols_admin = settings.VENUE.get("vols_admin_address") or []
                if vols_admin:
                    admin_body = (
                        f"I'm delighted to inform you that {request.user.last_name} has just added "
                        f"new volunteer\n\n"
                        f"{volunteer.member.name} <{volunteer.member.email}>\n\n"
                        f"to the toolkit.\n\n"
                        f"Please add them to the volunteers mailing list "
                        f"at your earliest convenience."
                    )
                    send_mail(
                        (
                            f"[{settings.VENUE['longname']}] New volunteer {volunteer.member.name}"
                        ),
                        admin_body,
                        settings.VENUE["mailout_from_address"],
                        vols_admin,
                        fail_silently=False,
                    )
            # After a new suspension, stay on the edit page with email preview.
            if not create_new and now_suspended and not was_suspended:
                request.session[f"suspension_email_pending_{volunteer.pk}"] = True
                return HttpResponseRedirect(
                    reverse("edit-volunteer", kwargs={"volunteer_id": volunteer.pk})
                    + "#suspension-email-preview"
                )
            # Go to the volunteer list view (summary for panopticon, list for others):
            if request.user.is_superuser:
                return HttpResponseRedirect(reverse("view-volunteer-summary"))
            return HttpResponseRedirect(reverse("view-volunteer-list"))
    else:
        vol_form = VolunteerForm(instance=volunteer, is_superuser=request.user.is_superuser)
        mem_form = MemberFormWithoutNotes(instance=volunteer.member)

    show_user_mgmt = settings.VENUE.get("show_user_management") and user is not None and request.user.is_superuser
    user_form = UserForm(instance=user) if show_user_mgmt else None

    if new_training_record:
        training_record_form = TrainingRecordForm(
            prefix="training", instance=new_training_record
        )
    else:
        training_record_form = None

    from toolkit.members.models import Qualification
    site_config = get_site_config()

    suspension_email_preview = None
    session_key = f"suspension_email_pending_{volunteer.pk}"
    if not create_new and (
        request.session.get(session_key)
        or request.GET.get("suspension_email_pending") == "1"
    ) and volunteer.status == Volunteer.STATUS_SUSPENDED:
        venue_name = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
        vol_name = volunteer.member.name or ""
        suspension_email_preview = {
            "to": volunteer.member.email or "",
            "subject": site_config.suspension_email_subject.replace(
                "{name}", vol_name
            ).replace("{venue}", venue_name),
            "body": site_config.suspension_email_body.replace(
                "{name}", vol_name
            ).replace("{venue}", venue_name),
        }
        request.session[session_key] = True

    context = {
        "pagetitle": "Add Volunteer" if create_new else "Edit Volunteer",
        "default_mugshot": settings.DEFAULT_MUGSHOT,
        "volunteer": volunteer,
        "user_form": user_form,
        "vol_form": vol_form,
        "mem_form": mem_form,
        "training_record_form": training_record_form,
        "dawn_of_toolkit": settings.DAWN_OF_TOOLKIT,
        "site_config": site_config,
        "general_training_enabled": site_config.general_training_enabled,
        "all_qualifications": Qualification.objects.all(),
        "is_panopticon": is_panopticon,
        "suspension_email_preview": suspension_email_preview,
    }
    return render(request, "form_volunteer.html", context)


@panopticon_required
@require_POST
def add_volunteer_training_record(request, volunteer_id):
    volunteer = get_object_or_404(Volunteer, id=volunteer_id)
    new_record = TrainingRecord(volunteer=volunteer)

    record_form = TrainingRecordForm(
        request.POST,
        instance=new_record,
        prefix="training",
    )

    if not volunteer.is_active:
        response = {"succeeded": False, "errors": "volunteer is not active"}
        return JsonResponse(response)
    elif record_form.is_valid():
        record_form.save()
        logger.info(
            f"Added training record {new_record.id} for volunteer '{volunteer.member.name}'"
        )

        if new_record.training_type == TrainingRecord.ROLE_TRAINING:
            training_description = str(new_record.role)
        else:
            training_description = new_record.GENERAL_TRAINING_DESC

        response = {
            "succeeded": True,
            "id": new_record.id,
            "training_description": training_description,
            "training_date": new_record.training_date.strftime("%d/%m/%Y"),
            "trainer": new_record.trainer,
            "notes": new_record.notes,
        }
        return JsonResponse(response)
    else:
        response = {"succeeded": False, "errors": record_form.errors}
        return JsonResponse(response)


@panopticon_required
@require_POST
def delete_volunteer_training_record(request, training_record_id):
    record = get_object_or_404(TrainingRecord, id=training_record_id)

    if not record.volunteer.is_active:
        logger.error("Tried to delete training record for inactive volunteer")
        return HttpResponse(
            "Can't delete record for inactive volunteer",
            status=403,
            content_type="text/plain",
        )

    logger.info(
        f"Deleting training_record '{record.id}' for volunteer '{record.volunteer.member.name}'"
    )
    record.delete()
    return HttpResponse("OK", content_type="text/plain")


@panopticon_required
@require_safe
def view_volunteer_training_records(request):
    # Two sets of data, the complicated one (training records) and the simpler
    # one (all active volunteers, for the 'general' dates.)
    records = (
        TrainingRecord.objects.filter(
            volunteer__status=Volunteer.STATUS_ACTIVE,
            training_type=TrainingRecord.ROLE_TRAINING,
        )
        .select_related()
        .prefetch_related("role")
    )
    role_map = {}
    for record in records:
        vol_map = role_map.setdefault(record.role, {})
        current = vol_map.get(record.volunteer, None)
        if not current or record.training_date > current.training_date:
            vol_map[record.volunteer] = record
    # Now sort by role ID / volunteer Name, using an obnoxiously complicated
    # comprehension (sorry):
    role_map_list = sorted(
        # List of (role, [(volunteer, record), (volunteer, record), ...])
        # tuples, with the list of (vol, rec) tuples sorted by
        # volunteer.member.name:
        [
            (
                role,
                sorted(
                    [(vol, record) for vol, record in vol_map.items()],
                    key=lambda v_r: v_r[0].member.name.lower(),
                ),
            )
            for role, vol_map in role_map.items()
        ],
        # ...and sort the [ (role, [(vol, rec), ...]), ...] list by role name:
        key=lambda r_l: r_l[0].name.lower(),
    )

    gst_enabled = get_site_config().general_training_enabled

    # Second data set - all active volunteers with GST records (only when GST is enabled).
    volunteers = Volunteer.objects.active().order_by("member__name").select_related()
    if gst_enabled:
        qs = TrainingRecord.objects.filter(
            training_type=TrainingRecord.GENERAL_TRAINING
        ).order_by("-training_date")
        volunteers = volunteers.prefetch_related(
            Prefetch("training_records", queryset=qs, to_attr="general_training")
        )

    context = {
        "report_data": role_map_list,
        "volunteers": volunteers,
        "general_training_enabled": gst_enabled,
    }
    return render(request, "volunteer_training_report.html", context)


@panopticon_required
def add_volunteer_training_group_record(request):
    if request.method == "POST":
        form = GroupTrainingForm(request.POST)
        if form.is_valid():
            training_type = form.cleaned_data["type"]
            role = form.cleaned_data["role"]
            trainer = form.cleaned_data["trainer"]
            members = form.cleaned_data["volunteers"]
            logger.info(
                f"Bulk add training records, type {training_type}, role '{role}', trainer '{trainer}', "
                f" members '{members}'"
            )

            for member in members:
                volunteer = member.volunteer
                record = TrainingRecord(
                    training_type=training_type,
                    role=role,
                    trainer=trainer,
                    training_date=form.cleaned_data["training_date"],
                    notes=form.cleaned_data["notes"],
                    volunteer=volunteer,
                )
                record.save()

            if training_type == TrainingRecord.ROLE_TRAINING:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Added {len(form.cleaned_data['volunteers'])} training records for {form.cleaned_data['role']}",
                )
            elif training_type == TrainingRecord.GENERAL_TRAINING:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f"Added {len(form.cleaned_data['volunteers'])} {TrainingRecord.GENERAL_TRAINING_DESC} records",
                )
            return HttpResponseRedirect(
                reverse("add-volunteer-training-group-record")
            )
    else:  # i.e. request.method == 'GET':
        form = GroupTrainingForm()

    context = {
        "form": form,
    }
    return render(request, "form_group_training.html", context)


def anonymise_volunteer(request, volunteer_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    member = volunteer.member
    volunteer_name = member.name

    # FK-linked entries are authoritative; text-match catches legacy entries
    # where the FK was never set (pre-migration rota history).
    fk_matches = RotaEntry.objects.filter(volunteer=volunteer)
    name_matches = RotaEntry.objects.filter(
        name__iexact=volunteer_name, volunteer__isnull=True
    )
    rota_match_count = fk_matches.count() + name_matches.count()
    rota_sample = list(
        fk_matches.select_related("showing__event")[:5]
    ) or list(
        name_matches.select_related("showing__event")[:5]
    )

    if request.method == "POST":
        confirm_name = request.POST.get("confirm_name", "").strip()
        if confirm_name != volunteer_name:
            messages.error(
                request,
                "Name did not match — no changes were made.",
            )
            return HttpResponseRedirect(
                reverse("anonymise-volunteer", kwargs={"volunteer_id": volunteer_id})
            )

        rota_match_count = volunteer.anonymise(performed_by=request.user)

        logger.info(
            f"Volunteer pk={volunteer.pk} anonymised by {request.user.username}"
        )
        messages.success(
            request,
            f"Volunteer record anonymised. {rota_match_count} rota "
            f"{'entry' if rota_match_count == 1 else 'entries'} cleared.",
        )
        return HttpResponseRedirect(reverse("search-members"))

    today = timezone.now().date()
    has_active_membership = (
        member.membership_expires is not None
        and member.membership_expires >= today
    )

    return render(
        request,
        "anonymise_volunteer.html",
        {
            "volunteer": volunteer,
            "member": member,
            "rota_match_count": rota_match_count,
            "rota_sample": rota_sample,
            "has_active_membership": has_active_membership,
        },
    )


@require_POST
def set_volunteer_password(request, volunteer_id):
    """Set a volunteer's password directly (Panopticon only)."""
    if not request.user.is_superuser:
        raise PermissionDenied

    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    user = volunteer.user
    if user is None:
        messages.error(request, "This volunteer has no linked user account.")
        return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))

    form = SetPasswordForm(user, request.POST)
    if form.is_valid():
        form.save()
        logger.info(
            "Password set for volunteer pk=%s by %s", volunteer_id, request.user.username
        )
        messages.success(request, f"Password updated for {volunteer.member.name}.")
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))


def _send_password_set_email(request, user, welcome=False):
    """Send a password-set link to a volunteer user.

    welcome=True sends a first-time welcome message; False sends the
    standard "password reset requested" message used for manual resets.
    The link uses Django's password-reset token mechanism and is valid
    for PASSWORD_RESET_TIMEOUT seconds (default 3 days).
    """
    token = default_token_generator.make_token(user)
    uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = request.build_absolute_uri(
        reverse("password_reset_confirm", kwargs={"uidb64": uid_b64, "token": token})
    )
    timeout_days = max(1, getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200) // 86400)
    validity = f"{timeout_days} day" if timeout_days == 1 else f"{timeout_days} days"

    name = user.first_name or user.username
    venue = settings.VENUE["longname"]
    from_email = settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL

    if welcome:
        subject = f"[{venue}] Welcome — set your toolkit password"
        message = (
            f"Hi {name},\n\n"
            f"You've been added as a volunteer at {venue}.\n\n"
            f"Click the link below to set your password and log in to the toolkit "
            f"(valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this email, you can ignore it — no account "
            f"will be activated unless you follow the link."
        )
    else:
        subject = f"[{venue}] Set your toolkit password"
        message = (
            f"Hi {name},\n\n"
            f"A password reset has been requested for your toolkit account.\n\n"
            f"Click the link below to set a new password (valid for {validity}):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this, you can ignore this email."
        )

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_volunteer_password_reset(request, volunteer_id):
    """Send a password reset email to a volunteer (Panopticon only)."""
    if not request.user.is_superuser:
        raise PermissionDenied

    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    user = volunteer.user
    if user is None or not user.email:
        messages.error(request, "This volunteer has no linked user account or no email address.")
        return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))

    _send_password_set_email(request, user, welcome=False)
    logger.info(
        "Password reset email sent to volunteer pk=%s by %s", volunteer_id, request.user.username
    )
    messages.success(request, f"Password reset email sent to {user.email}.")
    return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))


@login_required
@require_safe
def view_volunteer_directory(request):
    query = request.GET.get("q", "").strip()

    volunteers = (
        Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE)
        .filter(dir_share_listed=True)
        .select_related("member")
        .prefetch_related("collectives")
        .order_by("member__name")
    )

    if query:
        volunteers = volunteers.filter(member__name__icontains=query)

    try:
        own_volunteer_pk = request.user.volunteer.pk
    except Volunteer.DoesNotExist:
        own_volunteer_pk = None

    return render(
        request,
        "volunteer_directory.html",
        {"volunteers": volunteers, "query": query, "own_volunteer_pk": own_volunteer_pk},
    )


@require_POST
@login_required
def reactivate_self(request):
    """Let a dormant volunteer put themselves back on the active roster in one click.

    Triggered from the welcome-back dashboard card. Only acts on the requesting
    user's own record, and only when they are currently Dormant — so it can't be
    used to climb out of a Retired or Suspended state, which are deliberate
    admin/safeguarding decisions.
    """
    try:
        volunteer = request.user.volunteer
    except Exception:
        return HttpResponseRedirect(reverse("toolkit-index"))

    if volunteer.status == Volunteer.STATUS_DORMANT:
        volunteer.status = Volunteer.STATUS_ACTIVE
        volunteer.save(update_fields=["status"])
        logger.info("Volunteer pk=%s reactivated themselves from dormant", volunteer.pk)
        _notify_vols_admin_status_change(request, volunteer, now_active=True)
        messages.success(
            request,
            "Welcome back! You're active again and back on the volunteer roster.",
        )
    return HttpResponseRedirect(reverse("toolkit-index"))


@require_safe
def volunteer_digest_unsubscribe(request):
    """One-click unsubscribe from the weekly volunteer digest. No login required.

    Token format: <pk>:<hmac> — the pk is in the query string as the first
    segment so we can look up the volunteer before verifying the signature.
    """
    raw = request.GET.get("token", "")
    try:
        pk_str, token = raw.split(":", 1)
        pk = int(pk_str)
    except (ValueError, AttributeError):
        return render(request, "volunteer_digest_unsubscribe.html", {"error": True})

    signer = Signer(salt="volunteer-digest-unsubscribe")
    try:
        signer.unsign(f"{pk}:{token}")
    except BadSignature:
        return render(request, "volunteer_digest_unsubscribe.html", {"error": True})

    volunteer = get_object_or_404(Volunteer, pk=pk)
    volunteer.weekly_digest = False
    volunteer.save(update_fields=["weekly_digest"])

    return render(request, "volunteer_digest_unsubscribe.html", {"success": True})


@panopticon_required
def bulk_award_qualification(request):
    from toolkit.members.models import Qualification, VolunteerQualification

    all_qualifications = Qualification.objects.order_by("name")

    # Resolve the selected qualification (if any) from GET or POST
    qual_id = request.POST.get("qualification_id") or request.GET.get("qualification_id")
    selected_qual = None
    if qual_id:
        try:
            selected_qual = Qualification.objects.get(pk=qual_id)
        except Qualification.DoesNotExist:
            messages.error(request, "Qualification not found.")

    if request.method == "POST" and selected_qual:
        raw_ids = request.POST.getlist("volunteer_ids")
        try:
            selected_ids = [int(i) for i in raw_ids if i]
        except ValueError:
            messages.error(request, "Invalid volunteer selection.")
            return HttpResponseRedirect(reverse("bulk-award-qualification"))

        if not selected_ids:
            messages.warning(request, "No volunteers selected.")
        else:
            existing = set(
                VolunteerQualification.objects.filter(
                    volunteer_id__in=selected_ids,
                    qualification=selected_qual,
                ).values_list("volunteer_id", flat=True)
            )
            to_create = [vid for vid in selected_ids if vid not in existing]
            granted_by = request.user.get_full_name() or request.user.username
            VolunteerQualification.objects.bulk_create([
                VolunteerQualification(
                    volunteer_id=vid,
                    qualification=selected_qual,
                    granted_by=granted_by,
                )
                for vid in to_create
            ])
            skipped = len(selected_ids) - len(to_create)
            msg = f"'{selected_qual.name}' awarded to {len(to_create)} volunteer(s)."
            if skipped:
                msg += f" {skipped} already held it and were skipped."
            messages.success(request, msg)
            logger.info(
                "Bulk award: '%s' granted to %d volunteers by %s (%d skipped)",
                selected_qual.name, len(to_create), request.user.username, skipped,
            )
        return HttpResponseRedirect(
            reverse("bulk-award-qualification") + f"?qualification_id={selected_qual.pk}"
        )

    # Build volunteer list — active only, with their current qualifications prefetched
    volunteers = (
        Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE)
        .select_related("member")
        .prefetch_related("qualifications__qualification")
        .order_by("member__name")
    )

    # Annotate each volunteer with whether they already hold the selected qual
    if selected_qual:
        holders = set(
            VolunteerQualification.objects.filter(
                qualification=selected_qual
            ).values_list("volunteer_id", flat=True)
        )
        for vol in volunteers:
            vol.already_holds = vol.pk in holders
    else:
        for vol in volunteers:
            vol.already_holds = False

    hide_holders = request.GET.get("hide-holders") is not None and selected_qual is not None

    context = {
        "all_qualifications": all_qualifications,
        "selected_qual": selected_qual,
        "volunteers": volunteers,
        "hide_holders": hide_holders,
    }
    return render(request, "bulk_award_qualification.html", context)


@panopticon_required
@require_POST
def add_volunteer_qualification(request, volunteer_id):
    from toolkit.members.models import Qualification, VolunteerQualification
    volunteer = get_object_or_404(Volunteer, id=volunteer_id)
    qual_id = request.POST.get("qualification_id")
    granted_by = request.POST.get("granted_by", "").strip()
    try:
        qualification = Qualification.objects.get(pk=qual_id)
    except Qualification.DoesNotExist:
        messages.error(request, "Qualification not found.")
        return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))
    _, created = VolunteerQualification.objects.get_or_create(
        volunteer=volunteer,
        qualification=qualification,
        defaults={"granted_by": granted_by},
    )
    if created:
        messages.success(request, f"'{qualification.name}' qualification recorded for {volunteer.member.name}.")
    else:
        messages.warning(request, f"{volunteer.member.name} already holds the '{qualification.name}' qualification.")
    return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}) + "#vol-qualifications")


@panopticon_required
@require_POST
def remove_volunteer_qualification(request, vq_id):
    from toolkit.members.models import VolunteerQualification
    vq = get_object_or_404(VolunteerQualification, pk=vq_id)
    volunteer_id = vq.volunteer_id
    qual_name = vq.qualification.name
    vol_name = vq.volunteer.member.name
    vq.delete()
    messages.success(request, f"'{qual_name}' qualification removed from {vol_name}.")
    return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}) + "#vol-qualifications")


@panopticon_required
@require_safe
def view_qualification_report(request):
    from toolkit.members.models import Qualification, VolunteerQualification

    qualifications = Qualification.objects.order_by("name")
    qual_data = []
    for qual in qualifications:
        holders = (
            VolunteerQualification.objects
            .filter(qualification=qual)
            .select_related("volunteer__member")
            .order_by("volunteer__member__name")
        )
        gating_roles = Role.objects.filter(
            required_qualification=qual,
            qualification_gate__in=[Role.GATE_ADVISORY, Role.GATE_BLOCKING],
        ).order_by("name")
        qual_data.append({
            "qualification": qual,
            "holders": list(holders),
            "gating_roles": list(gating_roles),
        })

    return render(request, "volunteer_qualification_report.html", {"qual_data": qual_data})


@panopticon_required
def bulk_record(request):
    """Unified bulk-record page: training records and qualification grants, with a type selector."""
    from toolkit.members.models import Qualification, VolunteerQualification

    mode = request.POST.get("mode") or request.GET.get("mode", "training")
    if mode not in ("training", "qualification"):
        mode = "training"

    if mode == "training":
        return _bulk_record_training(request)
    else:
        return _bulk_record_qualification(request)


def _bulk_record_training(request):
    if request.method == "POST":
        form = GroupTrainingForm(request.POST)
        if form.is_valid():
            training_type = form.cleaned_data["type"]
            role = form.cleaned_data["role"]
            trainer = form.cleaned_data["trainer"]
            members = form.cleaned_data["volunteers"]
            logger.info(
                f"Bulk add training records, type {training_type}, role '{role}', trainer '{trainer}', "
                f"members '{members}'"
            )
            for member in members:
                volunteer = member.volunteer
                TrainingRecord(
                    training_type=training_type,
                    role=role,
                    trainer=trainer,
                    training_date=form.cleaned_data["training_date"],
                    notes=form.cleaned_data["notes"],
                    volunteer=volunteer,
                ).save()
            messages.success(
                request,
                f"Added {len(members)} training record(s) for "
                f"{'role ' + str(role) if role else 'general training'}.",
            )
            return HttpResponseRedirect(reverse("bulk-record") + "?mode=training")
    else:
        form = GroupTrainingForm()

    return render(request, "volunteer_bulk_record.html", {"mode": "training", "form": form})


def _bulk_record_qualification(request):
    from toolkit.members.models import Qualification, VolunteerQualification

    all_qualifications = Qualification.objects.order_by("name")
    qual_id = request.POST.get("qualification_id") or request.GET.get("qualification_id")
    selected_qual = None
    if qual_id:
        try:
            selected_qual = Qualification.objects.get(pk=qual_id)
        except Qualification.DoesNotExist:
            messages.error(request, "Qualification not found.")

    if request.method == "POST" and selected_qual:
        raw_ids = request.POST.getlist("volunteer_ids")
        try:
            selected_ids = [int(i) for i in raw_ids if i]
        except ValueError:
            messages.error(request, "Invalid volunteer selection.")
            return HttpResponseRedirect(reverse("bulk-record") + "?mode=qualification")

        if not selected_ids:
            messages.warning(request, "No volunteers selected.")
        else:
            existing = set(
                VolunteerQualification.objects.filter(
                    volunteer_id__in=selected_ids,
                    qualification=selected_qual,
                ).values_list("volunteer_id", flat=True)
            )
            to_create = [vid for vid in selected_ids if vid not in existing]
            granted_by = request.user.get_full_name() or request.user.username
            VolunteerQualification.objects.bulk_create([
                VolunteerQualification(
                    volunteer_id=vid,
                    qualification=selected_qual,
                    granted_by=granted_by,
                )
                for vid in to_create
            ])
            skipped = len(selected_ids) - len(to_create)
            msg = f"'{selected_qual.name}' awarded to {len(to_create)} volunteer(s)."
            if skipped:
                msg += f" {skipped} already held it and were skipped."
            messages.success(request, msg)
            logger.info(
                "Bulk award: '%s' granted to %d volunteers by %s (%d skipped)",
                selected_qual.name, len(to_create), request.user.username, skipped,
            )
        return HttpResponseRedirect(
            reverse("bulk-record") + f"?mode=qualification&qualification_id={selected_qual.pk}"
        )

    # Build volunteer list with already-holds annotation.
    volunteers = (
        Volunteer.objects.filter(status=Volunteer.STATUS_ACTIVE)
        .select_related("member")
        .prefetch_related("qualifications__qualification")
        .order_by("member__name")
    )
    hide_holders = bool(request.GET.get("hide-holders"))
    if selected_qual:
        holders = set(
            VolunteerQualification.objects.filter(
                qualification=selected_qual
            ).values_list("volunteer_id", flat=True)
        )
        for vol in volunteers:
            vol.already_holds = vol.pk in holders
    else:
        for vol in volunteers:
            vol.already_holds = False

    return render(request, "volunteer_bulk_record.html", {
        "mode": "qualification",
        "all_qualifications": all_qualifications,
        "selected_qual": selected_qual,
        "volunteers": volunteers,
        "hide_holders": hide_holders,
    })


@panopticon_required
@require_POST
def save_volunteer_permissions(request, volunteer_id):
    """Update Django user permissions (programmer, panopticon) for a volunteer."""
    volunteer = get_object_or_404(Volunteer, id=volunteer_id)
    user = volunteer.user
    if not settings.VENUE.get("show_user_management") or user is None:
        raise PermissionDenied
    user_form = UserForm(request.POST, instance=user)
    if user_form.is_valid():
        user_form.save(granted_by=request.user)
        logger.info(
            "Permissions updated for volunteer pk=%s by %s",
            volunteer.pk, request.user.username,
        )
        messages.success(request, f"Permissions updated for {volunteer.member.name}.")
    else:
        for field, errors in user_form.errors.items():
            for error in errors:
                messages.error(request, f"Permissions: {error}")
    return HttpResponseRedirect(
        reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
    )


@panopticon_required
@require_POST
def toggle_volunteer_suspension(request, volunteer_id):
    """Suspend or reinstate a volunteer via the dedicated suspension card."""
    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    action = request.POST.get("action")

    if action == "suspend" and volunteer.status != Volunteer.STATUS_SUSPENDED:
        volunteer.status = Volunteer.STATUS_SUSPENDED
        volunteer.suspension_reason = request.POST.get("suspension_reason", "").strip()
        volunteer.save()
        request.session[f"suspension_email_pending_{volunteer.pk}"] = True
        messages.warning(
            request,
            f"{volunteer.member.name} has been suspended — their login is now "
            f"disabled and they have been removed from all upcoming shifts. "
            f"See the suspension email panel below to notify them.",
        )
        logger.info(
            "Volunteer pk=%s suspended by %s", volunteer.pk, request.user.username
        )
        return HttpResponseRedirect(
            reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
            + "#suspension-email-preview"
        )
    elif action == "reinstate" and volunteer.status == Volunteer.STATUS_SUSPENDED:
        volunteer.status = Volunteer.STATUS_ACTIVE
        volunteer.suspension_reason = ""
        volunteer.save()
        messages.info(
            request,
            f"{volunteer.member.name}'s suspension has been lifted — their login is "
            f"restored. Any shifts they were removed from were not re-added automatically.",
        )
        logger.info(
            "Volunteer pk=%s reinstated by %s", volunteer.pk, request.user.username
        )
    else:
        messages.error(request, "Invalid suspension action.")

    return HttpResponseRedirect(
        reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
    )


@panopticon_required
@require_POST
def send_suspension_email(request, volunteer_id):
    """Send the pre-composed suspension email to the volunteer. Organiser-initiated."""
    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    member = volunteer.member

    if not member.email:
        messages.error(request, f"{member.name} has no email address — suspension email not sent.")
        return HttpResponseRedirect(
            reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
        )

    site_config = get_site_config()
    venue_name = settings.VENUE.get("longname", settings.VENUE.get("name", ""))
    vol_name = member.name or ""

    subject = site_config.suspension_email_subject.replace(
        "{name}", vol_name
    ).replace("{venue}", venue_name)
    body = site_config.suspension_email_body.replace(
        "{name}", vol_name
    ).replace("{venue}", venue_name)

    send_mail(
        subject,
        body,
        settings.VENUE["mailout_from_address"],
        [member.email],
        fail_silently=False,
    )
    logger.info(
        "EMAIL SENT: suspension email to %s (volunteer pk=%s) by %s",
        member.email, volunteer.pk, request.user.username,
    )
    request.session.pop(f"suspension_email_pending_{volunteer_id}", None)
    messages.success(request, f"Suspension email sent to {member.name} ({member.email}).")
    return HttpResponseRedirect(
        reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
    )


@panopticon_required
@require_POST
def skip_suspension_email(request, volunteer_id):
    """Dismiss the suspension email prompt without sending — clears the pending flag."""
    request.session.pop(f"suspension_email_pending_{volunteer_id}", None)
    return HttpResponseRedirect(
        reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
    )


@login_required
@require_safe
def volunteer_stats(request):
    try:
        volunteer = request.user.volunteer
    except Volunteer.DoesNotExist:
        return HttpResponseRedirect(reverse("login"))
    volunteer = Volunteer.objects.select_related("member", "user").get(pk=volunteer.pk)

    config = get_site_config()
    now = timezone.now()

    exclude_slugs = config.stats_training_tag_slugs or []

    base_qs = (
        RotaEntry.objects.filter(
            volunteer=volunteer,
            showing__confirmed=True,
            showing__start__lt=now,
            showing__cancelled=False,
        )
        .select_related("showing__event", "role")
        .order_by("showing__start")
    )

    upcoming_shifts = list(
        RotaEntry.objects.filter(
            volunteer=volunteer,
            showing__confirmed=True,
            showing__start__gte=now,
            showing__cancelled=False,
        )
        .select_related("showing__event", "role")
        .order_by("showing__start")
    )

    # Per-month bar chart for upcoming shifts.
    from collections import Counter
    _upcoming_months: Counter = Counter()
    for entry in upcoming_shifts:
        key = entry.showing.start.strftime("%b %Y")
        _upcoming_months[key] += 1
    # Preserve chronological order (Counter doesn't guarantee it in all Pythons).
    _seen: set = set()
    _upcoming_month_order = []
    for entry in upcoming_shifts:
        key = entry.showing.start.strftime("%b %Y")
        if key not in _seen:
            _seen.add(key)
            _upcoming_month_order.append(key)
    _upcoming_max = max(_upcoming_months.values()) if _upcoming_months else 1
    upcoming_by_month = [
        {"label": k, "count": _upcoming_months[k], "pct": round(_upcoming_months[k] * 100 / _upcoming_max)}
        for k in _upcoming_month_order
    ]

    two_weeks_ahead = (now + timedelta(weeks=2)).date()

    # Event shifts: exclude training-tagged events for the programming gate count.
    if exclude_slugs:
        event_entries_qs = base_qs.exclude(
            showing__event__tags__slug__in=exclude_slugs
        )
    else:
        event_entries_qs = base_qs

    # All confirmed past shifts (including training) for secondary headline count.
    all_shifts_count = base_qs.count()

    # Materialise event entries once — used for milestones and role first-dates.
    event_entries = list(event_entries_qs)
    total_shifts = len(event_entries)

    first_shift = event_entries[0] if event_entries else None
    last_shift = event_entries[-1] if event_entries else None

    if first_shift and last_shift:
        years_active = (
            last_shift.showing.start.year - first_shift.showing.start.year + 1
        )
    else:
        years_active = 0

    # Shifts per year.
    shifts_by_year = list(
        event_entries_qs.values("showing__start__year")
        .annotate(count=Count("pk"))
        .order_by("showing__start__year")
    )
    year_max = max((r["count"] for r in shifts_by_year), default=1)
    for r in shifts_by_year:
        r["pct"] = round(r["count"] * 100 / year_max)

    # Heatmap: list of {year, months: [{mo, count, level}]} rows.
    heatmap_raw = (
        event_entries_qs.values(
            yr=F("showing__start__year"), mo=F("showing__start__month")
        )
        .annotate(count=Count("pk"))
    )
    _heatmap_dict = {(r["yr"], r["mo"]): r["count"] for r in heatmap_raw}
    heatmap_years = sorted({k[0] for k in _heatmap_dict}) if _heatmap_dict else []
    heatmap_max = max(_heatmap_dict.values()) if _heatmap_dict else 0

    _MONTH_NAMES = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    def _heat_level(n):
        if n == 0:
            return 0
        if n == 1:
            return 1
        if n <= 3:
            return 2
        if n <= 6:
            return 3
        return 4

    heatmap_rows = [
        {
            "year": yr,
            "months": [
                {
                    "mo": mo,
                    "name": _MONTH_NAMES[mo - 1],
                    "count": _heatmap_dict.get((yr, mo), 0),
                    "level": _heat_level(_heatmap_dict.get((yr, mo), 0)),
                }
                for mo in range(1, 13)
            ],
        }
        for yr in heatmap_years
    ]

    # Role breakdown, grouped by stats_label (falls back to role name).
    role_rows = list(
        event_entries_qs.annotate(
            label=Coalesce(
                NullIf(F("role__stats_label"), Value("")),
                F("role__name"),
            )
        )
        .values("label")
        .annotate(count=Count("pk"))
        .order_by("-count")[:10]
    )
    total_for_pct = sum(r["count"] for r in role_rows) or 1
    role_breakdown = [
        {**r, "pct": round(r["count"] * 100 / total_for_pct)}
        for r in role_rows
    ]

    # Role evolution: first occurrence of each label, chronological.
    seen_labels = {}
    for entry in event_entries:
        label = entry.role.stats_label or entry.role.name
        if label not in seen_labels:
            seen_labels[label] = {
                "role_name": label,
                "first_date": entry.showing.start,
                "event_name": entry.showing.event.name,
            }
    role_first_dates = sorted(seen_labels.values(), key=lambda x: x["first_date"])

    # Milestones: 1st, 5th, 10th, 25th, 50th, 100th, 150th, 200th...
    _milestone_ns = [1, 5, 10, 25, 50, 100, 150, 200, 250, 300]
    milestones = []
    for n in _milestone_ns:
        if n <= total_shifts:
            entry = event_entries[n - 1]
            milestones.append({
                "n": n,
                "date": entry.showing.start,
                "event_name": entry.showing.event.name,
            })

    # Training records and qualifications.
    training_records = list(
        volunteer.training_records.select_related("role").order_by("training_date")
    )
    qualifications = list(
        volunteer.qualifications.select_related("qualification").order_by(
            "qualification__name"
        )
    )

    programming_min = config.programming_min_event_shifts
    programming_gate_met = total_shifts >= programming_min if programming_min else None
    programming_note = config.stats_programming_note

    # Full shift log: all confirmed past shifts, newest first, for the history table.
    all_past_shifts = list(
        base_qs.select_related("showing__event", "role").order_by("-showing__start")
    )

    # Keyholding shifts: roles flagged as keyholder_only.
    keyholder_shifts = list(
        base_qs.filter(role__keyholder_only=True).order_by("showing__start")
    )
    keyholder_first = keyholder_shifts[0] if keyholder_shifts else None
    twelve_months_ago = now - timedelta(days=365)
    keyholder_last_12m = sum(
        1 for e in keyholder_shifts if e.showing.start >= twelve_months_ago
    )
    _kh_by_year: dict = {}
    for entry in keyholder_shifts:
        yr = entry.showing.start.year
        _kh_by_year[yr] = _kh_by_year.get(yr, 0) + 1
    _kh_year_max = max(_kh_by_year.values()) if _kh_by_year else 1
    keyholder_by_year = [
        {"year": yr, "count": cnt, "pct": round(cnt * 100 / _kh_year_max)}
        for yr, cnt in sorted(_kh_by_year.items())
    ]

    return render(
        request,
        "volunteer_stats.html",
        {
            "volunteer": volunteer,
            "total_shifts": total_shifts,
            "all_shifts_count": all_shifts_count,
            "first_shift": first_shift,
            "last_shift": last_shift,
            "years_active": years_active,
            "shifts_by_year": shifts_by_year,
            "heatmap_rows": heatmap_rows,
            "heatmap_years": heatmap_years,
            "heatmap_max": heatmap_max,
            "year_max": year_max,
            "role_breakdown": role_breakdown,
            "role_first_dates": role_first_dates,
            "milestones": milestones,
            "training_records": training_records,
            "qualifications": qualifications,
            "programming_min": programming_min,
            "programming_gate_met": programming_gate_met,
            "programming_note": programming_note,
            "all_past_shifts": all_past_shifts,
            "upcoming_shifts": upcoming_shifts,
            "upcoming_by_month": upcoming_by_month,
            "two_weeks_ahead": two_weeks_ahead,
            "keyholder_shifts": keyholder_shifts,
            "keyholder_first": keyholder_first,
            "keyholder_last_12m": keyholder_last_12m,
            "keyholder_by_year": keyholder_by_year,
        },
    )
