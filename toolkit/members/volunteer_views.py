import logging
from datetime import datetime

from django.contrib.auth.models import User
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
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
from toolkit.members.models import AnonymisationLog, Member, Volunteer, TrainingRecord
from toolkit.diary.models import Role, RotaEntry, VolunteerEventMark, get_site_config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@panopticon_required
@require_safe
def view_volunteer_list(request):
    show_retired = request.GET.get("show-retired", None) is not None
    show_dormant = request.GET.get("show-dormant", None) is not None
    # Get all volunteers, sorted by name:
    qs = TrainingRecord.objects.filter(
        training_type=TrainingRecord.GENERAL_TRAINING
    ).order_by("-training_date")

    volunteers = (
        Volunteer.objects.order_by("member__name")
        .select_related()
        .prefetch_related("roles")
        .prefetch_related("member")
        .prefetch_related(
            Prefetch(
                "training_records", queryset=qs, to_attr="general_training"
            )
        )
    )

    if show_retired:
        pass  # show everything
    elif show_dormant:
        volunteers = volunteers.filter(status__in=[Volunteer.STATUS_ACTIVE, Volunteer.STATUS_DORMANT])
    else:
        volunteers = volunteers.filter(status=Volunteer.STATUS_ACTIVE)
    active_count = sum(1 for v in volunteers if v.active)
    context = {
        "volunteers": volunteers,
        "default_mugshot": settings.DEFAULT_MUGSHOT,
        "retired_data_included": show_retired,
        "dormant_data_included": show_dormant,
        "active_count": active_count,
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

    volunteers = Volunteer.objects.filter(active=True).order_by("member__name")
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
        Volunteer.objects.exclude(status=Volunteer.STATUS_RETIRED)
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
def view_volunteer_role_report(request):
    # Build dict of role names -> volunteer names
    role_vol_map = {}
    # Query for active volunteers, sorted by name
    volunteer_query = (
        Role.objects.filter(volunteer__active=True)
        .values_list("name", "volunteer__id", "volunteer__member__name")
        .order_by("volunteer__member__name", "name")
    )

    for role, vol_id, vol_name in volunteer_query:
        role_vol_map.setdefault(role, []).append(vol_name)

    # Now sort role_vol_map by role name:
    role_vol_map = sorted(
        role_vol_map.items(), key=lambda role_name_tuple: role_name_tuple[0]
    )
    # (now got a list  of (role, (name1, name2, ...)) tuples, rather than a
    # dict, but that's fine)

    context = {
        "role_vol_map": role_vol_map,
    }
    return render(request, "volunteer_role_report.html", context)


@panopticon_required
@require_safe
def select_volunteer(request, action, active=True):
    # This view is called to retire / unretire a volunteer. It presents a list
    # of all volunteer names and a button. If the view is called with
    # "action=retire" in the url then it shows a "retire" button linked to the
    # retire url, and if it's called with "action=unretire" it shows a link to
    # the unretire url.
    #
    # The selection of volunteers (retired vs unretired) is decided by the
    # "active" parameter to this method, which is set by the url route,
    # depending on which view was used. This is probably not the simplest way
    # to do this...
    action_urls = {
        "retire": reverse("inactivate-volunteer"),
        "unretire": reverse("activate-volunteer"),
    }

    assert action in action_urls
    assert isinstance(active, bool)

    volunteers = (
        Volunteer.objects.filter(active=active)
        .order_by("member__name")
        .select_related()
    )

    context = {
        "volunteers": volunteers,
        "action": action,
        "action_url": action_urls[action],
    }

    return render(request, "select_volunteer.html", context)


@panopticon_required
@require_POST
def activate_volunteer(request, set_active=True):
    # Sets the 'active' value for the volunteer with the id passed  in the
    # 'volunteer' parameter of the POST request

    vol_pk = request.POST.get("volunteer", None)

    vol = get_object_or_404(Volunteer, id=vol_pk)

    assert isinstance(set_active, bool)
    vol.status = Volunteer.STATUS_ACTIVE if set_active else Volunteer.STATUS_RETIRED
    vol.save()

    logger.info(
        f"{request.user.last_name} set status to {vol.status} for volunteer {vol.member.name}"
    )
    messages.add_message(
        request,
        messages.SUCCESS,
        f"{'Unretired' if set_active else 'Retired'} volunteer {vol.member.name}",
    )
    # email admin with the news (only if vols_admin_address is configured)
    vols_admin = settings.VENUE.get("vols_admin_address") or []
    if vols_admin:
        admin_body = (
            f"I'm delighted to inform you that {request.user.last_name} has updated the "
            f"status of volunteer\n\n"
            f"{vol.member.name} <{vol.member.email}>\n\n"
            f"to {'unretired' if set_active else 'retired'}.\n\n"
            f"Please amend the volunteers mailing list "
            f"at your earliest convenience."
        )
        send_mail(
            (
                f"[{settings.VENUE['longname']}] Change in volunteer status {vol.member.name}"
            ),
            admin_body,
            settings.VENUE["mailout_from_address"],
            vols_admin,
            fail_silently=False,
        )

    return HttpResponseRedirect(reverse("view-volunteer-summary"))


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

    context = {
        "pagetitle": "Add Volunteer" if create_new else "Edit Volunteer",
        "default_mugshot": settings.DEFAULT_MUGSHOT,
        "volunteer": volunteer,
        "user_form": user_form,
        "vol_form": vol_form,
        "mem_form": mem_form,
        "training_record_form": training_record_form,
        "dawn_of_toolkit": settings.DAWN_OF_TOOLKIT,
        "site_config": get_site_config(),
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

    if not volunteer.active:
        response = {"succeeded": False, "errors": "volunteer is not active"}
        return JsonResponse(response)
    elif record_form.is_valid():
        record_form.save()
        logger.info(
            f"Added training record {new_record.id} for volunteer '{volunteer.member.name}'"
        )

        if new_record.training_type == TrainingRecord.ROLE_TRAINING:
            # Now make sure the volunteer has that role selected:
            volunteer.roles.add(new_record.role)
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

    if not record.volunteer.active:
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
        TrainingRecord.objects.filter(volunteer__active=True)
        .filter(volunteer__roles=F("role"))
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

    # Second data set - all active volunteers.
    qs = TrainingRecord.objects.filter(
        training_type=TrainingRecord.GENERAL_TRAINING
    ).order_by("-training_date")

    volunteers = (
        Volunteer.objects.filter(active=True)
        .order_by("member__name")
        .select_related()
        # Use above queryset to prepopulate a 'general_training'
        # attribute on the retrieved volunteers (to keep the number
        # of queries sane)
        .prefetch_related(
            Prefetch(
                "training_records", queryset=qs, to_attr="general_training"
            )
        )
    )

    context = {"report_data": role_map_list, "volunteers": volunteers}
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
                    # Now make sure the volunteer has that role selected:
                    volunteer.roles.add(role)

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

        with transaction.atomic():
            anon_label = f"Anonymised volunteer {volunteer.pk}"

            # Clear FK-linked rota entries (primary path)
            fk_matches.update(volunteer=None, name="")
            # Legacy fallback: text-match entries where FK was never set
            name_matches.update(name="")

            # Anonymise the Member record
            member.name = anon_label
            member.email = f"anon-{volunteer.pk}@deleted.invalid"
            member.address = ""
            member.posttown = ""
            member.postcode = ""
            member.country = ""
            member.phone = ""
            member.altphone = ""
            member.personal_pronouns = ""
            member.notes = ""
            member.website = ""
            member.mailout = False
            member.save()

            # Anonymise the Volunteer record
            volunteer.notes = ""
            volunteer.access_intro = ""
            volunteer.access_needs = ""
            volunteer.access_links = ""
            volunteer.emergency_contact_name = ""
            volunteer.emergency_contact_relationship = ""
            volunteer.emergency_contact_phone = ""
            volunteer.dir_share_listed = False
            volunteer.dir_share_name_style = Volunteer.NAME_STYLE_FULL
            volunteer.dir_share_pronouns = False
            volunteer.dir_share_email = False
            volunteer.dir_share_phone = False
            volunteer.dir_share_access_rider = False
            volunteer.dir_share_collectives = False
            if volunteer.portrait:
                volunteer.portrait.delete(save=False)
                volunteer.portrait = None
            volunteer.status = Volunteer.STATUS_RETIRED
            volunteer.roles.clear()
            volunteer.collectives.clear()
            volunteer.save()

            # Anonymise the Django User account
            user = volunteer.user
            user.username = f"anon-{volunteer.pk}"
            user.first_name = ""
            user.last_name = ""
            user.email = ""
            user.is_active = False
            user.is_superuser = False
            user.set_unusable_password()
            user.save()

            # Remove personal-preference data
            VolunteerEventMark.objects.filter(volunteer=volunteer).delete()
            TrainingRecord.objects.filter(volunteer=volunteer).delete()

            AnonymisationLog.objects.create(
                volunteer_pk=volunteer.pk,
                performed_by=request.user,
            )

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
def send_volunteer_password_reset(request, volunteer_id):
    """Send a password reset email to a volunteer (Panopticon only)."""
    if not request.user.is_superuser:
        raise PermissionDenied

    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    user = volunteer.user
    if user is None or not user.email:
        messages.error(request, "This volunteer has no linked user account or no email address.")
        return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))

    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    token = default_token_generator.make_token(user)
    uid_b64 = urlsafe_base64_encode(force_bytes(user.pk))
    reset_url = request.build_absolute_uri(
        reverse("password_reset_confirm", kwargs={"uidb64": uid_b64, "token": token})
    )

    send_mail(
        subject=f"[{settings.VENUE['longname']}] Set your password",
        message=(
            f"Hi {user.first_name or user.username},\n\n"
            f"A Panopticon user has requested a password reset for your account.\n\n"
            f"Click the link below to set your password (valid for 24 hours):\n\n"
            f"{reset_url}\n\n"
            f"If you weren't expecting this, you can ignore this email."
        ),
        from_email=settings.VENUE.get("mailout_from_address") or settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )
    logger.info(
        "Password reset email sent to volunteer pk=%s by %s", volunteer_id, request.user.username
    )
    messages.success(request, f"Password reset email sent to {user.email}.")
    return HttpResponseRedirect(reverse("edit-volunteer", kwargs={"volunteer_id": volunteer_id}))


@require_POST
@panopticon_required
def clear_login_inactive(request, volunteer_id):
    """Clear the login-inactive flag after a panopticon user has followed up."""
    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    volunteer.login_inactive = False
    volunteer.save(update_fields=["login_inactive"])
    logger.info(
        "login_inactive flag cleared for volunteer pk=%s by %s",
        volunteer_id,
        request.user.username,
    )
    messages.success(request, f"Inactivity flag cleared for {volunteer.member.name}.")
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
