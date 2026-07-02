# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from dateutil.relativedelta import relativedelta
from django.db import models


class MaintenanceTask(models.Model):
    CATEGORY_SECURITY_FIRE = "security_fire"
    CATEGORY_HVAC = "hvac"
    CATEGORY_COMPLIANCE_LEGAL = "compliance_legal"
    CATEGORY_UTILITIES = "utilities"
    CATEGORY_PROPERTY = "property"
    CATEGORY_DIGITAL_AV = "digital_av"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_SECURITY_FIRE, "Security & Fire"),
        (CATEGORY_HVAC, "HVAC"),
        (CATEGORY_COMPLIANCE_LEGAL, "Compliance & Legal"),
        (CATEGORY_UTILITIES, "Utilities"),
        (CATEGORY_PROPERTY, "Property"),
        (CATEGORY_DIGITAL_AV, "Digital & AV"),
        (CATEGORY_OTHER, "Other"),
    ]

    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_QUARTERLY = "quarterly"
    FREQUENCY_BIANNUAL = "biannual"
    FREQUENCY_ANNUAL = "annual"
    FREQUENCY_THREE_YEARLY = "three_yearly"
    FREQUENCY_BESPOKE = "bespoke"
    FREQUENCY_CHOICES = [
        (FREQUENCY_MONTHLY, "Monthly"),
        (FREQUENCY_QUARTERLY, "Quarterly"),
        (FREQUENCY_BIANNUAL, "Twice a year"),
        (FREQUENCY_ANNUAL, "Annual"),
        (FREQUENCY_THREE_YEARLY, "Every 3 years"),
        (FREQUENCY_BESPOKE, "Bespoke / other"),
    ]

    FREQUENCY_PERIODS = {
        FREQUENCY_MONTHLY: relativedelta(months=1),
        FREQUENCY_QUARTERLY: relativedelta(months=3),
        FREQUENCY_BIANNUAL: relativedelta(months=6),
        FREQUENCY_ANNUAL: relativedelta(years=1),
        FREQUENCY_THREE_YEARLY: relativedelta(years=3),
    }

    STATUS_OVERDUE = "overdue"
    STATUS_DUE_SOON = "due_soon"
    STATUS_OK = "ok"

    name = models.CharField(max_length=128)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    frequency = models.CharField(max_length=16, choices=FREQUENCY_CHOICES, default=FREQUENCY_ANNUAL)
    frequency_notes = models.CharField(
        max_length=128, blank=True, default="", help_text="For bespoke or unusual patterns."
    )
    contractor = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Name of service provider if external; blank for volunteer-delivered tasks.",
    )
    keyholder_required = models.BooleanField(default=False)
    skills_required = models.TextField(blank=True, default="", help_text="What you need to know or be trained in.")
    time_commitment = models.CharField(
        max_length=128, blank=True, default="", help_text="e.g. '~2 hours', 'Half a day including travel'."
    )
    nextcloud_link = models.URLField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True, help_text="Retire tasks without losing history.")

    committed_to = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="committed_maintenance_tasks",
        help_text="Who has said they'll do the next occurrence, if anyone.",
    )
    committed_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def latest_record(self):
        # `records` is prefetched/ordered by -completed_date where possible;
        # falling back to a query keeps this correct even without prefetch.
        records = getattr(self, "_prefetched_objects_cache", {}).get("records")
        if records is not None:
            return records[0] if records else None
        return self.records.order_by("-completed_date").first()

    @property
    def next_due(self):
        latest = self.latest_record
        if latest is not None and latest.next_due_override is not None:
            return latest.next_due_override
        period = self.FREQUENCY_PERIODS.get(self.frequency)
        if period is None:
            # Bespoke frequency with no override: nothing to calculate against.
            return None
        base = latest.completed_date if latest is not None else datetime.date.today()
        return base + period

    @property
    def status(self):
        next_due = self.next_due
        if next_due is None:
            return self.STATUS_OK
        today = datetime.date.today()
        if next_due < today:
            return self.STATUS_OVERDUE
        if next_due <= today + datetime.timedelta(days=28):
            return self.STATUS_DUE_SOON
        return self.STATUS_OK

    @property
    def stale_commitment(self):
        """A commitment is stale if it predates the task's frequency period and
        nothing has been completed since it was made."""
        if self.committed_on is None:
            return False
        latest = self.latest_record
        if latest is not None and latest.completed_date >= self.committed_on:
            return False
        period = self.FREQUENCY_PERIODS.get(self.frequency)
        if period is None:
            return False
        return self.committed_on + period < datetime.date.today()


class MaintenanceRecord(models.Model):
    task = models.ForeignKey(MaintenanceTask, on_delete=models.CASCADE, related_name="records")
    completed_date = models.DateField()
    completed_by = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_maintenance_records",
    )
    completed_by_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="For contractor completions or cases where no toolkit account exists.",
    )
    notes = models.TextField(blank=True, default="")
    next_due_override = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-completed_date"]

    def __str__(self):
        return f"{self.task.name} — {self.completed_date}"
