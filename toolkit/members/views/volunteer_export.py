# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: export.
"""
from ._common import *
from toolkit.diary.models import Event

_UPCOMING_EVENTS_HORIZON_DAYS = 90

_EXPORT_FIELD_GROUPS = [
    (
        "basic",
        "Basic (name, email, status)",
        False,
        [
            ("Name", lambda v: v.member.name),
            ("Email", lambda v: v.member.email),
            ("Status", lambda v: v.status),
            ("Collectives", lambda v: ", ".join(c.name for c in v.collectives.all())),
        ],
    ),
    (
        "contact",
        "Contact details (phone numbers)",
        True,
        [
            ("Phone", lambda v: v.member.phone),
            ("Alternate phone", lambda v: v.member.altphone),
        ],
    ),
    (
        "address",
        "Home address",
        True,
        [
            ("Address", lambda v: v.member.address.replace("\r\n", ", ")),
            ("City", lambda v: v.member.posttown),
            ("Postcode", lambda v: v.member.postcode),
        ],
    ),
    (
        "notes",
        "Internal notes",
        False,
        [
            ("Member notes", lambda v: v.member.notes),
            ("Volunteer notes", lambda v: v.notes),
        ],
    ),
    (
        "dates",
        "Dates (inducted, last update)",
        False,
        [
            (
                "Inducted",
                lambda v: (
                    "Pre-toolkit"
                    if v.is_old()
                    else v.member.created_at.strftime("%d %b %Y")
                ),
            ),
            ("Last update", lambda v: v.member.updated_at.strftime("%d %b %Y")),
        ],
    ),
]


_EXPORT_GROUP_IDS = {g[0] for g in _EXPORT_FIELD_GROUPS}


_SENSITIVE_GROUP_IDS = {g[0] for g in _EXPORT_FIELD_GROUPS if g[2]}


def _upcoming_confirmed_events():
    """Confirmed events with a future showing, for the export event checklist."""
    horizon = timezone.now() + timedelta(days=_UPCOMING_EVENTS_HORIZON_DAYS)
    return (
        Event.objects.filter(
            showings__start__gte=timezone.now(),
            showings__start__lte=horizon,
            showings__confirmed=True,
        )
        .distinct()
        .order_by("name")
    )


def _filtered_volunteers(filter_type, event_ids):
    """Volunteer queryset for the given export filter."""
    volunteers = (
        Volunteer.objects.active()
        .select_related("member")
        .prefetch_related("collectives")
        .order_by("member__name")
    )
    if filter_type == ExportAuditLog.FILTER_ALL:
        return volunteers

    shift_filter = RotaEntry.objects.filter(showing__start__gte=timezone.now())
    if filter_type == ExportAuditLog.FILTER_EVENTS:
        shift_filter = shift_filter.filter(showing__event_id__in=event_ids)
    volunteer_ids = shift_filter.values_list("volunteer_id", flat=True).distinct()
    return volunteers.filter(pk__in=volunteer_ids)


@panopticon_required
def export_volunteers_as_csv(request):
    """Full export page: filter + field-group selector + PII warning + audit log."""
    if request.method == "POST":
        selected_ids = [
            gid for gid in _EXPORT_GROUP_IDS
            if request.POST.get(f"group_{gid}")
        ]
        if not selected_ids:
            selected_ids = ["basic"]

        filter_type = request.POST.get("filter_type", ExportAuditLog.FILTER_ALL)
        if filter_type not in dict(ExportAuditLog.FILTER_TYPE_CHOICES):
            filter_type = ExportAuditLog.FILTER_ALL
        event_ids = [
            int(pk) for pk in request.POST.getlist("filter_event_ids") if pk.isdigit()
        ]
        if filter_type != ExportAuditLog.FILTER_EVENTS:
            event_ids = []

        # Build flat list of (header, accessor) for selected groups.
        columns = []
        for gid, _label, _sensitive, fields in _EXPORT_FIELD_GROUPS:
            if gid in selected_ids:
                columns.extend(fields)

        volunteers = _filtered_volunteers(filter_type, event_ids)
        rows = list(volunteers)

        # Log the export.
        export_reason = request.POST.get("export_reason", "").strip()
        is_sensitive = bool(set(selected_ids) & _SENSITIVE_GROUP_IDS)
        logger.info(
            f"User {request.user} exported {len(rows)} volunteers "
            f"(fields: {selected_ids}, filter: {filter_type}, sensitive={is_sensitive}, reason={export_reason!r})"
        )
        ExportAuditLog.objects.create(
            exported_by=request.user,
            fields_included=selected_ids,
            recipient_count=len(rows),
            export_reason=export_reason,
            filter_type=filter_type,
            filter_event_ids=event_ids,
        )

        now = datetime.now().strftime("%d %b %Y %I-%M %p")
        file_name = f"{settings.VENUE['name']} Volunteers {now}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        writer = csv.writer(response)
        writer.writerow([col[0] for col in columns])
        for volunteer in rows:
            writer.writerow([col[1](volunteer) for col in columns])
        return response

    # GET: render the field selection page.
    return render(request, "volunteer_export.html", {
        "field_groups": _EXPORT_FIELD_GROUPS,
        "sensitive_ids": _SENSITIVE_GROUP_IDS,
        "upcoming_events": _upcoming_confirmed_events(),
    })


@panopticon_required
@require_safe
def export_audit_log(request):
    """Audit log of all volunteer CSV exports."""
    logs = list(ExportAuditLog.objects.select_related("exported_by").all()[:200])

    event_ids = {eid for log in logs for eid in log.filter_event_ids}
    event_names = dict(Event.objects.filter(pk__in=event_ids).values_list("pk", "name"))
    for log in logs:
        log.filter_event_names = [
            event_names.get(eid, f"(deleted event {eid})") for eid in log.filter_event_ids
        ]

    return render(request, "volunteer_export_audit.html", {"logs": logs})


