import json
import datetime
import logging
import csv
import os

from collections import OrderedDict

from django.http import (
    HttpResponse,
    Http404,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.conf import settings
from django import forms as django_forms
from django.forms.models import modelformset_factory
from django.contrib import messages
from django.views.generic import View
import django.template
import django.db
from django.db.models import Count, Q, Min
import django.utils.timezone as timezone
from django.contrib.auth.decorators import (
    permission_required,
    user_passes_test,
)
from toolkit.toolkit_auth.decorators import (
    feature_required,
    write_required,
    read_required,
)
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.decorators.http import require_POST, require_http_methods
from django.utils.html import escape, mark_safe
from django.utils.http import url_has_allowed_host_and_scheme

from toolkit.diary.models import (
    Showing,
    Event,
    EventLink,
    EventTemplateLink,
    DiaryIdea,
    MediaItem,
    EventTemplate,
    EventTag,
    Role,
    RotaEntry,
    PrintedProgramme,
    Room,
    RoomBooking,
    EventTemplateRoom,
    VolunteerEventMark,
    get_site_config,
)
import toolkit.diary.forms as diary_forms
import toolkit.diary.validators as diary_validators
import toolkit.diary.edit_prefs as edit_prefs
from toolkit.diary.poster import generate_event_placeholder
from toolkit.members.models import Qualification, VolunteerQualification
from toolkit.util.image import adjust_colour

# Shared utility method:
from toolkit.diary.daterange import get_date_range

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@feature_required("event_tags")
def edit_event_tags(request):
    active_qs = EventTag.objects.filter(archived=False)
    archived_qs = EventTag.objects.filter(archived=True)

    _filter_group_choices = [("", "—")] + [
        (slug, label) for slug, label in settings.PROGRAMME_FILTER_GROUPS
    ]

    class EventTagForm(django_forms.ModelForm):
        filter_group = django_forms.ChoiceField(
            choices=_filter_group_choices,
            required=False,
            label="Filter group",
        )
        description = django_forms.CharField(
            required=False,
            label="When to use",
            widget=django_forms.TextInput(
                attrs={
                    "placeholder": "e.g. Use for hands-on learning sessions."
                }
            ),
        )

        class Meta:
            model = EventTag
            fields = (
                "name",
                "promoted",
                "sort_order",
                "filter_group",
                "description",
            )

        def clean_filter_group(self):
            return self.cleaned_data["filter_group"] or None

        def clean_description(self):
            return self.cleaned_data["description"] or None

    event_tag_formset = modelformset_factory(
        EventTag,
        form=EventTagForm,
        fields=(
            "name",
            "promoted",
            "sort_order",
            "filter_group",
            "description",
        ),
        can_delete=False,
    )

    if request.method == "POST":
        action = request.POST.get("_action")
        if action == "archive":
            tag_id = request.POST.get("tag_id")
            try:
                tag = EventTag.objects.get(pk=tag_id)
                tag.delete()  # model.delete() archives if used, deletes if unused
                messages.add_message(
                    request, messages.SUCCESS, f"Tag '{tag.name}' archived."
                )
            except EventTag.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_event_tags"))
        elif action == "restore":
            tag_id = request.POST.get("tag_id")
            try:
                tag = EventTag.objects.get(pk=tag_id)
                tag.archived = False
                tag.save()
                messages.add_message(
                    request, messages.SUCCESS, f"Tag '{tag.name}' restored."
                )
            except EventTag.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_event_tags"))
        else:
            formset = event_tag_formset(request.POST, queryset=active_qs)
            if formset.is_valid():
                logger.info("Event tags updated")
                formset.save()
                messages.add_message(
                    request, messages.SUCCESS, "Event tags updated"
                )
                return HttpResponseRedirect(reverse("edit_event_tags"))
    else:
        formset = event_tag_formset(queryset=active_qs)

    context = {"formset": formset, "archived_tags": archived_qs}
    return render(request, "edit_event_tags.html", context)


@feature_required("roles")
def edit_roles(request):
    # This is pretty slow, but it's not a commonly used bit of the UI.
    active_qs = (
        Role.objects.filter(archived=False, is_one_shot=False)
        .select_related("required_qualification")
        .annotate(rota_count=Count("rotaentry"))
    )
    archived_qs = Role.objects.filter(archived=True, is_one_shot=False)

    RoleFormset = modelformset_factory(
        Role,
        diary_forms.RoleForm,
        fields=(
            "name",
            "standard",
            "description",
            "beginner_friendly",
            "wheelchair_accessible",
            "keyholder_only",
            "required_qualification",
            "qualification_gate",
        ),
        can_delete=False,
    )

    if request.method == "POST":
        action = request.POST.get("_action")
        if action == "archive":
            role_id = request.POST.get("role_id")
            try:
                role = Role.objects.get(pk=role_id)
                role.delete()  # model.delete() archives if used, deletes if unused
                messages.add_message(
                    request, messages.SUCCESS, f"Role '{role.name}' archived."
                )
            except Role.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "restore":
            role_id = request.POST.get("role_id")
            try:
                role = Role.objects.get(pk=role_id)
                role.archived = False
                role.save()
                messages.add_message(
                    request, messages.SUCCESS, f"Role '{role.name}' restored."
                )
            except Role.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "add_qualification":
            qual_name = request.POST.get("qualification_name", "").strip()
            qual_notes = request.POST.get("qualification_notes", "").strip()
            if qual_name:
                qual, created = Qualification.objects.get_or_create(
                    name=qual_name
                )
                if created:
                    qual.notes = qual_notes
                    qual.save()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        f"Qualification '{qual_name}' added.",
                    )
                else:
                    messages.add_message(
                        request,
                        messages.WARNING,
                        f"Qualification '{qual_name}' already exists.",
                    )
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "edit_qualification":
            qual_id = request.POST.get("qualification_id")
            try:
                qual = Qualification.objects.get(pk=qual_id)
                new_name = request.POST.get("qualification_name", "").strip()
                new_notes = request.POST.get("qualification_notes", "").strip()
                if not new_name:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        "Qualification name cannot be blank.",
                    )
                elif (
                    new_name != qual.name
                    and Qualification.objects.filter(name=new_name).exists()
                ):
                    messages.add_message(
                        request,
                        messages.ERROR,
                        f"A qualification named '{new_name}' already exists.",
                    )
                else:
                    qual.name = new_name
                    qual.notes = new_notes
                    qual.save()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        f"Qualification '{qual.name}' updated.",
                    )
            except Qualification.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        elif action == "delete_qualification":
            qual_id = request.POST.get("qualification_id")
            try:
                qual = Qualification.objects.get(pk=qual_id)
                if qual.required_for_roles.exists():
                    messages.add_message(
                        request,
                        messages.ERROR,
                        f"Cannot delete '{qual.name}' — it is required by one or more roles. "
                        "Remove the requirement from those roles first.",
                    )
                else:
                    qual.delete()
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        f"Qualification '{qual.name}' deleted.",
                    )
            except Qualification.DoesNotExist:
                pass
            return HttpResponseRedirect(reverse("edit_roles"))
        else:
            formset = RoleFormset(request.POST, queryset=active_qs)
            if formset.is_valid():
                logger.info("Roles updated")
                formset.save()
                messages.add_message(
                    request, messages.SUCCESS, "Roles updated"
                )
                return HttpResponseRedirect(reverse("edit_roles"))
    else:
        formset = RoleFormset(queryset=active_qs)

    return render(
        request,
        "form_edit_roles.html",
        {
            "formset": formset,
            "archived_roles": archived_qs,
            "all_qualifications": Qualification.objects.all(),
        },
    )


@feature_required("printed_programmes")
def printed_programme_edit(request, operation):
    assert operation in ("edit", "add")

    programme_queryset = PrintedProgramme.objects.order_by("start_month")
    programme_formset = modelformset_factory(
        PrintedProgramme,
        form=diary_forms.EditPrintedProgrammeSeasonForm,
        fields=("programme", "designer", "notes"),
        can_delete=True,
        extra=0,
    )

    # Blank forms, for use in GET or for whichever form hasn't been POSTed
    formset = programme_formset(queryset=programme_queryset)
    new_programme_form = diary_forms.NewPrintedProgrammeForm()

    if request.method == "POST":
        if operation == "edit":
            formset = programme_formset(
                request.POST, request.FILES, queryset=programme_queryset
            )
            edited_form = formset
        elif operation == "add":
            new_programme_form = diary_forms.NewPrintedProgrammeForm(
                request.POST, request.FILES
            )
            edited_form = new_programme_form

        if edited_form.is_valid():
            try:
                # Without a transaction an IntegrityError will leave a broken
                # transaction
                with django.db.transaction.atomic():
                    edited_form.save()
            except django.db.IntegrityError:
                edited_form.add_error(
                    None,
                    "Printed programme with this month/year already exists.",
                )
            else:
                logger.info("Printed programme archive updated")
                return HttpResponseRedirect(reverse("edit-printed-programmes"))

    context = {
        "formset": formset,
        "new_programme_form": new_programme_form,
    }

    return render(request, "form_printedprogramme_archive.html", context)


@feature_required("rooms")
@require_http_methods(["GET", "POST"])
def edit_rooms(request):
    """List all rooms; handle create-new-room POST."""
    if request.method == "POST":
        form = diary_forms.RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            logger.info("Room '%s' created", room.name)
            messages.success(request, f"Room '{room.name}' created.")
            return HttpResponseRedirect(reverse("edit_rooms"))
    else:
        form = diary_forms.RoomForm()

    rooms = Room.objects.all().order_by("-is_primary", "name")
    return render(request, "edit_rooms.html", {"rooms": rooms, "form": form})


@feature_required("rooms")
@require_http_methods(["GET", "POST"])
def edit_room_detail(request, room_id):
    """Edit or delete a single room."""
    room = get_object_or_404(Room, pk=room_id)

    if request.method == "POST":
        if "delete" in request.POST:
            if room.bookings.exists():
                messages.error(
                    request,
                    f"Cannot delete '{room.name}' — it is still used by one or more showings.",
                )
                return HttpResponseRedirect(reverse("edit_rooms"))
            name = room.name
            room.delete()
            logger.info("Room '%s' deleted", name)
            messages.success(request, f"Room '{name}' deleted.")
            return HttpResponseRedirect(reverse("edit_rooms"))

        form = diary_forms.RoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            logger.info("Room '%s' updated", room.name)
            messages.success(request, f"Room '{room.name}' updated.")
            return HttpResponseRedirect(reverse("edit_rooms"))
    else:
        form = diary_forms.RoomForm(instance=room)

    return render(
        request, "edit_room_detail.html", {"room": room, "form": form}
    )
