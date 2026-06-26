# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: reports.
"""
from ._common import *

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


@panopticon_required
@require_safe
def view_volunteer_role_report(request):
    # Role assignment was removed; redirect to the qualification report which replaced it.
    return HttpResponseRedirect(reverse("view-qualification-report"))


