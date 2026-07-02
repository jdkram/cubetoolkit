# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: edit.
"""
from ._common import *

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
            "subject": _render_admin_email(site_config.suspension_email_subject, vol_name, venue_name),
            "body": _render_admin_email(site_config.suspension_email_body, vol_name, venue_name),
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

    Thin delegate over toolkit.toolkit_auth.password_emails.send_password_set_email
    so the token-building + venue lookup + welcome/reset copy live in one place
    shared with the inductions check-in flow.
    """
    password_emails.send_password_set_email(request, user, welcome=welcome)


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


