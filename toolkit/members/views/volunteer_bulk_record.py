# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: bulk_record.
"""
from ._common import *

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


