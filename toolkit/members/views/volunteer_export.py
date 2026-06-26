# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: export.
"""
from ._common import *

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


@panopticon_required
def export_volunteers_as_csv(request):
    """Full export page: field-group selector + PII warning + audit log."""
    if request.method == "POST":
        selected_ids = [
            gid for gid in _EXPORT_GROUP_IDS
            if request.POST.get(f"group_{gid}")
        ]
        if not selected_ids:
            selected_ids = ["basic"]

        # Build flat list of (header, accessor) for selected groups.
        columns = []
        for gid, _label, _sensitive, fields in _EXPORT_FIELD_GROUPS:
            if gid in selected_ids:
                columns.extend(fields)

        volunteers = (
            Volunteer.objects.active()
            .select_related("member")
            .prefetch_related("collectives")
            .order_by("member__name")
        )
        rows = list(volunteers)

        # Log the export.
        export_reason = request.POST.get("export_reason", "").strip()
        is_sensitive = bool(set(selected_ids) & _SENSITIVE_GROUP_IDS)
        logger.info(
            f"User {request.user} exported {len(rows)} volunteers "
            f"(fields: {selected_ids}, sensitive={is_sensitive}, reason={export_reason!r})"
        )
        ExportAuditLog.objects.create(
            exported_by=request.user,
            fields_included=selected_ids,
            recipient_count=len(rows),
            export_reason=export_reason,
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
    })


@panopticon_required
@require_safe
def export_audit_log(request):
    """Audit log of all volunteer CSV exports."""
    logs = ExportAuditLog.objects.select_related("exported_by").all()[:200]
    return render(request, "volunteer_export_audit.html", {"logs": logs})


