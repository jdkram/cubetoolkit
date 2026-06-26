# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: pool_admin.
"""
from ._common import *

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
    subject = _render_admin_email(subject_template, name, venue)
    body = _render_admin_email(body_template, name, venue)

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
            subject = _render_admin_email(subject_template, name, venue)
            body = _render_admin_email(body_template, name, venue)
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


