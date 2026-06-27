import logging

from django.db import models

from .event import Event

logger = logging.getLogger(__name__)


class Role(models.Model):
    name = models.CharField(max_length=64, unique=True)

    standard = models.BooleanField(
        default=False,
        help_text="Should this role be presented in"
        " the main list of roles for events",
    )

    # Allow role to be edited/deleted
    read_only = models.BooleanField(default=False)

    description = models.TextField(
        blank=True,
        default="",
        help_text="Guidance for volunteers about this role: what's involved, "
        "accessibility notes, links to guides, training requirements, etc.",
    )

    archived = models.BooleanField(
        default=False,
        help_text="Archived roles are hidden from normal use. "
        "Roles used in past rota entries cannot be permanently deleted.",
    )

    is_one_shot = models.BooleanField(
        default=False,
        help_text="One-shot roles are created on the fly for a specific showing "
        "and do not appear in the permanent roles list.",
    )

    beginner_friendly = models.BooleanField(
        default=False,
        help_text="Show the 🌱 good-first-role badge on the rota — "
        "great for new volunteers.",
    )

    wheelchair_accessible = models.BooleanField(
        default=False,
        help_text="Show the ♿ accessible badge on the rota — "
        "someone has specifically reviewed this role and confirmed it is suitable for wheelchair users.",
    )

    keyholder_only = models.BooleanField(
        default=False,
        help_text="Show the 🔑 keyholder badge on the rota — "
        "slot must be filled by a trained venue keyholder.",
    )

    programmer_contact = models.BooleanField(
        default=False,
        help_text="Mark this as the event's programmer/contact slot — "
        "empty slots show a warning on the rota to encourage sign-up.",
    )

    GATE_OFF = "off"
    GATE_ADVISORY = "advisory"
    GATE_BLOCKING = "blocking"
    GATE_MODE_CHOICES = [
        (GATE_OFF, "Off"),
        (GATE_ADVISORY, "Advisory"),
        (GATE_BLOCKING, "Blocking"),
    ]

    stats_label = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Optional label used to group this role with others in volunteer stats. "
            "E.g. set 'Bar' on 'Bar Staff - Shift 1' and 'Bar Staff - Shift 2' so they "
            "appear as a single 'Bar' row. Leave blank to use the role name."
        ),
    )

    required_qualification = models.ForeignKey(
        "members.Qualification",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="required_for_roles",
        help_text="Qualification volunteers must hold to sign up for this role.",
    )
    qualification_gate = models.CharField(
        max_length=10,
        choices=GATE_MODE_CHOICES,
        default=GATE_OFF,
        help_text="What happens when a volunteer without the required qualification tries to sign up.",
    )

    @property
    def has_active_gate(self):
        """True when this role has a qualification requirement that actually fires (not 'off')."""
        return bool(
            self.required_qualification_id
            and self.qualification_gate != self.GATE_OFF
        )

    class Meta:
        db_table = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original value of name, so it can't be edited for
        # read only roles
        self._original_name = self.name
        self._original_read_only = self.read_only
        self._original_is_one_shot = self.is_one_shot

    def save(self, *args, **kwargs):
        if self._original_read_only and self._original_name != self.name:
            logger.error(f"Tried to edit read-only role {self.name}")
            return
        elif self._original_read_only and not self.read_only:
            # TODO: Unit test!
            logger.error(f"Tried to unprotect read-only role {self.name}")
            return
        else:
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and self.read_only:
            logger.error(f"Tried to delete read-only role {self.name}")
            return False
        # Archive instead of delete if this role appears in any rota entries.
        if self.pk and RotaEntry.objects.filter(role=self).exists():
            self.archived = True
            self.save()
            return (0, {})
        return super().delete(*args, **kwargs)


class EventTemplate(models.Model):

    name = models.CharField(max_length=32)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Default roles for this event (with per-role slot counts)
    roles = models.ManyToManyField(Role, through="EventTemplateRole")
    # Default tags for this event
    tags = models.ManyToManyField(
        "diary.EventTag", db_table="EventTemplate_Tags", blank=True
    )
    # Default pricing for this event
    pricing = models.CharField(max_length=256, null=False, blank=True)

    # Default copy fields — applied to new events on creation
    copy = models.TextField(max_length=8192, null=True, blank=True)
    copy_summary = models.TextField(max_length=4096, null=True, blank=True)
    terms = models.TextField(max_length=4096, null=True, blank=True)
    film_information = models.CharField(max_length=256, null=False, blank=True)
    private = models.BooleanField(default=False)
    outside_hire = models.BooleanField(default=False)

    # Structured cost fields — pre-populate matching fields on new events
    cost_type = models.CharField(
        max_length=32,
        choices=Event.COST_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Cost type",
    )
    cost_distributor = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Distributor / booker",
    )
    cost_flat_fee_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Flat fee (£)",
    )
    cost_fee_includes_vat = models.BooleanField(
        null=True, blank=True, verbose_name="Fee includes VAT"
    )
    cost_percentage_split = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="% split to distributor",
    )
    cost_minimum_guarantee_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Minimum guarantee (£)",
    )
    cost_total_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total cost (£)",
    )
    cost_rider_notes = models.TextField(
        max_length=4096,
        null=True,
        blank=True,
        verbose_name="Hospitality / rider",
    )
    cost_sound_engineer_name = models.CharField(
        max_length=256, null=True, blank=True, verbose_name="Sound engineer"
    )
    cost_sound_engineer_fee_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Sound engineer fee (£)",
    )
    cost_sound_engineer_paid_by = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=Event.SOUND_ENGINEER_PAID_BY_CHOICES,
        verbose_name="Sound engineer paid by",
    )

    # Default rota notes — applied to the first showing on creation
    rota_notes = models.TextField(max_length=4096, null=False, blank=True)

    class Meta:
        db_table = "EventTemplates"
        ordering = ["name"]

    def __str__(self):
        return self.name


class EventTemplateRole(models.Model):
    """Through model for EventTemplate.roles, adding a per-role slot count."""

    template = models.ForeignKey(
        EventTemplate, on_delete=models.CASCADE, related_name="role_slots"
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    count = models.PositiveSmallIntegerField(
        default=1,
        help_text="Number of slots to create for this role when a new event is made from this template.",
    )

    class Meta:
        db_table = "EventTemplateRoles"
        unique_together = [("template", "role")]
        ordering = ["role__name"]

    def __str__(self):
        return f"{self.template.name} — {self.role.name} ×{self.count}"


class EventTemplateRoom(models.Model):
    """Default room booking for an EventTemplate.

    When a new Showing is created from a template, one RoomBooking is
    auto-created per EventTemplateRoom.

    start_delta_minutes: offset (in minutes) from Showing.start when the
      room booking begins. 0 = same time as the showing, -120 = 2 hours
      before. Combined with date_offset so a "day before, from noon" booking
      is start_delta_minutes=-480 (if showing is 20:00) with date_offset=-1.
    end_delta_minutes: end offset in minutes from Showing.start. Null means
      derive the end from the event duration (same as _create_room_booking).
    date_offset: -1 = day before the showing, 0 = same day, +1 = day after.
    """

    template = models.ForeignKey(
        EventTemplate, on_delete=models.CASCADE, related_name="default_rooms"
    )
    room = models.ForeignKey(
        "diary.Room",
        on_delete=models.PROTECT,
        related_name="template_defaults",
    )
    start_delta_minutes = models.IntegerField(
        default=0,
        help_text=(
            "Start offset from Showing start (minutes). 0 = same time, -120 = 2 hours before."
        ),
    )
    end_delta_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="End offset from Showing start (minutes). Leave blank to use event duration.",
    )
    date_offset = models.IntegerField(
        default=0,
        help_text="Days relative to the Showing: 0 = same day, -1 = day before, +1 = day after.",
    )

    class Meta:
        db_table = "EventTemplateRooms"
        ordering = ["date_offset", "start_delta_minutes"]
        unique_together = [("template", "room", "date_offset")]

    def __str__(self):
        label = f"{self.template.name} — {self.room.name}"
        if self.date_offset != 0:
            label += f" (day {'before' if self.date_offset < 0 else 'after'})"
        if self.start_delta_minutes != 0:
            label += f" {self.start_delta_minutes:+}min"
        return label


class RotaEntry(models.Model):

    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    showing = models.ForeignKey("diary.Showing", on_delete=models.CASCADE)
    volunteer = models.ForeignKey(
        "members.Volunteer",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rota_entries",
    )

    required = models.BooleanField(default=True)
    rank = models.IntegerField(default=1)

    # Free text for superusers (external hires, ad-hoc notes) and legacy entries.
    # For volunteer sign-ups, written from volunteer.member.name at time of save.
    name = models.TextField(max_length=256, null=False, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "RotaEntries"
        ordering = ["role", "rank"]

    def __str__(self):
        return f"{str(self.role)} {self.rank}"

    def __init__(self, *args, **kwargs):
        # Allow a template keyword arg to be supplied. If it is, copy rota
        # details across (except for the showing id, if that's set separately)
        if "template" in kwargs:
            template = kwargs.pop("template")
        else:
            template = None

        super().__init__(*args, **kwargs)

        if template:
            # Only use the showing from the template if one hasn't been set yet
            if self.showing is None:
                self.showing = template.showing
            self.role = template.role
            self.required = template.required
            self.rank = template.rank
            logger.info(
                "Cloning rota entry from existing rota entry with "
                f"role_id {template.role.pk}"
            )
