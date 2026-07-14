# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: suspension.
"""
from ._common import *

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

    subject = _render_admin_email(site_config.suspension_email_subject, vol_name, venue_name)
    body = _render_admin_email(site_config.suspension_email_body, vol_name, venue_name)

    try:
        send_mail(
            subject,
            body,
            settings.VENUE["mailout_from_address"],
            [member.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            f"Failed to send suspension email to volunteer pk={volunteer.pk}"
        )
        messages.error(
            request,
            f"The suspension email to {member.name} failed to send. "
            f"Their suspension is unaffected; try sending the email again.",
        )
        return HttpResponseRedirect(
            reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id})
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


