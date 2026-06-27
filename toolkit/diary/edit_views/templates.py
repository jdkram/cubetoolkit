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


@feature_required("event_templates")
def edit_event_templates(request):
    """List all event templates with links to per-template edit pages."""
    templates = EventTemplate.objects.prefetch_related(
        "role_slots__role", "tags"
    ).all()
    return render(
        request, "edit_event_templates.html", {"templates": templates}
    )


@feature_required("event_templates")
def edit_event_template_detail(request, template_id=None):
    """Create or edit a single event template."""
    if template_id is not None:
        event_template = get_object_or_404(EventTemplate, pk=template_id)
    else:
        event_template = None

    if request.method == "POST":
        if "delete" in request.POST and event_template is not None:
            name = event_template.name
            event_template.delete()
            logger.info("Event template '%s' deleted", name)
            messages.add_message(
                request, messages.SUCCESS, f"Deleted template '{name}'"
            )
            return HttpResponseRedirect(reverse("edit_event_templates"))

        form = diary_forms.EventTemplateForm(
            request.POST, instance=event_template
        )
        roles_formset = diary_forms.EventTemplateRoleFormSet(
            request.POST, instance=event_template or EventTemplate()
        )
        links_formset = diary_forms.EventTemplateLinkFormSet(
            request.POST, instance=event_template or EventTemplate()
        )
        rooms_formset = diary_forms.EventTemplateRoomFormSet(
            request.POST, instance=event_template or EventTemplate()
        )

        if (
            form.is_valid()
            and roles_formset.is_valid()
            and links_formset.is_valid()
            and rooms_formset.is_valid()
        ):
            saved = form.save()
            roles_formset.instance = saved
            roles_formset.save()
            links_formset.instance = saved
            links_formset.save()
            rooms_formset.instance = saved
            rooms_formset.save()
            logger.info("Event template '%s' saved", saved.name)
            messages.add_message(
                request, messages.SUCCESS, f"Saved template '{saved.name}'"
            )
            return HttpResponseRedirect(reverse("edit_event_templates"))
    else:
        form = diary_forms.EventTemplateForm(instance=event_template)
        roles_formset = diary_forms.EventTemplateRoleFormSet(
            instance=event_template
        )
        links_formset = diary_forms.EventTemplateLinkFormSet(
            instance=event_template
        )
        rooms_formset = diary_forms.EventTemplateRoomFormSet(
            instance=event_template
        )

    export_json = None
    if event_template is not None:
        export_json = _export_template_json(event_template)

    context = {
        "form": form,
        "roles_formset": roles_formset,
        "links_formset": links_formset,
        "rooms_formset": rooms_formset,
        "event_template": event_template,
        "export_json": export_json,
        "allowed_domains": diary_validators.get_eventlink_allowed_domains(),
    }
    return render(request, "edit_event_template_detail.html", context)


def _export_template_json(template):
    """Serialise an EventTemplate to a JSON string suitable for copy-paste export."""
    data = {
        "name": template.name,
        "pricing": template.pricing or "",
        "film_information": template.film_information or "",
        "copy_summary": template.copy_summary or "",
        "copy": template.copy or "",
        "terms": template.terms or "",
        "rota_notes": template.rota_notes or "",
        "private": template.private,
        "outside_hire": template.outside_hire,
        "tags": [t.name for t in template.tags.order_by("name")],
        "role_slots": [
            {"role": slot.role.name, "count": slot.count}
            for slot in template.role_slots.select_related("role").order_by(
                "role__name"
            )
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["GET", "POST"])
def import_event_template(request):
    """Import a template from JSON (Panopticon only).

    Handles same-name conflict via an 'overwrite' checkbox.  When unchecked
    and a template with the given name exists, the import creates a copy
    suffixed with " (copy)".
    """
    if request.method == "POST":
        json_text = request.POST.get("json_text", "").strip()
        overwrite = request.POST.get("overwrite") == "1"
        errors = []
        template = None

        if not json_text:
            errors.append("Paste a JSON template to import.")
        else:
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as exc:
                errors.append(f"Invalid JSON: {exc}")
                data = None

            if data is not None:
                name = (data.get("name") or "").strip()
                if not name:
                    errors.append(
                        "Template JSON must contain a non-empty 'name' field."
                    )
                else:
                    existing = EventTemplate.objects.filter(name=name).first()
                    if existing and overwrite:
                        template = existing
                        template.role_slots.all().delete()
                        template.tags.clear()
                    elif existing and not overwrite:
                        name = f"{name} (copy)"
                        template = EventTemplate(name=name)
                    else:
                        template = EventTemplate(name=name)

                    if not errors:
                        template.pricing = data.get("pricing") or ""
                        template.film_information = (
                            data.get("film_information") or ""
                        )
                        template.copy_summary = data.get("copy_summary") or ""
                        template.copy = data.get("copy") or ""
                        template.terms = data.get("terms") or ""
                        template.rota_notes = data.get("rota_notes") or ""
                        template.private = bool(data.get("private", False))
                        template.outside_hire = bool(
                            data.get("outside_hire", False)
                        )
                        template.save()

                        tag_warnings = []
                        for tag_name in data.get("tags") or []:
                            try:
                                tag = EventTag.objects.get(name=tag_name)
                                template.tags.add(tag)
                            except EventTag.DoesNotExist:
                                tag_warnings.append(tag_name)

                        role_warnings = []
                        for slot in data.get("role_slots") or []:
                            role_name = (slot.get("role") or "").strip()
                            count = slot.get("count", 1)
                            try:
                                role = Role.objects.get(name=role_name)
                                EventTemplateRole = template.role_slots.model
                                EventTemplateRole.objects.create(
                                    template=template, role=role, count=count
                                )
                            except Role.DoesNotExist:
                                role_warnings.append(role_name)

                        msg = f"Imported template '{template.name}'."
                        if tag_warnings:
                            msg += f" Unknown tags skipped: {', '.join(tag_warnings)}."
                        if role_warnings:
                            msg += f" Unknown roles skipped: {', '.join(role_warnings)}."
                        messages.success(request, msg)
                        return HttpResponseRedirect(
                            reverse(
                                "edit_event_template_detail",
                                kwargs={"template_id": template.pk},
                            )
                        )

        return render(
            request,
            "import_event_template.html",
            {
                "errors": errors,
                "json_text": json_text,
                "overwrite": overwrite,
            },
        )

    return render(request, "import_event_template.html", {})
