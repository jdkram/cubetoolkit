# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django.db import models
from django.contrib.auth.models import User

from toolkit.diary.validators import validate_event_link_url

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
    sample_role = models.TextField(
        blank=True, default="",
        verbose_name="Sample role",
        help_text="A short, concrete example of what a member might actually do — shown to help people decide whether to join.",
    )
    contact = models.CharField(
        max_length=256, blank=True, default="",
        help_text="Contact email or address shown at the bottom of the card.",
    )
    invite_only = models.BooleanField(
        default=False,
        help_text="If set, volunteers cannot self-join — membership is managed by admins only.",
    )
    listed_publicly = models.BooleanField(
        default=False,
        help_text="Include this collective on the public /labs/collectives/public/ page. Requires public_copy to be set.",
    )
    public_copy = models.TextField(
        blank=True, default="",
        verbose_name="Public description",
        help_text="Short description for the public directory (100–300 characters). Leave blank to exclude from the public page even if listed_publicly is checked.",
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


class CollectiveLink(models.Model):
    """A named link attached to a collective — WhatsApp group, Linktree, shared pad, etc.

    Uses the same domain allowlist as EventLink to keep things consistent.
    Max 3 per collective enforced by the formset.
    """

    collective = models.ForeignKey(
        Collective,
        on_delete=models.CASCADE,
        related_name="links",
    )
    label = models.CharField(
        max_length=80,
        help_text="Short name shown on the link chip, e.g. 'WhatsApp group' or 'Linktree'.",
    )
    url = models.URLField(
        max_length=500,
        validators=[validate_event_link_url],
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.label} ({self.collective_id})"


class CollectiveRole(models.Model):
    """A structured role within a collective — shown to help volunteers decide whether to join."""

    collective = models.ForeignKey(
        Collective, on_delete=models.CASCADE, related_name="defined_roles"
    )
    title = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    time_commitment = models.CharField(
        max_length=128, blank=True, default="",
        help_text="e.g. '~3hrs/month', 'weekly Tuesday evenings'",
    )
    getting_started = models.TextField(
        blank=True, default="",
        help_text="First concrete step for someone interested in this role.",
    )
    needs_volunteers = models.BooleanField(
        default=False,
        help_text="Flag this role as actively seeking more people (shown as a badge).",
    )
    open_to_new_volunteers = models.BooleanField(
        default=True,
        help_text="Uncheck if this role is currently invite-only or full.",
    )
    display_order = models.IntegerField(default=0)

    class Meta:
        ordering = ["display_order", "pk"]

    def __str__(self):
        return f"{self.title} ({self.collective})"


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


class Bulletin(models.Model):
    """Operational notice shown on the labs bulletin board and dashboard banner.

    Posted by any logged-in user; pinned / expired by Programmer+; deleted by
    Panopticon. Acknowledgement is tracked per-User (not Volunteer) via
    BulletinRead.
    """

    title = models.CharField(max_length=200)
    body = models.TextField()
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "Leave blank to use the site default (bulletin_default_expiry_days). "
            "Set explicitly to override."
        ),
    )
    pinned = models.BooleanField(
        default=False,
        help_text=(
            "Pinned bulletins appear at the top of the board regardless of date. "
            "Programmer+ only."
        ),
    )

    class Meta:
        db_table = "labs_bulletins"
        ordering = ["-pinned", "-created_at"]

    def __str__(self):
        return self.title

    def effective_expiry(self):
        """Return the datetime at which this bulletin becomes inactive, or None
        if it never expires (site default is 0 and no explicit expiry).
        """
        from django.utils import timezone
        from toolkit.diary.models import get_site_config

        if self.expires_at:
            return self.expires_at
        days = get_site_config().bulletin_default_expiry_days
        if days == 0:
            return None
        return self.created_at + datetime.timedelta(days=days)

    def is_active(self):
        from django.utils import timezone

        expiry = self.effective_expiry()
        if expiry is None:
            return True
        return expiry > timezone.now()


class BulletinRead(models.Model):
    bulletin = models.ForeignKey(Bulletin, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "labs_bulletin_reads"
        unique_together = [("bulletin", "user")]

    def __str__(self):
        return f"{self.user} read {self.bulletin_id} at {self.read_at:%Y-%m-%d %H:%M}"


# ── Shopping list (consumables) ───────────────────────────────────────────────

class ConsumableItem(models.Model):
    CATEGORY_CLEANING = "cleaning"
    CATEGORY_STATIONERY = "stationery"
    CATEGORY_KITCHEN = "kitchen"
    CATEGORY_SNACKS = "snacks"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_CLEANING, "Cleaning"),
        (CATEGORY_STATIONERY, "Stationery"),
        (CATEGORY_KITCHEN, "Kitchen"),
        (CATEGORY_SNACKS, "Cinema Snacks"),
        (CATEGORY_OTHER, "Other"),
    ]

    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "labs_consumable_items"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    @property
    def open_flag(self):
        return self.need_flags.filter(resolved_at__isnull=True).first()


class SupplierRecord(models.Model):
    item = models.ForeignKey(ConsumableItem, on_delete=models.CASCADE, related_name="suppliers")
    supplier_name = models.CharField(max_length=100)
    product_code = models.CharField(max_length=100, blank=True, default="")
    product_url = models.URLField(blank=True, default="")
    unit_desc = models.CharField(max_length=200, blank=True, default="", help_text="e.g. '6-pack', '5L'")
    approx_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    ordering_notes = models.TextField(blank=True, default="")
    account_holder = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supplier_accounts",
        help_text="Volunteer who holds the login for this supplier account.",
    )
    account_notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "labs_supplier_records"
        ordering = ["supplier_name"]

    def __str__(self):
        return f"{self.supplier_name} ({self.item.name})"


class NeedFlag(models.Model):
    item = models.ForeignKey(ConsumableItem, on_delete=models.CASCADE, related_name="need_flags")
    flagged_by = models.ForeignKey(
        "members.Volunteer", null=True, blank=True, on_delete=models.SET_NULL, related_name="flagged_needs"
    )
    flagged_at = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=300, blank=True, default="")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_flags",
    )

    class Meta:
        db_table = "labs_need_flags"
        ordering = ["-flagged_at"]

    def __str__(self):
        return f"{self.item.name} flagged at {self.flagged_at:%Y-%m-%d %H:%M}"

    @property
    def is_resolved(self):
        return self.resolved_at is not None


class ProcurementPledge(models.Model):
    need_flag = models.OneToOneField(NeedFlag, on_delete=models.CASCADE, related_name="pledge")
    pledged_by = models.ForeignKey(
        "members.Volunteer", null=True, blank=True, on_delete=models.SET_NULL, related_name="pledges"
    )
    pledged_at = models.DateTimeField(auto_now_add=True)
    eta_date = models.DateField(null=True, blank=True)
    eta_notes = models.CharField(max_length=200, blank=True, default="", help_text="e.g. 'Friday cleaning club'")
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "labs_procurement_pledges"

    def __str__(self):
        return f"Pledge by {self.pledged_by} for {self.need_flag.item.name}"


# ── Loft inventory ─────────────────────────────────────────────────────────────

class FoundItem(models.Model):
    TYPE_FOUND = "found"
    TYPE_LOST = "lost"
    TYPE_CHOICES = [
        (TYPE_FOUND, "Found item"),
        (TYPE_LOST, "Lost report"),
    ]

    STATUS_UNCLAIMED = "unclaimed"
    STATUS_CLAIMED = "claimed"
    STATUS_DISPOSED = "disposed"
    STATUS_CHOICES = [
        (STATUS_UNCLAIMED, "Unclaimed"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_DISPOSED, "Disposed"),
    ]

    DISPOSAL_BINNED = "binned"
    DISPOSAL_DONATED = "donated"
    DISPOSAL_RETURNED = "returned"
    DISPOSAL_OTHER = "other"
    DISPOSAL_CHOICES = [
        (DISPOSAL_BINNED, "Binned"),
        (DISPOSAL_DONATED, "Donated"),
        (DISPOSAL_RETURNED, "Returned to owner"),
        (DISPOSAL_OTHER, "Other"),
    ]

    report_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default=TYPE_FOUND)
    description = models.CharField(max_length=200)
    location_found = models.CharField(max_length=100)
    found_on = models.DateField(default=datetime.date.today)
    logged_by = models.CharField(max_length=100)
    reporter_contact = models.TextField(
        blank=True,
        default="",
        help_text="Private contact details for the person who lost the item. Not shown in the list view.",
    )
    photo = models.ImageField(upload_to="lost-and-found/", blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_UNCLAIMED)
    claimed_by = models.CharField(max_length=200, blank=True, default="")
    claimed_on = models.DateField(null=True, blank=True)
    disposed_on = models.DateField(null=True, blank=True)
    disposal_method = models.CharField(max_length=12, choices=DISPOSAL_CHOICES, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "labs_found_items"
        ordering = ["-found_on", "-pk"]

    def __str__(self):
        return f"L-{self.pk:03d}: {self.description}"

    @property
    def label_id(self):
        return f"L-{self.pk:03d}"

    @property
    def is_overdue(self):
        from toolkit.diary.models import get_site_config
        if self.report_type != self.TYPE_FOUND or self.status != self.STATUS_UNCLAIMED:
            return False
        retain_days = get_site_config().lost_and_found_retain_days
        if retain_days <= 0:
            return False
        threshold = datetime.date.today() - datetime.timedelta(days=retain_days)
        return self.found_on <= threshold

    def status_display(self):
        """Context-appropriate status label depending on report type."""
        if self.report_type == self.TYPE_LOST:
            return {
                self.STATUS_UNCLAIMED: "Seeking",
                self.STATUS_CLAIMED: "Reunited",
                self.STATUS_DISPOSED: "Closed",
            }.get(self.status, self.status)
        return self.get_status_display()


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


class ExchangeItem(models.Model):
    """
    Community exchange — covers both lending (borrow + return) and giving (free to a good home).
    listing_type distinguishes the two flows; status meanings differ accordingly.
    """

    TYPE_LEND = "lend"
    TYPE_GIVE = "give"
    TYPE_SHARE = "share"
    TYPE_CHOICES = [
        (TYPE_LEND, "🔧 Lend — borrow and return"),
        (TYPE_GIVE, "🎁 Give away — free to a good home"),
        (TYPE_SHARE, "🥔 Share — help yourself to some"),
    ]

    CATEGORY_TOOLS = "tools"
    CATEGORY_KITCHEN = "kitchen"
    CATEGORY_AV = "av"
    CATEGORY_CLOTHING = "clothing"
    CATEGORY_BOOKS = "books"
    CATEGORY_GARDEN = "garden"
    CATEGORY_FURNITURE = "furniture"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_TOOLS, "Tools"),
        (CATEGORY_KITCHEN, "Kitchen"),
        (CATEGORY_AV, "AV & tech"),
        (CATEGORY_CLOTHING, "Clothing"),
        (CATEGORY_BOOKS, "Books & media"),
        (CATEGORY_GARDEN, "Garden"),
        (CATEGORY_FURNITURE, "Furniture"),
        (CATEGORY_OTHER, "Other"),
    ]

    CONDITION_NEW = "new"
    CONDITION_GOOD = "good"
    CONDITION_FAIR = "fair"
    CONDITION_ATTENTION = "attention"
    CONDITION_CHOICES = [
        (CONDITION_NEW, "New"),
        (CONDITION_GOOD, "Good"),
        (CONDITION_FAIR, "Fair"),
        (CONDITION_ATTENTION, "Needs attention"),
    ]

    OWNER_COLLECTIVE = "collective"
    OWNER_VOLUNTEER = "volunteer"
    OWNER_CHOICES = [
        (OWNER_COLLECTIVE, "S+S collective"),
        (OWNER_VOLUNTEER, "Volunteer"),
    ]

    # Status meanings by type:
    #   lend:  available → on_loan → available (cycle); withdrawn to remove
    #   give:  available → claimed; withdrawn to remove
    #   share: available → all_gone; withdrawn to remove
    STATUS_AVAILABLE = "available"
    STATUS_ON_LOAN = "on_loan"
    STATUS_CLAIMED = "claimed"
    STATUS_ALL_GONE = "all_gone"
    STATUS_MISSING = "missing"
    STATUS_WITHDRAWN = "withdrawn"
    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_ON_LOAN, "On loan"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_ALL_GONE, "All gone"),
        (STATUS_MISSING, "Missing"),
        (STATUS_WITHDRAWN, "Withdrawn"),
    ]

    listing_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default=TYPE_GIVE)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    condition = models.CharField(max_length=16, choices=CONDITION_CHOICES, default=CONDITION_GOOD)
    owner_type = models.CharField(max_length=16, choices=OWNER_CHOICES, default=OWNER_VOLUNTEER)
    owner_volunteer = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="exchange_items",
        help_text="Only visible to logged-in users. Set when owner is a volunteer.",
    )
    location_notes = models.CharField(
        max_length=256,
        blank=True,
        default="",
        help_text="Where to collect or arrange pickup — e.g. 'Bring to the next event' or 'Ask at the bar'.",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_AVAILABLE)
    quantity = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="How much is there? e.g. 'about 10kg', '3 trays', 'a big bag'. Share listings only.",
    )
    available_until = models.DateField(
        null=True,
        blank=True,
        help_text="Optional — show urgency. Useful for food that will go off. Share listings only.",
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Quirks, usage notes, or anything relevant to whoever borrows/takes it.",
    )
    image = models.ImageField(upload_to="exchange/", blank=True)
    active = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    borrowed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    borrowed_by_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Free-text name for verbal/in-person loans. Shown instead of username if set.",
    )
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "labs_exchange_items"
        ordering = ["listing_type", "category", "name"]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        return self.status == self.STATUS_AVAILABLE

    @property
    def borrower_display(self):
        """Best available name for who currently has the item."""
        if self.borrowed_by_name:
            return self.borrowed_by_name
        if self.borrowed_by_id:
            try:
                vol = self.borrowed_by.volunteer
                return vol.member.name
            except Exception:
                pass
            return self.borrowed_by.username
        return None

    def status_label(self):
        """Human label that accounts for listing_type context."""
        if self.listing_type == self.TYPE_LEND:
            return {
                self.STATUS_AVAILABLE: "Available to borrow",
                self.STATUS_ON_LOAN: "On loan",
                self.STATUS_CLAIMED: "Claimed",
                self.STATUS_ALL_GONE: "All gone",
                self.STATUS_MISSING: "Missing",
                self.STATUS_WITHDRAWN: "Withdrawn",
            }.get(self.status, self.get_status_display())
        if self.listing_type == self.TYPE_SHARE:
            return {
                self.STATUS_AVAILABLE: "Available — help yourself",
                self.STATUS_ON_LOAN: "In progress",
                self.STATUS_CLAIMED: "All gone",
                self.STATUS_ALL_GONE: "All gone",
                self.STATUS_WITHDRAWN: "No longer available",
            }.get(self.status, self.get_status_display())
        return {
            self.STATUS_AVAILABLE: "Available",
            self.STATUS_ON_LOAN: "On loan",
            self.STATUS_CLAIMED: "Gone to a good home",
            self.STATUS_ALL_GONE: "All gone",
            self.STATUS_WITHDRAWN: "No longer available",
        }.get(self.status, self.get_status_display())
