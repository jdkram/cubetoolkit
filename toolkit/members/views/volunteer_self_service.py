# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: self_service.
"""
from ._common import *

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


@require_POST
@login_required
def renew_consent_self(request):
    """Let a volunteer reconfirm data-processing consent from their dashboard.

    Requires login (unlike a token-link renewal) so that renewing also proves
    the account is still in active use. Stamps Member.gdpr_opt_in and brings
    the volunteer's consent_policy_version up to date, clearing the overdue flag.
    """
    from toolkit.inductions.models import InductionsSettings

    try:
        volunteer = request.user.volunteer
    except Exception:
        return HttpResponseRedirect(reverse("toolkit-index"))

    volunteer.member.gdpr_opt_in = timezone.now()
    volunteer.member.save(update_fields=["gdpr_opt_in"])
    volunteer.consent_policy_version = InductionsSettings.load().privacy_policy_version
    volunteer.consent_reminder_sent_at = None
    volunteer.save(update_fields=["consent_policy_version", "consent_reminder_sent_at"])
    logger.info("Volunteer pk=%s renewed consent", volunteer.pk)
    messages.success(request, "Thanks — your consent has been reconfirmed.")
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


