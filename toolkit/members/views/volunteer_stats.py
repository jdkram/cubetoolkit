# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-input"
"""Auto-extracted from toolkit/members/volunteer_views.py (chunk 5 of the
maintainability pass — see MAINTAINABILITY_PASS.md). Verbatim move; no
behaviour change. Group: stats.
"""
from ._common import *

@login_required
@require_safe
def volunteer_stats(request):
    try:
        volunteer = request.user.volunteer
    except Volunteer.DoesNotExist:
        return HttpResponseRedirect(reverse("login"))
    volunteer = Volunteer.objects.select_related("member", "user").get(pk=volunteer.pk)

    config = get_site_config()
    now = timezone.now()

    exclude_slugs = config.stats_training_tag_slugs or []

    base_qs = (
        RotaEntry.objects.filter(
            volunteer=volunteer,
            showing__confirmed=True,
            showing__start__lt=now,
            showing__cancelled=False,
        )
        .select_related("showing__event", "role")
        .order_by("showing__start")
    )

    upcoming_shifts = list(
        RotaEntry.objects.filter(
            volunteer=volunteer,
            showing__confirmed=True,
            showing__start__gte=now,
            showing__cancelled=False,
        )
        .select_related("showing__event", "role")
        .order_by("showing__start")
    )

    # Per-month bar chart for upcoming shifts.
    from collections import Counter
    _upcoming_months: Counter = Counter()
    for entry in upcoming_shifts:
        key = entry.showing.start.strftime("%b %Y")
        _upcoming_months[key] += 1
    # Preserve chronological order (Counter doesn't guarantee it in all Pythons).
    _seen: set = set()
    _upcoming_month_order = []
    for entry in upcoming_shifts:
        key = entry.showing.start.strftime("%b %Y")
        if key not in _seen:
            _seen.add(key)
            _upcoming_month_order.append(key)
    _upcoming_max = max(_upcoming_months.values()) if _upcoming_months else 1
    upcoming_by_month = [
        {"label": k, "count": _upcoming_months[k], "pct": round(_upcoming_months[k] * 100 / _upcoming_max)}
        for k in _upcoming_month_order
    ]

    two_weeks_ahead = (now + timedelta(weeks=2)).date()

    # Event shifts: exclude training-tagged events for the programming gate count.
    if exclude_slugs:
        event_entries_qs = base_qs.exclude(
            showing__event__tags__slug__in=exclude_slugs
        )
    else:
        event_entries_qs = base_qs

    # All confirmed past shifts (including training) for secondary headline count.
    all_shifts_count = base_qs.count()

    # Materialise event entries once — used for milestones and role first-dates.
    event_entries = list(event_entries_qs)
    total_shifts = len(event_entries)

    first_shift = event_entries[0] if event_entries else None
    last_shift = event_entries[-1] if event_entries else None

    if first_shift and last_shift:
        years_active = (
            last_shift.showing.start.year - first_shift.showing.start.year + 1
        )
    else:
        years_active = 0

    # Shifts per year.
    shifts_by_year = list(
        event_entries_qs.values("showing__start__year")
        .annotate(count=Count("pk"))
        .order_by("showing__start__year")
    )
    year_max = max((r["count"] for r in shifts_by_year), default=1)
    for r in shifts_by_year:
        r["pct"] = round(r["count"] * 100 / year_max)

    # Heatmap: list of {year, months: [{mo, count, level}]} rows.
    heatmap_raw = (
        event_entries_qs.values(
            yr=F("showing__start__year"), mo=F("showing__start__month")
        )
        .annotate(count=Count("pk"))
    )
    _heatmap_dict = {(r["yr"], r["mo"]): r["count"] for r in heatmap_raw}
    heatmap_years = sorted({k[0] for k in _heatmap_dict}) if _heatmap_dict else []
    heatmap_max = max(_heatmap_dict.values()) if _heatmap_dict else 0

    _MONTH_NAMES = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    def _heat_level(n):
        if n == 0:
            return 0
        if n == 1:
            return 1
        if n <= 3:
            return 2
        if n <= 6:
            return 3
        return 4

    heatmap_rows = [
        {
            "year": yr,
            "months": [
                {
                    "mo": mo,
                    "name": _MONTH_NAMES[mo - 1],
                    "count": _heatmap_dict.get((yr, mo), 0),
                    "level": _heat_level(_heatmap_dict.get((yr, mo), 0)),
                }
                for mo in range(1, 13)
            ],
        }
        for yr in heatmap_years
    ]

    # Role breakdown, grouped by stats_label (falls back to role name).
    role_rows = list(
        event_entries_qs.annotate(
            label=Coalesce(
                NullIf(F("role__stats_label"), Value("")),
                F("role__name"),
            )
        )
        .values("label")
        .annotate(count=Count("pk"))
        .order_by("-count")[:10]
    )
    total_for_pct = sum(r["count"] for r in role_rows) or 1
    role_breakdown = [
        {**r, "pct": round(r["count"] * 100 / total_for_pct)}
        for r in role_rows
    ]

    # Role evolution: first occurrence of each label, chronological.
    seen_labels = {}
    for entry in event_entries:
        label = entry.role.stats_label or entry.role.name
        if label not in seen_labels:
            seen_labels[label] = {
                "role_name": label,
                "first_date": entry.showing.start,
                "event_name": entry.showing.event.name,
            }
    role_first_dates = sorted(seen_labels.values(), key=lambda x: x["first_date"])

    # Milestones: 1st, 5th, 10th, 25th, 50th, 100th, 150th, 200th...
    _milestone_ns = [1, 5, 10, 25, 50, 100, 150, 200, 250, 300]
    milestones = []
    for n in _milestone_ns:
        if n <= total_shifts:
            entry = event_entries[n - 1]
            milestones.append({
                "n": n,
                "date": entry.showing.start,
                "event_name": entry.showing.event.name,
            })

    # Training records and qualifications.
    training_records = list(
        volunteer.training_records.select_related("role").order_by("training_date")
    )
    qualifications = list(
        volunteer.qualifications.select_related("qualification").order_by(
            "qualification__name"
        )
    )

    programming_min = config.programming_min_event_shifts
    programming_gate_met = total_shifts >= programming_min if programming_min else None
    programming_note = config.stats_programming_note

    # Full shift log: all confirmed past shifts, newest first, for the history table.
    all_past_shifts = list(
        base_qs.select_related("showing__event", "role").order_by("-showing__start")
    )

    # Keyholding shifts: roles flagged as keyholder_only.
    keyholder_shifts = list(
        base_qs.filter(role__keyholder_only=True).order_by("showing__start")
    )
    keyholder_first = keyholder_shifts[0] if keyholder_shifts else None
    twelve_months_ago = now - timedelta(days=365)
    keyholder_last_12m = sum(
        1 for e in keyholder_shifts if e.showing.start >= twelve_months_ago
    )
    _kh_by_year: dict = {}
    for entry in keyholder_shifts:
        yr = entry.showing.start.year
        _kh_by_year[yr] = _kh_by_year.get(yr, 0) + 1
    _kh_year_max = max(_kh_by_year.values()) if _kh_by_year else 1
    keyholder_by_year = [
        {"year": yr, "count": cnt, "pct": round(cnt * 100 / _kh_year_max)}
        for yr, cnt in sorted(_kh_by_year.items())
    ]

    return render(
        request,
        "volunteer_stats.html",
        {
            "volunteer": volunteer,
            "total_shifts": total_shifts,
            "all_shifts_count": all_shifts_count,
            "first_shift": first_shift,
            "last_shift": last_shift,
            "years_active": years_active,
            "shifts_by_year": shifts_by_year,
            "heatmap_rows": heatmap_rows,
            "heatmap_years": heatmap_years,
            "heatmap_max": heatmap_max,
            "year_max": year_max,
            "role_breakdown": role_breakdown,
            "role_first_dates": role_first_dates,
            "milestones": milestones,
            "training_records": training_records,
            "qualifications": qualifications,
            "programming_min": programming_min,
            "programming_gate_met": programming_gate_met,
            "programming_note": programming_note,
            "all_past_shifts": all_past_shifts,
            "upcoming_shifts": upcoming_shifts,
            "upcoming_by_month": upcoming_by_month,
            "two_weeks_ahead": two_weeks_ahead,
            "keyholder_shifts": keyholder_shifts,
            "keyholder_first": keyholder_first,
            "keyholder_last_12m": keyholder_last_12m,
            "keyholder_by_year": keyholder_by_year,
        },
    )


