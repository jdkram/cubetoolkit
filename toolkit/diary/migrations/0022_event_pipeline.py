"""
Migration: event programming pipeline fields.

Adds to Event:
  - status (proposed/approved/rejected, default proposed)
  - created_by / proposed_by / keyholder_confirmed (FK to auth.User)
  - rejection_reason / meeting_notes (TextField)
  - cost_hire / cost_tech / cost_performer / cost_accommodation /
    cost_travel / cost_food / cost_other / revenue_expected (DecimalField)
  - deal_type (CharField)
  - tech_requirements (TextField)

Adds to Showing:
  - date_note (CharField) — free-text placeholder when start is TBC
  - Makes start nullable

Adds to SiteConfiguration:
  - programming_etiquette_url
  - finance_referral_threshold_standard
  - finance_referral_threshold_music

Data migration: events with at least one confirmed showing → status='approved';
all others → status='proposed' (already the default).
"""

import django.db.models.deletion
import toolkit.diary.models
from django.conf import settings
from django.db import migrations, models


def _set_existing_event_statuses(apps, schema_editor):
    """
    Events that already have at least one confirmed showing → approved.
    All others stay as proposed (the column default).
    """
    Event = apps.get_model("diary", "Event")
    Showing = apps.get_model("diary", "Showing")

    confirmed_event_ids = set(
        Showing.objects.filter(confirmed=True).values_list("event_id", flat=True)
    )
    if confirmed_event_ids:
        Event.objects.filter(pk__in=confirmed_event_ids).update(status="approved")


class Migration(migrations.Migration):

    dependencies = [
        ("diary", "0021_volunteer_event_mark"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── Event: pipeline status ────────────────────────────────────────────
        migrations.AddField(
            model_name="event",
            name="status",
            field=models.CharField(
                choices=[
                    ("proposed", "Proposed"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                db_index=True,
                default="proposed",
                help_text="Pipeline status: where this event is in the approval process.",
                max_length=16,
            ),
        ),
        # ── Event: people fields ──────────────────────────────────────────────
        migrations.AddField(
            model_name="event",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who created this event record. Set automatically.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="events_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="proposed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="Programmer responsible for this proposal. Defaults to who created it, but can be changed.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="events_proposed",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="keyholder_confirmed",
            field=models.ForeignKey(
                blank=True,
                help_text="Keyholder who has agreed to cover this event.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="events_keyholder",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # ── Event: meeting notes / rejection ─────────────────────────────────
        migrations.AddField(
            model_name="event",
            name="rejection_reason",
            field=models.TextField(
                blank=True,
                help_text="Reason recorded when the meeting rejected this proposal.",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="meeting_notes",
            field=models.TextField(
                blank=True,
                help_text="Notes recorded during the meeting discussion of this proposal.",
            ),
        ),
        # ── Event: cost fields ────────────────────────────────────────────────
        migrations.AddField(
            model_name="event",
            name="cost_hire",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Hire cost (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_tech",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Technical costs (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_performer",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Performer fee (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_accommodation",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Accommodation (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_travel",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Travel (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_food",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Food / hospitality (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="cost_other",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Other costs (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="revenue_expected",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Expected revenue (£)",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="deal_type",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "—"),
                    ("door-split", "Door split"),
                    ("flat-fee", "Flat fee"),
                    ("guarantee", "Guarantee"),
                    ("free", "Free"),
                    ("other", "Other"),
                ],
                max_length=32,
                verbose_name="Deal type",
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="tech_requirements",
            field=models.TextField(
                blank=True,
                help_text="What technical setup does this event need? (PA, projector, live mixing, etc.)",
                verbose_name="Tech requirements",
            ),
        ),
        # ── Showing: date-TBC support ─────────────────────────────────────────
        migrations.AddField(
            model_name="showing",
            name="date_note",
            field=models.CharField(
                blank=True,
                help_text="Free-text placeholder when no specific date is set, e.g. 'a Friday in May'.",
                max_length=256,
            ),
        ),
        migrations.AlterField(
            model_name="showing",
            name="start",
            field=toolkit.diary.models.FutureDateTimeField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
        # ── SiteConfiguration: pipeline settings ─────────────────────────────
        migrations.AddField(
            model_name="siteconfiguration",
            name="programming_etiquette_url",
            field=models.URLField(
                blank=True,
                default="",
                max_length=500,
                help_text="Link to the programming etiquette guide. Shown on event creation and in the programming queue.",
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="finance_referral_threshold_standard",
            field=models.PositiveSmallIntegerField(
                default=500,
                help_text="Cost threshold (£) above which a standard event requires Finance Collective sign-off.",
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="finance_referral_threshold_music",
            field=models.PositiveSmallIntegerField(
                default=750,
                help_text="Cost threshold (£) above which a music event requires Finance Collective sign-off.",
            ),
        ),
        # ── Data migration: set status on existing events ─────────────────────
        migrations.RunPython(
            _set_existing_event_statuses,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
