# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.db import models
from django.contrib.auth.models import User


class RoomNote(models.Model):
    room_id = models.CharField(max_length=100, unique=True)
    body = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        db_table = "labs_room_notes"

    def __str__(self):
        return f"{self.room_id}: {self.body[:60]}"


class DonationItem(models.Model):
    STATUS_NOT_NEEDED = "not_needed"
    STATUS_CHECK_FIRST = "check_first"
    STATUS_WANTED = "wanted"
    STATUS_CHOICES = [
        (STATUS_WANTED, "Wanted"),
        (STATUS_CHECK_FIRST, "Check first"),
        (STATUS_NOT_NEEDED, "Not needed"),
    ]

    name = models.CharField(max_length=128)
    category = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_WANTED)
    notes = models.TextField(blank=True, default="")
    contact = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Contact for this item — leave blank to use the site default.",
    )
    display_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "labs_donation_items"
        ordering = ["category", "display_order", "name"]

    def __str__(self):
        return self.name


class Job(models.Model):
    URGENCY_LOW = "low"
    URGENCY_MEDIUM = "medium"
    URGENCY_HIGH = "high"
    URGENCY_CHOICES = [
        (URGENCY_HIGH, "Urgent"),
        (URGENCY_MEDIUM, "Soon"),
        (URGENCY_LOW, "Whenever"),
    ]

    title = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    location = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Where the job needs to happen, e.g. 'Main hall', 'Kitchen'.",
    )
    skills = models.TextField(
        blank=True,
        default="",
        help_text="What skills or tools are needed.",
    )
    keyholder_required = models.BooleanField(default=False)
    urgency = models.CharField(max_length=16, choices=URGENCY_CHOICES, default=URGENCY_LOW)
    posted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="posted_jobs"
    )
    posted_at = models.DateTimeField(auto_now_add=True)
    claimed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claimed_jobs",
    )
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "labs_jobs"
        ordering = ["-done", "urgency", "-posted_at"]

    def __str__(self):
        return self.title
