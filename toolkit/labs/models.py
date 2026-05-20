# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.db import models
from django.contrib.auth.models import User

COLLECTIVE_PALETTE = [
    # Blues & navies
    ("#0d2b45", "Deep Navy"),
    ("#1a3a5c", "Navy"),
    ("#1a3a6b", "Cobalt"),
    ("#2d3a7a", "Indigo"),
    # Teals
    ("#0d4f4f", "Dark Teal"),
    ("#1a5c72", "Teal"),
    ("#2a5a5a", "Petrol"),
    ("#1a6b5a", "Emerald"),
    # Greens
    ("#1a4a3a", "Spruce"),
    ("#1a5c48", "Jade"),
    ("#2d5a2a", "Forest"),
    ("#3a5a1a", "Fern"),
    ("#4a5a20", "Olive"),
    # Purples & violets
    ("#3d1f6e", "Deep Purple"),
    ("#4a2060", "Aubergine"),
    ("#523070", "Plum"),
    ("#6b3070", "Violet"),
    # Reds & crimsons
    ("#5a1a3a", "Burgundy"),
    ("#6b1a2a", "Claret"),
    ("#7a2a4a", "Crimson"),
    ("#8b2020", "Deep Red"),
    # Browns & ambers
    ("#4a2a0d", "Dark Brown"),
    ("#5a3a1a", "Chestnut"),
    ("#6b4428", "Umber"),
    ("#7a3a2a", "Rust"),
    ("#7a4a1a", "Ochre"),
    # Neutrals
    ("#2a3540", "Dark Slate"),
    ("#343a40", "Slate"),
]


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
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Public-facing notes shown on the donations page.",
    )
    internal_notes = models.TextField(
        blank=True,
        default="",
        help_text="Internal notes visible only to volunteers (e.g. storage location, condition requirements).",
    )
    contact = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Contact for this item — leave blank to use the site default.",
    )
    display_order = models.IntegerField(default=0)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_edited_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        db_table = "labs_donation_items"
        ordering = ["category", "display_order", "name"]

    def __str__(self):
        return self.name


class Collective(models.Model):
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=64, unique=True)
    colour = models.CharField(max_length=7, default="#343a40")
    display_order = models.IntegerField(default=0, help_text="Lower numbers appear first.")
    active = models.BooleanField(default=True)
    volunteer_count = models.CharField(
        max_length=256, blank=True, default="",
        help_text="Descriptive volunteer count shown on the collectives page.",
    )
    about = models.TextField(blank=True, default="")
    roles = models.TextField(blank=True, default="", verbose_name="Roles and tasks")
    organising = models.TextField(blank=True, default="", verbose_name="How they meet and organise")
    proud_of = models.TextField(blank=True, default="", verbose_name="What they're most proud of")
    get_involved = models.TextField(blank=True, default="", verbose_name="How to get involved")
    contact = models.CharField(
        max_length=256, blank=True, default="",
        help_text="Contact email or address shown at the bottom of the card.",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "labs_collectives"
        ordering = ["display_order", "name"]

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

    LOCATION_BUILDING = "building"
    LOCATION_REMOTE = "remote"
    LOCATION_BOTH = "both"
    LOCATION_CHOICES = [
        (LOCATION_BUILDING, "In building"),
        (LOCATION_REMOTE, "Remote"),
        (LOCATION_BOTH, "Both"),
    ]

    # What and where
    title = models.CharField(max_length=128)
    area = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Area or location, e.g. 'Kitchen', 'Roof', 'Anywhere'.",
    )
    description = models.TextField(blank=True, default="", help_text="Full description of the issue or task.")
    plan_status = models.TextField(blank=True, default="", help_text="Current plan or status update.")

    # Flags
    safety_risk = models.BooleanField(default=False, help_text="Is there an immediate safety risk?")
    skill_needed = models.BooleanField(default=False, help_text="Does this require a specific skill or trade?")
    keyholder_required = models.BooleanField(default=False)
    urgency = models.CharField(max_length=16, choices=URGENCY_CHOICES, default=URGENCY_LOW)
    location_type = models.CharField(
        max_length=16,
        choices=LOCATION_CHOICES,
        default=LOCATION_BUILDING,
        help_text="Can this be done remotely, or does it require being in the building?",
    )

    # People
    posted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="posted_jobs"
    )
    reporter_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Name of the person who reported the issue and can provide more detail.",
    )
    claimed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="claimed_jobs",
    )

    # Dates
    posted_at = models.DateTimeField(auto_now_add=True)

    # Resolution
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "labs_jobs"

    def __str__(self):
        return self.title


class LoftItem(models.Model):
    zone_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    added_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="loft_items"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "labs_loft_items"
        ordering = ["zone_id", "added_at"]

    def __str__(self):
        return f"{self.zone_id}: {self.name}"


class AreaPhoto(models.Model):
    """One reference photo per mapped area (room or loft zone)."""

    area_id = models.CharField(max_length=100, unique=True)
    image = models.ImageField(upload_to="area-photos/")
    caption = models.CharField(max_length=200, blank=True, default="")
    uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "labs_area_photos"

    def __str__(self) -> str:
        return f"Photo for {self.area_id}"


class LoftItemPhoto(models.Model):
    item = models.ForeignKey(LoftItem, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="loft-photos/")
    caption = models.CharField(max_length=200, blank=True, default="")
    uploaded_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "labs_loft_item_photos"
        ordering = ["uploaded_at"]

    def __str__(self):
        return f"Photo for {self.item.name} ({self.pk})"
