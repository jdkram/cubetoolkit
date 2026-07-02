# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-written"

"""Itemised budget lines (estimate vs actual, by category) for an Event.

Replaces the "Budget template.xlsx" spreadsheet workflow (task 9.149).
Sits alongside the 9.54 "deal terms" cost_* fields on Event, not instead of
them: deal terms describe one negotiated headline cost; budget lines
describe everything else (catering, decoration, promotion, ...), plus the
Incoming side (ticket sales).
"""

from decimal import Decimal

from django.db import models

from .site_config import get_site_config


class EventBudgetLine(models.Model):
    """A single estimate/actual budget row for an Event.

    One row per category/item combination. estimate_source records where
    the estimate figure came from: a derived row (deal_terms/site_default)
    is re-populated by sync_budget_lines_for_event() whenever its source
    value changes; a manual row (including one explicitly overridden by a
    programmer) is never touched by sync.
    """

    DIRECTION_OUTGOING = "outgoing"
    DIRECTION_INCOME = "incoming"
    DIRECTION_CHOICES = [
        ("outgoing", "Outgoing"),
        ("incoming", "Incoming"),
    ]

    SOURCE_MANUAL = "manual"
    SOURCE_DEAL_TERMS = "deal_terms"
    SOURCE_SITE_DEFAULT = "site_default"
    SOURCE_CALCULATOR = "calculator"
    SOURCE_CHOICES = [
        ("manual", "Manual entry"),
        ("deal_terms", "Linked to deal terms"),
        ("site_default", "Site default"),
        ("calculator", "Break-even calculator"),
    ]

    event = models.ForeignKey(
        "diary.Event", on_delete=models.CASCADE, related_name="budget_lines"
    )
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES)
    category = models.CharField(max_length=64)
    item = models.CharField(max_length=128, blank=True)
    estimate_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    estimate_source = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default=SOURCE_MANUAL
    )
    actual_gbp = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(max_length=1024, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["direction", "order", "pk"]

    def __str__(self):
        label = f"{self.category} > {self.item}" if self.item else self.category
        return f"{self.event_id}: {label} ({self.direction})"


# Category templates, keyed by the event type used to select them. Each
# category is (name, [item names]) -- an empty item list means the category
# itself is the only row (free-entry, no item-level breakdown). These are
# collectively agreed with the Programming/Finance Collective, not something
# an individual programmer should be able to silently change, so they live
# here as a Python constant rather than on SiteConfiguration.
BUDGET_CATEGORY_TEMPLATES = {
    "film": [
        ("Programming", ["Licence", "DVD/ Blu-ray"]),
        ("Catering", []),
        ("Decoration", []),
        ("Merch", []),
        ("Promotion", []),
        ("Misc.", []),
    ],
    "music_gig": [
        ("Acts/ Performers", ["Hire fee", "Travel", "Accommodation", "Rider"]),
        ("Fees", ["Late night licence", "Door staff"]),
        ("Catering", []),
        ("Decoration", []),
        ("Merch", []),
        ("Promotion", []),
        ("Volunteer costs", []),
        ("Misc.", []),
    ],
    "other_public_event": [
        ("Acts/ Performers", []),
        ("Catering", []),
        ("Decoration", []),
        ("Merch", []),
        ("Promotion", []),
        ("Cafe & bar", []),
        ("Volunteer costs", []),
        ("Misc.", []),
    ],
}
INCOME_CATEGORY_TEMPLATE = [("Ticket sales", [])]


def _budget_event_type(event) -> str:
    """Map an Event to a BUDGET_CATEGORY_TEMPLATES key.

    "film" (tag slug "film") is a proven convention used elsewhere
    (edit_views/events.py). "music_gig" relies on EventTag.filter_group ==
    "music" -- a real field, but not yet confirmed as the live convention
    for classifying gigs specifically (as opposed to driving the public
    programme filter buttons). TODO(jonny): confirm the music tag
    convention against live EventTag data. There is no "volunteer only
    event" detection yet -- such events fall into "other_public_event",
    which is harmless (real categories a programmer can just ignore).
    """
    if event.tags.filter(slug="film").exists():
        return "film"
    if event.tags.filter(filter_group="music").exists():
        return "music_gig"
    return "other_public_event"


def _derive_estimate(event, category, item, site_config):
    """Return (estimate_gbp, estimate_source, notes) for a template row.

    notes is only ever non-None for the Rider row, where the deal-terms
    text is pre-filled rather than an estimate figure -- there is no GBP
    amount to derive there, only free text, but the row is still marked
    "deal_terms" so the same override affordance applies.
    """
    if category == "Acts/ Performers" and item == "Hire fee":
        if event.cost_type in (
            event.COST_TYPE_PERFORMER_FEE,
            event.COST_TYPE_VENUE_HIRE,
        ):
            value = event.cost_total_gbp or event.cost_flat_fee_gbp
            if value is not None:
                return value, EventBudgetLine.SOURCE_DEAL_TERMS, None
    elif category == "Programming" and item == "Licence":
        if (
            event.cost_type == event.COST_TYPE_FILM_LICENSE
            and event.cost_flat_fee_gbp is not None
        ):
            return (
                event.cost_flat_fee_gbp,
                EventBudgetLine.SOURCE_DEAL_TERMS,
                None,
            )
    elif category == "Acts/ Performers" and item == "Rider":
        if event.cost_rider_notes:
            return None, EventBudgetLine.SOURCE_DEAL_TERMS, event.cost_rider_notes
    elif category == "Fees" and item == "Late night licence":
        if site_config.late_licence_fee_gbp is not None:
            return (
                site_config.late_licence_fee_gbp,
                EventBudgetLine.SOURCE_SITE_DEFAULT,
                None,
            )
    return None, EventBudgetLine.SOURCE_MANUAL, None


def sync_budget_lines_for_event(event) -> None:
    """Ensure EventBudgetLine rows exist for event's category template.

    Never deletes or blanks an existing row -- re-tagging an event to a
    different type just adds the new type's rows alongside any already
    filled in for the old type. Re-derives estimate_gbp for rows whose
    estimate_source is not "manual", in case the source value (e.g.
    cost_total_gbp) changed since the row was created; a row a programmer
    has overridden to "manual" is never touched again. Ad-hoc items added
    via "Add item" (not part of the template) are untouched either way.
    """
    site_config = get_site_config()
    event_type = _budget_event_type(event)
    template = BUDGET_CATEGORY_TEMPLATES[event_type]

    expected = []
    for category, items in template:
        if items:
            for item in items:
                expected.append(
                    (EventBudgetLine.DIRECTION_OUTGOING, category, item)
                )
        else:
            expected.append((EventBudgetLine.DIRECTION_OUTGOING, category, ""))
    for category, items in INCOME_CATEGORY_TEMPLATE:
        expected.append((EventBudgetLine.DIRECTION_INCOME, category, ""))

    existing = {
        (line.direction, line.category, line.item): line
        for line in event.budget_lines.all()
    }

    for order, (direction, category, item) in enumerate(expected):
        key = (direction, category, item)
        line = existing.get(key)
        if line is None:
            estimate_gbp, estimate_source, notes = _derive_estimate(
                event, category, item, site_config
            )
            EventBudgetLine.objects.create(
                event=event,
                direction=direction,
                category=category,
                item=item,
                estimate_gbp=estimate_gbp,
                estimate_source=estimate_source,
                notes=notes or "",
                order=order,
            )
        elif line.estimate_source != EventBudgetLine.SOURCE_MANUAL:
            estimate_gbp, estimate_source, notes = _derive_estimate(
                event, category, item, site_config
            )
            update_fields = []
            if line.estimate_gbp != estimate_gbp:
                line.estimate_gbp = estimate_gbp
                update_fields.append("estimate_gbp")
            if notes is not None and line.notes != notes:
                line.notes = notes
                update_fields.append("notes")
            if update_fields:
                line.save(update_fields=update_fields)
