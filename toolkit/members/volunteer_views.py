import logging
from datetime import datetime

from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
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
from django.db.models import Exists, F, OuterRef, Prefetch
from django.utils import timezone
import csv

from toolkit.members.forms import (
    UserForm,
    VolunteerForm,
    MemberFormWithoutNotes,
    TrainingRecordForm,
    GroupTrainingForm,
)
from toolkit.members.models import Member, Volunteer, TrainingRecord
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


@panopticon_required
@require_safe
def export_volunteers_as_csv(request):
    # TODO use settings.DAWN_OF_TOOLKIT with export
    logger.info(f"User {request.user} requested a volunteer CSV export")
    now = datetime.now().strftime("%d %b %Y %I-%M %p")
    file_name = f"{settings.VENUE['name']} Volunteers {now}.csv"
    logger.info(f'Exported CSV filename: "{file_name}"')

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "Name",
            "Email",
            "Address",
            "City",
            "Postcode",
            "Phone",
            "Alternate phone",
            "Member notes",
            "Volunteer notes",
            "Inducted",
            "Last update",
        ]
    )

    volunteers = Volunteer.objects.active().order_by("member__name")
    for volunteer in volunteers:
        writer.writerow(
            [
                volunteer.member.name,
                volunteer.member.email,
                volunteer.member.address.replace("\r\n", ", "),
                volunteer.member.posttown,
                volunteer.member.postcode,
                volunteer.member.phone,
                volunteer.member.altphone,
                volunteer.member.notes,
                volunteer.member.volunteer.notes,
                volunteer.member.created_at.strftime("%I:%M %p %d %b %Y"),
                volunteer.member.updated_at.strftime("%I:%M %p %d %b %Y"),
            ]
        )
    return response


@panopticon_required
@require_safe
def view_volunteer_summary(request):
    if not request.user.is_superuser:
        raise PermissionDenied

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
    context = {
        "volunteers": volunteers,
        "active_count": active_count,
        "dormant_count": dormant_count,
        "sort_type": sort_type,
        "dawn_of_toolkit": settings.DAWN_OF_TOOLKIT,
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

    context = {
        "never_onboarded": never_onboarded,
        "never_onboarded_count": never_onboarded.count(),
        "long_inactive": long_inactive,
        "long_inactive_count": long_inactive.count(),
        "recently_dormant": recently_dormant,
        "recently_dormant_count": recently_dormant.count(),
        "dormancy_days": config.volunteer_dormancy_days,
        "never_logged_in_grace_days": config.volunteer_never_logged_in_grace_days,
        "purge_days": config.volunteer_purge_days,
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
@require_safe
def view_volunteer_role_report(request):
    # Volunteer role assignment has been removed; this view is now a stub.
    context = {"role_vol_map": []}
    return render(request, "volunteer_role_report.html", context)


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
        show_user_mgmt = settings.VENUE.get("show_user_management") and user is not None and request.user.is_superuser
        user_form = UserForm(request.POST, instance=user) if show_user_mgmt else None
        forms_valid = vol_form.is_valid() and mem_form.is_valid()
        if user_form is not None:
            forms_valid = forms_valid and user_form.is_valid()
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
                    f"{member.name} has been suspended: their login is now "
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

            if user_form is not None:
                user_form.save(granted_by=request.user)

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
                    "Added {len(form.cleaned_data['volunteers'])} {TrainingRecord.GENERAL_TRAINING_DESC} records",
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

    return render(
        request,
        "anonymise_volunteer.html",
        {
            "volunteer": volunteer,
            "member": member,
            "rota_match_count": rota_match_count,
            "rota_sample": rota_sample,
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


@require_POST
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
