import re
import logging

import datetime

from django.db import models
import django.utils.timezone
import nh3
from django.utils.safestring import mark_safe
from django.db.models.query import QuerySet
from django.utils.text import slugify
from django.conf import settings

from toolkit.diary.validators import validate_in_future, validate_event_link_url
import toolkit.util.image as imagetools

logger = logging.getLogger(__name__)


class FutureDateTimeField(models.DateTimeField):
    """DateTime field that can only be set to times in the future.
    Used for Showing start times"""

    default_error_messages = {
        "invalid": "Date may not be in the past",
    }
    default_validators = [validate_in_future]


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
        return bool(self.required_qualification_id and self.qualification_gate != self.GATE_OFF)

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


class MediaItem(models.Model):
    """Media (eg. video, audio, html fragment?). Currently to be assoicated
    with events, in future with other things?"""

    media_file = models.ImageField(
        upload_to="diary",
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Image file",
    )
    mimetype = models.CharField(max_length=64, editable=False)

    credit = models.CharField(
        max_length=256,
        blank=True,
        default="Internet scavenged",
        verbose_name="Image credit",
    )
    alt_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Alt text",
        help_text=(
            "Describe the image for screen readers and when images fail to load. "
            "E.g. \"People sitting in an outdoor cinema under a night sky.\""
        ),
    )
    caption = models.CharField(max_length=256, blank=True)
    bar_colour = models.CharField(
        max_length=7,
        blank=True,
        default="",
        verbose_name="Letterbox bar colour",
        help_text=(
            "If set, the programme grid thumbnail is padded with bars of this colour "
            "before being cropped. Your original image is never modified. "
            "Leave empty to use the crop box alone."
        ),
    )
    crop_x = models.FloatField(null=True, blank=True)
    crop_y = models.FloatField(null=True, blank=True)
    crop_w = models.FloatField(null=True, blank=True)
    crop_h = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "MediaItems"

    def __str__(self):
        return f"{self.pk}: {self.media_file}"

    # Overloaded Django ORM method:

    def save(self, *args, **kwargs):
        # Before saving, update mimetype field:
        # (do this even if file name has stayed the same, as file may have been
        # overwritten)
        self.autoset_mimetype()

        return super().save(*args, **kwargs)

    # Extra, custom methods:
    def autoset_mimetype(self):
        # See lib/python2.7/site-packages/django/forms/fields.py for how to do
        # basic validation of PNGs / JPEGs
        if self.media_file and self.media_file.name != "":
            try:
                self.mimetype = imagetools.get_mimetype(self.media_file.file)
            except OSError:
                logger.error(
                    f"Failed to determine mimetype of file {self.media_file.name}"
                )
                self.mimetype = "application/octet-stream"
            logger.debug(
                f"Mime type for {self.media_file.name} detected as {self.mimetype}"
            )


class EventTagQuerySet(QuerySet):
    def contains_tag_to_not_need_terms(self) -> bool:
        """
        Do any of the tags match the list of tags which mean terms text is not
        required for an event?
        """
        return self.filter(name__in=settings.TAGS_WITHOUT_TERMS).exists()


class EventTag(models.Model):
    name = models.CharField(max_length=32, unique=True)
    slug = models.SlugField(max_length=50, unique=True)  # allow_unicode=True?
    read_only = models.BooleanField(default=False, editable=False)
    promoted = models.BooleanField(default=False)
    sort_order = models.IntegerField(null=True, blank=True, editable=True)
    archived = models.BooleanField(
        default=False,
        help_text="Archived tags are hidden from normal use. "
        "Tags used on past events cannot be permanently deleted.",
    )
    filter_group = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="If set, this tag contributes to the named filter group on the public programme page.",
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="One or two sentences on when to use this tag. Shown as a tooltip on the event edit form.",
    )

    objects = EventTagQuerySet.as_manager()

    class Meta:
        db_table = "EventTags"
        ordering = ["sort_order", "name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store original value of read_only, so we can tell when the flag has
        # been set after load, and name/slug so we can enforce they haven't
        # changed:
        self._read_only_at_load = self.read_only
        self._name_at_load = self.name
        self._slug_at_load = self.slug

    def __str__(self):
        return self.name

    def clean(self):
        # Force to lowercase:
        self.name = self.name.lower().strip()
        # Generate slug:
        self.slug = slugify(self.name)

    # Overloaded Django ORM methods:
    def save(self, *args, **kwargs):
        if self.pk and self._read_only_at_load:
            # Allow "promoted" and "sort_order" to be changed:
            self.read_only = self._read_only_at_load
            self.name = self._name_at_load
            self.slug = self._slug_at_load
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.pk and self.read_only:
            return False
        # Archive instead of delete if this tag has been used on any event.
        if self.pk and Event.objects.filter(tags=self).exists():
            self.archived = True
            self.save()
            return (0, {})
        return super().delete(*args, **kwargs)


class Film(models.Model):
    """Structured metadata for a film or TV show screened at the venue.

    One Film record is shared across multiple Event screenings. imdb_id is the
    primary external key; nullable so programmers can create records for
    local/niche works not in OMDb.
    """

    MEDIA_TYPE_FILM = "film"
    MEDIA_TYPE_TV = "tv"
    MEDIA_TYPE_CHOICES = [("film", "Film"), ("tv", "TV show")]

    # External identifiers (nullable — local works may have neither)
    imdb_id = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="IMDB ID",
        help_text="e.g. tt0036775",
    )
    media_type = models.CharField(
        max_length=8,
        default=MEDIA_TYPE_FILM,
        choices=MEDIA_TYPE_CHOICES,
    )

    # Core metadata (all optional so partial manual entry is supported)
    title = models.CharField(max_length=500)
    original_title = models.CharField(max_length=500, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    director = models.CharField(
        max_length=256,
        blank=True,
        help_text="Director(s) or TV creator(s), comma-separated if more than one.",
    )
    runtime_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    countries = models.CharField(
        max_length=256,
        blank=True,
        help_text="e.g. GB, US",
    )
    languages = models.CharField(
        max_length=256,
        blank=True,
        help_text="e.g. English, French",
    )
    overview = models.TextField(
        blank=True,
        help_text="Plot summary. Internal reference only — not shown publicly.",
    )
    poster_url = models.CharField(
        max_length=512,
        blank=True,
        verbose_name="Poster URL",
        help_text="Direct URL to a poster image. Set automatically from OMDb.",
    )

    notes = models.TextField(
        blank=True,
        help_text="Internal programmer notes about this title.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "year"]

    def __str__(self):
        year_str = f" ({self.year})" if self.year else ""
        return f"{self.title}{year_str}"

    def generate_film_information(self) -> str:
        """Return a formatted display string suitable for Event.film_information.

        Format: 'Dir. X, Country YYYY, N mins, Cert Z' — blank fields omitted.
        """
        parts = []
        if self.director:
            parts.append(f"Dir. {self.director}")
        if self.countries:
            parts.append(self.countries)
        if self.year:
            parts.append(str(self.year))
        if self.runtime_minutes:
            parts.append(f"{self.runtime_minutes} mins")
        return ", ".join(parts)


class Event(models.Model):

    name = models.CharField(max_length=256, blank=False)

    # Eg; "Prodco presents..."
    pre_title = models.CharField(max_length=256, null=False, blank=True)

    # Eg. "with support from The Supporters"
    post_title = models.CharField(max_length=256, null=False, blank=True)

    # This is the primary key used in the old perl/bdb system
    legacy_id = models.CharField(max_length=256, null=True, editable=False)

    template = models.ForeignKey(
        "EventTemplate",
        verbose_name="Event Type",
        related_name="template",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    film = models.ForeignKey(
        Film,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="screenings",
        help_text="Structured film/TV metadata. Optional — link via the film search in the edit form.",
    )
    tags = models.ManyToManyField(EventTag, db_table="Event_Tags", blank=True)

    duration = models.TimeField(null=True)

    outside_hire = models.BooleanField(default=False)
    hire_name = models.CharField(
        max_length=256,
        blank=True,
        verbose_name="Hirer name / organisation",
        help_text="Who is hiring the venue? Shown on the rota so everyone knows who to liaise with.",
    )
    private = models.BooleanField(default=False)

    media = models.ManyToManyField(MediaItem, db_table="Event_MediaItems")

    # Free text pricing info:
    pricing = models.CharField(max_length=256, null=False, blank=True)
    ticket_link = models.URLField(max_length=256, null=False, blank=True)
    trailer_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Trailer URL",
        help_text="Link to a trailer (e.g. YouTube or Vimeo). Shown as a 'Watch trailer' link on the public event page.",
    )

    # Free text film information:
    film_information = models.CharField(max_length=256, null=False, blank=True)

    age_restriction = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name="Age restriction",
        help_text="Age rating or restriction for this event. Options are configured in the site settings.",
    )

    # Legacy constants — kept so any migrations that reference them still work.
    AGE_UNSET = ""
    AGE_ALL = "all_ages"
    AGE_16_PLUS = "16_plus"
    AGE_18_PLUS = "18_plus"

    copy = models.TextField(max_length=8192, null=True, blank=True)
    copy_summary = models.TextField(max_length=4096, null=True, blank=True)

    # Following flag is True when the event copy has been imported from the
    # "legacy" toolkit; the bizarre text wrapping will be fixed up before
    # display, regex will be applied to turn http://.* into links, etc.
    legacy_copy = models.BooleanField(
        default=False, null=False, editable=False
    )

    terms = models.TextField(max_length=4096, null=True, blank=True)

    COST_TYPE_FILM_LICENSE = "film_license"
    COST_TYPE_PERFORMER_FEE = "performer_fee"
    COST_TYPE_VENUE_HIRE = "venue_hire"
    COST_TYPE_INTERNAL = "internal"
    COST_TYPE_TBC = "tbc"
    COST_TYPE_CHOICES = [
        ("film_license", "Film licence"),
        ("performer_fee", "Performer fee / gig"),
        ("venue_hire", "Venue hire"),
        ("internal", "Internal / volunteer"),
        ("tbc", "TBC"),
    ]
    cost_type = models.CharField(
        max_length=32,
        choices=COST_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Cost type",
        help_text="The nature of the financial deal for this event.",
    )
    cost_distributor = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Distributor / booker",
        help_text="The distribution company or booker contact (film licence / performer fee).",
    )
    cost_flat_fee_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Flat fee (£)",
        help_text="Fixed licence or performance fee in pounds.",
    )
    cost_fee_includes_vat = models.BooleanField(
        null=True,
        blank=True,
        verbose_name="Fee includes VAT",
    )
    cost_percentage_split = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="% split to distributor",
        help_text="Percentage of net door takings paid to the distributor/performer.",
    )
    cost_minimum_guarantee_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Minimum guarantee (£)",
        help_text="Guaranteed minimum payment regardless of door takings.",
    )
    cost_total_gbp = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Total cost (£)",
        help_text="Total agreed fee (performer / hire).",
    )
    cost_rider_notes = models.TextField(
        max_length=4096,
        null=True,
        blank=True,
        verbose_name="Hospitality / rider",
        help_text="Food, drink, accommodation, or other rider requirements for the performer or hirer.",
    )
    SOUND_ENGINEER_PAID_BY_VENUE = "venue"
    SOUND_ENGINEER_PAID_BY_PERFORMER = "performer"
    SOUND_ENGINEER_PAID_BY_HIRER = "hirer"
    SOUND_ENGINEER_PAID_BY_CHOICES = [
        ("venue", "Venue"),
        ("performer", "Performer"),
        ("hirer", "Hirer"),
    ]
    cost_sound_engineer_name = models.CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name="Sound engineer",
        help_text="Name or contact for the sound engineer, if applicable.",
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
        choices=SOUND_ENGINEER_PAID_BY_CHOICES,
        verbose_name="Sound engineer paid by",
    )
    technical_notes = models.TextField(
        max_length=4096,
        null=True,
        blank=True,
        verbose_name="Technical notes",
        help_text=(
            "AV / tech rider requirements, projection format, sound spec, etc. "
            "Kept separate from financial terms so the two don't get conflated."
        ),
    )

    APPROVAL_MEETING = "meeting"
    APPROVAL_STANDING = "standing"
    APPROVAL_CHOICES = [
        ("", "Not recorded"),
        ("meeting", "Approved at programming meeting"),
        ("standing", "Standing / regular event — no meeting needed"),
    ]
    approval_type = models.CharField(
        max_length=16,
        blank=True,
        choices=APPROVAL_CHOICES,
        default="",
        verbose_name="Approval status",
        help_text="How this event entered the programme.",
    )
    approved_at_meeting_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Meeting date",
        help_text="Date of the programming meeting at which this was approved.",
    )
    meeting_name = models.CharField(
        max_length=128,
        blank=True,
        verbose_name="Meeting name",
        help_text="Optional identifier, e.g. 'Monday meeting'.",
    )
    meeting_minutes_url = models.URLField(
        blank=True,
        max_length=500,
        verbose_name="Minutes link",
        help_text="Optional link to the meeting minutes.",
    )

    PROGRAMMING_STATUS_CHOICES = [
        ("active", "Active"),
        ("draft", "Draft"),
        ("proposed", "Proposed for meeting"),
        ("rejected", "Returned / needs work"),
    ]
    programming_status = models.CharField(
        max_length=16,
        blank=True,
        choices=PROGRAMMING_STATUS_CHOICES,
        default="active",
        verbose_name="Programming status",
        help_text=(
            "Internal status for the programming queue. "
            "'Draft' = not yet ready for a meeting; 'Proposed' = queued for discussion; "
            "'Active' = normal/approved event; 'Returned' = sent back for changes."
        ),
    )
    programming_notes = models.TextField(
        blank=True,
        verbose_name="Programmer's notes",
        help_text=(
            "Internal working notes — not visible to the public. "
            "Use for queue context (e.g. 'looking for a Friday in May — sample date'), "
            "meeting decisions, and conditions attached to approval. "
            "Financial details and hire contacts belong in Terms."
        ),
    )

    programming_status_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Status last changed",
        help_text="Set automatically whenever programming_status is updated.",
    )

    target_month = models.DateField(
        null=True,
        blank=True,
        verbose_name="Target month",
        help_text=(
            "For undated proposals: the rough month being targeted. "
            "Always stored as the 1st of the month. "
            "Shown in the diary alongside monthly ideas notes."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Events"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate scalar fields from template on construction.
        # Only fills blank/null fields so explicit kwargs always win.
        if "template" in kwargs:
            tmpl = kwargs["template"]
            for field in (
                "pricing",
                "copy",
                "copy_summary",
                "terms",
                "film_information",
            ):
                if not getattr(self, field):
                    setattr(self, field, getattr(tmpl, field) or "")
            # Copy nullable cost fields from template when not yet set on this event.
            for field in (
                "cost_type",
                "cost_distributor",
                "cost_flat_fee_gbp",
                "cost_fee_includes_vat",
                "cost_percentage_split",
                "cost_minimum_guarantee_gbp",
                "cost_total_gbp",
                "cost_rider_notes",
                "cost_sound_engineer_name",
                "cost_sound_engineer_fee_gbp",
                "cost_sound_engineer_paid_by",
            ):
                if getattr(self, field) is None:
                    tmpl_val = getattr(tmpl, field)
                    if tmpl_val is not None:
                        setattr(self, field, tmpl_val)
            # Booleans: only override if still at their default (False)
            if not self.private:
                self.private = tmpl.private
            if not self.outside_hire:
                self.outside_hire = tmpl.outside_hire

    def __str__(self):
        return f"{self.name} ({self.id})"

    def reset_tags_to_default(self):
        if self.template:
            for tag in self.template.tags.all():
                self.tags.add(tag)

    def delete(self, *args, **kwargs):
        # Don't allow Events to be deleted. This doesn't block deletes on
        # querysets, SQL, etc.
        raise django.db.IntegrityError("Event deletion not allowed")

    # Extra, custom methods:
    def clear_main_mediaitem(self):
        if self.media.count() == 0:
            return
        media_item = self.media.all()[0]
        logger.info(f"Removing media file {media_item} from event {self.pk}")
        self.media.remove(media_item)

    def set_main_mediaitem(self, media_file):
        self.clear_main_mediaitem()
        logger.info(f"Adding media file {media_file} to event {self.pk}")
        self.media.add(media_file)

    def get_main_mediaitem(self):
        if self.media.count() == 0:
            return None
        return self.media.all()[0]

    # Regular expressions for mangling legacy copy:
    _wrap_re = re.compile(r"(.{70,})\n")
    _lotsofnewlines_re = re.compile(r"\n\n+")
    # Catch well-formatted links (ie. beginning http://)
    _link_re_1 = re.compile(r"(https?:\/\/\S{4,})")
    # Optimistic stab at spotting other things that are probably links, based
    # on a smattering of TLDs:
    _link_re_2 = re.compile(
        r"(\s)(www\.[\w.]+\.(com|org|net|uk|de|ly|us|tk)[^\t\n\r\f\v\. ]*)"
    )

    def get_age_restriction_display(self):
        """Return the human-readable label for the stored age restriction value.

        Looks up the site-configured age_rating_choices first, then falls back
        to legacy hardcoded labels so old stored values (all_ages / 16_plus /
        18_plus) still render correctly on events created before the BBFC
        migration.
        """
        if not self.age_restriction:
            return ""
        cfg = get_site_config()
        for entry in cfg.age_rating_choices:
            if entry.get("value") == self.age_restriction:
                return entry.get("label", self.age_restriction)
        _legacy = {"all_ages": "All ages welcome", "16_plus": "16+ only", "18_plus": "18+ only"}
        return _legacy.get(self.age_restriction, self.age_restriction)

    def all_showings_in_past(self):
        return all(s.in_past() for s in self.showings.all())

    def all_showings_confirmed(self) -> bool:
        return all(s.confirmed for s in self.showings.all())

    # Tags and attributes permitted in stored HTML copy.
    # Script tags, event-handler attributes (onclick etc.) and javascript:
    # hrefs are stripped by nh3 regardless of this allowlist.
    _COPY_ALLOWED_TAGS = {
        "a", "abbr", "b", "blockquote", "br", "cite", "code",
        "em", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
        "i", "img", "li", "ol", "p", "s", "strike", "strong",
        "sub", "sup", "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
    }
    _COPY_ALLOWED_ATTRS = {
        "a":   {"href", "title", "target"},
        "img": {"src", "alt", "width", "height", "border"},
        "td":  {"colspan", "rowspan"},
        "th":  {"colspan", "rowspan"},
    }

    @property
    def copy_html(self):
        """If self.legacy_copy == True, then try to mangle self.copy into
        sane HTML fragment. Otherwise return self.copy.
        (Legacy cube copy has line breaks around the 70-80 character mark, and
        no hyperlinks)

        In both cases the result is sanitized with nh3 to strip script tags,
        event-handler attributes, and javascript: hrefs before being marked
        safe for template rendering."""

        if not self.legacy_copy:
            result = self.copy or ""
        else:
            # remove all whitespace from start and end of line:
            result = self.copy.strip()
            # Strip out carriage returns:

            result = result.strip().replace("\r", "")
            # Strip out new lines when they occur after 70 other characters
            # (try to fix wrapping)
            result = self._wrap_re.sub(r"\1 ", result)
            # Replace a sequence of 2+ new lines with a double line break;
            result = self._lotsofnewlines_re.sub(" <br><br>", result)

            # Now replace all new lines with a single line break;
            result = result.replace("\n", " <br>\n")

            # Attempt to magically convert any links to HTML markup:
            result = self._link_re_1.sub(r'<a href="\1">\1</a>', result)
            result = self._link_re_2.sub(
                r'\1<a href="http://\2">\2</a>', result
            )

        return mark_safe(nh3.clean(
            result,
            tags=self._COPY_ALLOWED_TAGS,
            attributes=self._COPY_ALLOWED_ATTRS,
        ))

    # This RE needs to be compiled so that the flags can be specified, as the
    # flags option to re.sub() wasn't added until python 2.7
    _plaintext_re = re.compile(r"\[(.*?)\]\((https?://.*?)\)", flags=re.DOTALL)

    def terms_long_enough(self):
        if not self.terms:
            return False
        word_count = len(self.terms.split())
        return word_count >= get_site_config().programme_event_terms_min_words

    def terms_required(self):
        return not self.tags.contains_tag_to_not_need_terms()

    def terms_satisfied(self):
        """Terms requirement is met if: not required, OR freetext is long enough, OR a non-TBC cost type is recorded."""
        if not self.terms_required():
            return True
        if self.terms_long_enough():
            return True
        return bool(self.cost_type and self.cost_type != self.COST_TYPE_TBC)


class Room(models.Model):
    name = models.CharField(max_length=64)
    colour = models.CharField(max_length=9, default="#33CC33")
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary spaces are shown with full colour in the calendar; others are desaturated.",
    )
    map_slug = models.SlugField(
        max_length=64,
        blank=True,
        default="",
        help_text="SVG element ID in the building floorplan (e.g. 'room-cinema'). Leave blank if not on the map.",
    )
    show_column = models.BooleanField(
        default=True,
        help_text="Show this room as its own column in the diary list view. "
        "Uncheck to bundle bookings into the 'Other rooms' column.",
    )

    class Meta:
        db_table = "Rooms"

    def __str__(self):
        return self.name


class RoomBooking(models.Model):
    """A time-slot reservation of a Room for a Showing.

    A Showing can have multiple RoomBookings (e.g. setup in Venue Space from
    16:00, screening in Cinema from 19:30). start/end are independent of
    Showing.start so that pre/post-event room use can be recorded.

    date_offset shifts the booking date relative to the Showing's date:
    0 = same day (default), -1 = day before, +1 = day after.  This covers
    multi-day load-in/teardown without creating dummy Showings.
    """

    showing = models.ForeignKey(
        "Showing", on_delete=models.CASCADE, related_name="room_bookings"
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    date_offset = models.IntegerField(
        default=0,
        help_text="Days relative to the showing date: 0 = same day, -1 = day before, +1 = day after.",
    )

    class Meta:
        db_table = "RoomBookings"
        ordering = ["start"]

    def __str__(self):
        return f"{self.room.name} @ {self.showing}"


class ShowingQuerySet(QuerySet):
    """
    This class provides some custom methods to make searching and selecting
    sets of Showings clearer
    """

    def start_in_future(self):
        """Filter showings that have a start date in the future"""
        return self.filter(start__gt=django.utils.timezone.now())

    def start_in_past(self):
        """Filter showings that have a start date in the past"""
        return self.exclude(start__gt=django.utils.timezone.now())

    def start_in_range(self, startdate, enddate):
        """Filter showings that have a start date in the given range"""
        return self.filter(start__range=[startdate, enddate])

    def public(self):
        """
        Filters so only showings that should be visible to the general public
        are included. (ie. exclude unconfirmed, hidden in programme)
        """
        return (
            self.filter(event__private=False)
            .filter(confirmed=True)
            .filter(hide_in_programme=False)
        )

    def not_cancelled(self):
        """Filter out cancelled showings"""
        return self.filter(cancelled=False)

    def confirmed(self):
        """Filter out unconfirmed showings"""
        return self.filter(confirmed=True)


class Showing(models.Model):

    event = models.ForeignKey(
        "Event", related_name="showings", on_delete=models.CASCADE
    )

    start = FutureDateTimeField(db_index=True)

    booked_by = models.CharField(max_length=64)

    extra_copy = models.TextField(max_length=4096, null=True, blank=True)
    extra_copy_summary = models.TextField(
        max_length=4096, null=True, blank=True
    )

    confirmed = models.BooleanField(default=False)
    hide_in_programme = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    discounted = models.BooleanField(default=False)
    sold_out = models.BooleanField(default=False)

    # sales tables?

    # Rota entries
    roles = models.ManyToManyField(Role, through="RotaEntry")

    # Free text rota field for this showing
    rota_notes = models.TextField(max_length=4096, blank=True)

    setup_time = models.TimeField(null=True, blank=True)
    doors_time = models.TimeField(null=True, blank=True)
    final_volunteer_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Custom manager, with some extra methods:
    objects = ShowingQuerySet.as_manager()

    class Meta:
        db_table = "Showings"
        ordering = ["start"]

    def __init__(self, *args, **kwargs):
        # Allow "copy_from" and "start_offset" keyword args to be supplied.
        # If "copy_from" is supplied, all showing details except for rota
        # items (which require DB writes) are copied from the supplied Showing
        # object.
        # If "start_offset" is passed and "copy_from" is also passed then the
        # given TimeDelta is added to copy_from.start
        # (If start_offset is defined but copy_from is not then a ValueError is
        # raised)

        copy_from = kwargs.pop("copy_from", None)
        start_offset = kwargs.pop("start_offset", None)
        if start_offset and copy_from is None:
            raise ValueError("start_offset supplied with no copy_from")

        super().__init__(*args, **kwargs)

        self._original_start = self.start

        if copy_from:
            logger.info(
                f"Cloning showing from existing showing (id {copy_from.pk})"
            )
            # Manually copy fields, rather than using things from copy library,
            # as don't want to copy the rota (as that would make db writes)
            attributes_to_copy = (
                "event",
                "start",
                "booked_by",
                "extra_copy",
                "confirmed",
                "hide_in_programme",
                "cancelled",
                "discounted",
            )
            for attribute in attributes_to_copy:
                setattr(self, attribute, getattr(copy_from, attribute))
            if start_offset:
                self.start += start_offset

    def __str__(self):
        if (
            self.start is not None
            and self.id is not None
            and self.event is not None
        ):
            return "{0} - {1} ({2})".format(
                self.start.strftime("%H:%M %Z%z %d/%m/%y"),
                self.event.name,
                self.id,
            )
        else:
            return "[uninitialised]"

    # Overload django model methods:

    def save(self, *args, **kwargs):
        # Don't allow showings to be edited if they're finished. This isn't a
        # complete fix, as operations on querysets (or just SQL) will bypass
        # this, but this will stop the forms deleting records. (Stored
        # procedures, anyone?)
        #
        # (Mostly for tests, if force=True then this check is bypassed)
        force = kwargs.pop("force", False)
        if not force and self.pk is not None and (self.in_past() or self.original_start_in_past()):
            logger.error(
                f"Tried to update showing {self.pk} with start time {self.start}"
                f" in the past (original start time {self._original_start}"
            )
            raise django.db.IntegrityError(
                "Can't update showings that start in the past"
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Don't allow showings to be deleted if they're finished. This isn't a
        # complete fix, as operations on querysets (or just SQL) will bypass
        # this, but this will stop the forms deleting records.
        if self.in_past() or self.original_start_in_past():
            logger.error(
                f"Tried to delete showing {self.pk} with start time "
                f"{self.start} in the past"
            )
            raise django.db.IntegrityError(
                "Can't delete showings that start in the past"
            )
        return super().delete(*args, **kwargs)

    # Extra, custom methods:

    @property
    def start_date(self):
        # Used by templates
        return self.start.date()

    @property
    def end_time(self):
        # Used by templates and calendar JSON
        duration = self.event.duration
        if duration is None:
            # Apply default 2-hour duration for events without explicit duration
            # This ensures FullCalendar can detect overlaps and tile events properly
            return self.start + datetime.timedelta(hours=2)
        return self.start + datetime.timedelta(
            hours=duration.hour, minutes=duration.minute
        )

    @property
    def rooms_display(self):
        """Comma-separated room names, ordered by booking start time."""
        return ", ".join(rb.room.name for rb in self.room_bookings.all()) or ""

    @property
    def primary_room(self):
        """First booked room by start time, or None."""
        rb = self.room_bookings.all().first()
        return rb.room if rb else None

    def occupies_rooms(self):
        """Whether this showing's room bookings should display as occupying a room.

        A cancelled date — or a date on an event that's been rejected from the
        programming queue — frees its rooms: the booking rows are kept (so
        un-cancelling restores them) but they stop showing on the diary and
        calendar. Consistent with clash detection, which only blocks on
        confirmed bookings (see clash.py).
        """
        if self.cancelled:
            return False
        if self.event.programming_status == "rejected":
            return False
        return True

    @property
    def visible_room_bookings(self):
        """Room bookings to render as occupying rooms — empty when freed.

        See occupies_rooms(). Use this (not room_bookings.all()) anywhere room
        occupancy is surfaced on the diary or calendar.
        """
        if not self.occupies_rooms():
            return []
        return list(self.room_bookings.all())

    def in_past(self):
        return self.start and (self.start < django.utils.timezone.now())

    def original_start_in_past(self):
        return (
            self._original_start
            and self._original_start < django.utils.timezone.now()
        )

    def reset_rota_to_default(self):
        """Clear any existing rota entries. If the associated event has an
        event type defined then apply the default set of rota entries for that
        type, and copy any default rota_notes from the template."""

        # Delete all existing rota entries (if any)
        self.rotaentry_set.all().delete()

        if self.event.template is not None:
            tmpl = self.event.template
            # Add rota entries for each role slot in the template, respecting count:
            for slot in tmpl.role_slots.select_related("role").all():
                for rank in range(1, slot.count + 1):
                    RotaEntry(role=slot.role, showing=self, rank=rank).save()
            # Pre-populate rota notes from the template (only if blank)
            if not self.rota_notes and tmpl.rota_notes:
                self.rota_notes = tmpl.rota_notes
                self.save(update_fields=["rota_notes"])

    def create_room_bookings_from_template(self):
        """Auto-create RoomBookings for this Showing from the event template's default rooms.

        Skips rooms that already have a booking on this Showing to avoid
        duplicating manually-selected rooms. Does not check for clashes with
        other events — the clash warning on the edit-showing form covers that.
        """
        tmpl = self.event.template
        if tmpl is None:
            return
        already_booked_room_ids = set(
            self.room_bookings.values_list("room_id", flat=True)
        )
        for default in tmpl.default_rooms.select_related("room").all():
            if default.room_id in already_booked_room_ids:
                continue
            start_offset = datetime.timedelta(minutes=default.start_delta_minutes)
            booking_start = self.start + datetime.timedelta(days=default.date_offset) + start_offset
            if default.end_delta_minutes is not None:
                booking_end = self.start + datetime.timedelta(
                    days=default.date_offset,
                    minutes=default.end_delta_minutes,
                )
            elif self.event.duration:
                booking_end = booking_start + datetime.timedelta(
                    hours=self.event.duration.hour,
                    minutes=self.event.duration.minute,
                )
            else:
                booking_end = None
            RoomBooking.objects.create(
                showing=self,
                room=default.room,
                start=booking_start,
                end=booking_end,
                date_offset=default.date_offset,
            )

    def clone_rota_from_showing(self, source_showing):
        assert self.pk is not None
        # Copy rota_notes alongside the rota entries so recurring events keep
        # stable operational notes (setup instructions, access codes, timing).
        #
        # CAUTION: notes sometimes contain date-specific volunteer messages
        # ("Alice can't make this date") which will be wrong on the new
        # showing. Until the clone flow has a review/edit step, programmers
        # should check and clear stale notes after cloning. See TASKS.md 9.10.6
        # for the recommended near-term mitigation (inline warning on clone form).
        self.rota_notes = source_showing.rota_notes
        self.save(update_fields=["rota_notes"])
        for rota_entry in source_showing.rotaentry_set.all():
            new_entry = RotaEntry(showing=self, template=rota_entry)
            new_entry.save()

    def clone_or_reset_rota(self, source_showing):
        if source_showing:
            self.clone_rota_from_showing(source_showing)
        else:
            self.reset_rota_to_default()

    def update_rota(self, _rota):
        """Update rota from supplied dict. Dict should be a map of
        role_id: no. entries
        If no. entries is 0, any existing RotaEntries are deleted. If it's
        greater than the number of RotaEntries, they'r added as required. If a
        role_id is not in the dict, then any RotaEntries aren't affected"""

        # copy rota:
        rota = dict(_rota)

        # Build map of rota entries by role id
        rota_entries_by_id = {}
        for rota_entry in self.rotaentry_set.select_related():
            rota_entries_by_id.setdefault(rota_entry.role.pk, []).append(
                rota_entry
            )

        for role_id, count in rota.items():
            # Number of existing rota entries for this role_id.
            # Remove from dict, so anything left in the dict at the end
            # is an error...
            existing_entries = rota_entries_by_id.pop(role_id, [])
            # delete highest ranked instances
            while count < len(existing_entries):
                logger.info(f"Removing role {role_id} from showing {self.pk}")
                highest_ranked = max(existing_entries, key=lambda re: re.rank)
                highest_ranked.delete()
                existing_entries.remove(highest_ranked)
            # add required entries
            while count > len(existing_entries):
                logger.info(f"Adding role {role_id} to showing {self.pk}")
                # add rotaentries
                new_re = RotaEntry(role_id=role_id, showing=self)
                if len(existing_entries) > 0:
                    new_re.rank = (
                        1 + max(existing_entries, key=lambda re: re.rank).rank
                    )
                new_re.save()
                existing_entries.append(new_re)

        # Remove orphaned one-shot roles (no longer referenced by any RotaEntry)
        self._cleanup_unused_oneshot_roles()

    @staticmethod
    def _cleanup_unused_oneshot_roles():
        """Delete one-shot roles that are no longer referenced by any RotaEntry."""
        from django.db.models import Count as _Count

        Role.objects.filter(is_one_shot=True).annotate(
            usage=_Count("rotaentry")
        ).filter(usage=0).delete()


class DiaryIdea(models.Model):
    month = models.DateField(editable=False)
    ideas = models.TextField(max_length=16384, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "DiaryIdeas"

    def __str__(self):
        return f"{self.month.month}/{self.month.year}"


class EventTemplate(models.Model):

    name = models.CharField(max_length=32)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Default roles for this event (with per-role slot counts)
    roles = models.ManyToManyField(Role, through="EventTemplateRole")
    # Default tags for this event
    tags = models.ManyToManyField(
        EventTag, db_table="EventTemplate_Tags", blank=True
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
    cost_distributor = models.CharField(max_length=256, null=True, blank=True, verbose_name="Distributor / booker")
    cost_flat_fee_gbp = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Flat fee (£)")
    cost_fee_includes_vat = models.BooleanField(null=True, blank=True, verbose_name="Fee includes VAT")
    cost_percentage_split = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="% split to distributor")
    cost_minimum_guarantee_gbp = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Minimum guarantee (£)")
    cost_total_gbp = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Total cost (£)")
    cost_rider_notes = models.TextField(max_length=4096, null=True, blank=True, verbose_name="Hospitality / rider")
    cost_sound_engineer_name = models.CharField(max_length=256, null=True, blank=True, verbose_name="Sound engineer")
    cost_sound_engineer_fee_gbp = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Sound engineer fee (£)")
    cost_sound_engineer_paid_by = models.CharField(max_length=16, null=True, blank=True, choices=Event.SOUND_ENGINEER_PAID_BY_CHOICES, verbose_name="Sound engineer paid by")

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
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="template_defaults")
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
    showing = models.ForeignKey(Showing, on_delete=models.CASCADE)
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


class PrintedProgrammeQuerySet(QuerySet):
    def month_in_range(self, start, end):
        """Select printed programmes for months in given range"""
        # The idea being that even if 'start' is some day after the first of
        # the month, the programme for that month is still returned
        start_date = datetime.date(start.year, start.month, 1)

        return self.filter(month__range=[start_date, end])


class PrintedProgramme(models.Model):
    month = models.DateField(editable=False, unique=True)
    programme = models.FileField(
        upload_to="printedprogramme",
        max_length=256,
        null=False,
        blank=False,
        verbose_name="Programme PDF",
    )
    designer = models.CharField(max_length=256, blank=True)
    notes = models.TextField(max_length=8192, null=True, blank=True)

    objects = PrintedProgrammeQuerySet.as_manager()

    class Meta:
        db_table = "PrintedProgrammes"

    def __str__(self):
        return f"Printed programme for {self.month.month}/{self.month.year}"

    def save(self, *args, **kwargs):
        # Enforce month column always being a date for the first of the month:
        if self.month.day != 1:
            logger.error(
                "PrintedProgramme has month value which isn't the 1st"
                " of the month"
            )
            self.month = datetime.date(self.month.year, self.month.month, 1)
        return super().save(*args, **kwargs)


class EventLink(models.Model):
    """A named clickable link attached to an event (max 3 per event).

    Used to surface shared resources — event folders, crew chat links, planning
    docs, etc. — directly on the rota view so volunteers don't have to hunt for
    them.  Only a curated domain whitelist is accepted at validation time to
    prevent the rota becoming a phishing vector.
    """

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="links",
    )
    label = models.CharField(
        max_length=80,
        help_text="Short name shown on the link chip, e.g. 'Event folder' or 'Crew chat'.",
    )
    url = models.URLField(
        max_length=500,
        validators=[validate_event_link_url],
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (lower numbers first).",
    )

    class Meta:
        db_table = "EventLinks"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.label} ({self.event_id})"


class EventTemplateLink(models.Model):
    """A named resource link attached to an event template (max 3 per template).

    When a new event is created from this template the links are copied across
    as EventLink records on the new event, saving programmers from re-entering
    them every time.
    """

    template = models.ForeignKey(
        EventTemplate,
        on_delete=models.CASCADE,
        related_name="links",
    )
    label = models.CharField(max_length=80)
    url = models.URLField(
        max_length=500,
        validators=[validate_event_link_url],
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "EventTemplateLinks"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.label} ({self.template_id})"


class EventTermsRevision(models.Model):
    """Snapshot of audited financial fields on an Event, captured on each change.

    A new record is created by a pre_save signal whenever terms, outside_hire,
    or private changes. It stores the values *before* the save so the history
    is a complete chain of prior states.
    """

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="terms_revisions"
    )
    saved_at = models.DateTimeField(auto_now_add=True)
    saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Snapshot of audited fields immediately before this save
    terms_text = models.TextField(blank=True)
    outside_hire = models.BooleanField()
    private = models.BooleanField()

    class Meta:
        ordering = ["-saved_at"]

    def __str__(self):
        return f"Revision of '{self.event_id}' at {self.saved_at}"


DEFAULT_FILMS_START_BANNER_TEXT = (
    "We don't show adverts or trailers, so please arrive promptly, as films "
    "start as soon as most people have arrived."
)


class SiteConfiguration(models.Model):
    """Singleton (pk=1) holding runtime-editable site settings.

    A Panopticon edits these via /toolkit/site-config/ instead of needing a
    code deploy. The DB row is the source of truth; settings.py values are
    only used to seed the row in the initial data migration.
    """

    # --- Display & UX ---
    films_start_on_time = models.BooleanField(
        default=False,
        help_text="Show a banner on public event detail pages stating that films start on time.",
    )
    films_start_on_time_banner_text = models.TextField(
        blank=True,
        default=DEFAULT_FILMS_START_BANNER_TEXT,
        help_text="The banner copy. Only shown when 'Films start on time' is enabled.",
    )
    rota_show_tags = models.BooleanField(
        default=True,
        help_text=(
            "Show coloured event tag badges (e.g. 'family-friendly', 'accessible') on the "
            "edit rota page, along with a filter bar for narrowing the rota by tag. "
            "Useful once events are consistently tagged; turn off to reduce visual clutter "
            "if tags are rarely used at your venue."
        ),
    )
    rota_clear_email_prompt_enabled = models.BooleanField(
        default=True,
        help_text=(
            "When a volunteer removes themselves from a rota slot, show a reminder "
            "prompt asking them to notify the volunteers list. "
            "Edit the prompt text in the field below."
        ),
    )
    rota_clear_email_prompt_text = models.TextField(
        blank=True,
        default=(
            "Slot cleared.\n"
            "Please consider emailing {email} to say that the shift needs covering."
        ),
        help_text=(
            "The message shown when a volunteer clears their rota slot. "
            "Use {email} as a placeholder; it will be replaced with the volunteers list address "
            "set in the 'Volunteers list email' field below. "
            "Only shown when 'Rota clear email prompt' is enabled above."
        ),
    )
    vols_email = models.EmailField(
        blank=True,
        default="",
        max_length=254,
        verbose_name="Volunteers list email",
        help_text=(
            "The email address of the volunteers mailing list. "
            "Shown in the rota slot-cleared prompt (see above) when the {email} placeholder is used. "
            "Seeded from the VENUE settings on first run."
        ),
    )
    show_archive_images = models.BooleanField(
        default=True,
        help_text=(
            "If off, hide event images on the public site for events whose "
            "showings all predate the 'Images start date' below. Volunteers "
            "(authenticated users) always see images. Useful for taking "
            "pre-archive imagery offline quickly (e.g. copyright issues)."
        ),
    )
    images_start_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Cutoff date for the 'Show archive images' setting above. Has no "
            "effect unless that setting is off. Leave blank to disable hiding."
        ),
    )

    # --- Age ratings ---
    age_rating_choices = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Age-rating options shown in the event edit form. "
            "e.g. BBFC: U / PG / 12A / 12 / 15 / 18. "
            "Leave the list empty to hide the age restriction field entirely."
        ),
    )

    # --- Terminology ---
    # What this venue calls a single dated occurrence of an event. Cinemas
    # screen "showings"; a mixed-programme venue may prefer "dates" so the word
    # also fits a workshop or club-night run. Defaults are cinema-first because
    # this codebase is primarily used by cinemas (see SPEC: good neighbours).
    occurrence_noun = models.CharField(
        max_length=32,
        default="showing",
        verbose_name="Occurrence noun (singular)",
        help_text=(
            "Lowercase singular word for one dated occurrence of an event "
            "(e.g. 'showing' for a cinema, 'date' or 'session' elsewhere). "
            "Used throughout the event-editing UI."
        ),
    )
    occurrence_noun_plural = models.CharField(
        max_length=32,
        default="showings",
        verbose_name="Occurrence noun (plural)",
        help_text="Plural of the occurrence noun (e.g. 'showings', 'dates').",
    )
    confirm_label = models.CharField(
        max_length=48,
        default="Confirm",
        help_text=(
            "Label on the button that makes an occurrence public and opens its rota. "
            "Cinemas may prefer the short 'Confirm'; venues wanting to spell out the "
            "dual effect can use e.g. 'Publish & open rota'."
        ),
    )

    # --- Calendar ---
    calendar_slot_min_hour = models.PositiveSmallIntegerField(
        default=10,
        help_text=(
            "Earliest hour shown in the 3-day and week calendar views (0–23). "
            "Events before this time are still shown but the grid starts here. "
            "Default 10 hides the dead early-morning hours."
        ),
    )

    # --- Break-even calculator ---
    breakeven_guidance_note = models.TextField(
        blank=True,
        default=(
            "Opening the doors at S&S costs roughly £200 before any additional costs —"
            " make sure this is factored in above."
            " Finance Collective sign-off required if total costs exceed"
            " £500 (standard) or £750 (music)."
        ),
        help_text=(
            "Guidance note shown below the break-even calculator on the event hub page. "
            "Plain text."
        ),
    )
    breakeven_fc_standard_threshold = models.PositiveSmallIntegerField(
        default=500,
        help_text=(
            "Gross cost threshold (£) for a standard event above which a Finance Collective "
            "sign-off is required. Triggers a warning in the break-even calculator."
        ),
    )
    breakeven_fc_music_threshold = models.PositiveSmallIntegerField(
        default=750,
        help_text=(
            "Gross cost threshold (£) for a music event above which a Finance Collective "
            "sign-off is required. Triggers a warning in the break-even calculator."
        ),
    )

    # --- Programme limits ---
    max_count_per_role = models.PositiveSmallIntegerField(
        default=8,
        help_text="Maximum number of slots per role on a single showing's rota.",
    )
    max_showing_dates_shown = models.PositiveSmallIntegerField(
        default=5,
        help_text=(
            "Maximum number of future showing dates to display on the public event "
            "detail page before collapsing extras into a 'Show more' section. "
            "Set to 0 to always show all dates."
        ),
    )
    programme_copy_summary_max_chars = models.PositiveSmallIntegerField(
        default=450,
        help_text="Maximum length of an event's copy summary (the listing blurb).",
    )
    programme_event_terms_min_words = models.PositiveSmallIntegerField(
        default=3,
        help_text="Minimum word count in an event's terms before it can be confirmed.",
    )
    programme_media_max_size_mb = models.PositiveSmallIntegerField(
        default=5,
        help_text="Maximum size in megabytes for an uploaded event image.",
    )
    thumbnail_crop_width = models.PositiveSmallIntegerField(
        default=600,
        help_text=(
            "Width of the programme card image ratio (e.g. 2 for 2:3, or 600 for 600×900). "
            "Used when padding uploaded images with letterbox bars and when generating typographic posters. "
            "Default 600 (2:3 portrait)."
        ),
    )
    thumbnail_crop_height = models.PositiveSmallIntegerField(
        default=900,
        help_text=(
            "Height of the programme card image ratio (e.g. 3 for 2:3, or 900 for 600×900). "
            "Default 900 (2:3 portrait)."
        ),
    )
    programme_accent_colour = models.CharField(
        max_length=7,
        default="#e91e8c",
        verbose_name="Programme accent colour",
        help_text=(
            "The primary brand colour used in the public programme (hex, e.g. #e91e8c). "
            "Shown as a suggested bar colour when editing event images."
        ),
    )

    # --- Mailout ---
    mailout_details_days_ahead = models.PositiveSmallIntegerField(
        default=9,
        help_text=(
            "This setting controls the members mailout — the periodic programme newsletter "
            "sent to people on the membership list (not volunteers, not the public website). "
            "Events whose next showing falls within this many days from the mailout send date "
            "will have their full event copy (synopsis, terms, etc.) included in the mailout. "
            "Events further away than this threshold, but within the listings window below, "
            "appear as brief listings only. Default is 9 days."
        ),
    )
    mailout_listings_days_ahead = models.PositiveSmallIntegerField(
        default=14,
        help_text=(
            "The outer window for the members mailout. Events whose next showing falls within "
            "this many days from the mailout send date will appear as brief listings (title, "
            "date, and time) even if they are outside the detailed copy window above. "
            "Events beyond this window are not included in the mailout at all. Default is 14 days."
        ),
    )

    # --- Membership ---
    membership_length_days = models.PositiveSmallIntegerField(
        default=365,
        help_text="Default length of a new membership in days. Only used when membership expiry is enabled.",
    )
    default_training_expiry_months = models.PositiveSmallIntegerField(
        default=12,
        help_text=(
            "Months after which a training record is shown as 'out of date' on the volunteer list. "
            "This is informational only — it does not affect rota sign-up. "
            "The training gate checks for any record, however old."
        ),
    )

    # --- Dashboard ---
    rota_gap_min_missing = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            "Show the 'rota gaps' dashboard widget for showings with at least this many "
            "unfilled required slots. Set to 0 to use only the percentage threshold."
        ),
    )
    rota_gap_min_pct = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Show the 'rota gaps' dashboard widget for showings where at least this "
            "percentage of required slots are unfilled (0–100). Set to 0 to use only "
            "the count threshold."
        ),
    )

    # --- Stats & programming ---
    programming_min_event_shifts = models.PositiveSmallIntegerField(
        default=10,
        verbose_name="Programming eligibility threshold",
        help_text=(
            "Minimum confirmed non-training shifts before a volunteer is considered ready to "
            "programme their own event. Shown on the volunteer stats page as a target — "
            "never enforced by the system."
        ),
    )
    stats_programming_note = models.TextField(
        blank=True,
        default="",
        verbose_name="Programming eligibility note",
        help_text=(
            "Optional extra text shown below the programming eligibility count on the volunteer stats page. "
            "Plain text only. Leave blank to show nothing."
        ),
    )
    stats_training_tag_slugs = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tags excluded from shift count",
        help_text=(
            "Events tagged with any of these are excluded from a volunteer's confirmed shift "
            "count on the stats page. Use this to separate training and induction sessions "
            "from regular programming activity."
        ),
    )

    # --- Volunteers ---
    general_training_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Show General Safety Training records and prompts across the volunteer list, "
            "profile 'Key dates', and training report. Disable if your venue does not run "
            "General Safety Training — role-specific training records remain available "
            "regardless of this setting. The GST training type is also hidden from the "
            "'add training record' form when disabled."
        ),
    )
    volunteer_dormancy_days = models.PositiveSmallIntegerField(
        default=365,
        help_text=(
            "Mark active volunteers as Dormant if they have not logged in for this many days. "
            "Dormant is a soft, reversible label: it does not disable login or rota signup. "
            "Set to 0 to never auto-mark dormancy. "
            "Applied by the 'auto_dormancy' management command (run periodically, e.g. via cron) "
            "and surfaced on the volunteer pool-health dashboard."
        ),
    )
    volunteer_never_logged_in_grace_days = models.PositiveSmallIntegerField(
        default=90,
        help_text=(
            "Mark active volunteers who have never logged in as Dormant once this many days "
            "have passed since their account was created (they were inducted but never engaged — "
            "likely re-induction candidates). Set to 0 to never auto-mark these. "
            "Applied by the 'auto_dormancy' command."
        ),
    )
    volunteer_purge_days = models.PositiveSmallIntegerField(
        default=1095,
        help_text=(
            "Flag dormant/retired volunteers as candidates for anonymisation (GDPR data "
            "minimisation) once their last activity is older than this many days. "
            "Set to 0 to never flag purge candidates. Surfaced on the pool-health dashboard; "
            "acted on only via the manual 'purge_stale_volunteers' command — never automatically."
        ),
    )

    DIGEST_DAY_DISABLED = 0
    DIGEST_DAY_CHOICES = [
        (0, "Disabled"),
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]
    volunteer_digest_day = models.PositiveSmallIntegerField(
        default=4,
        choices=DIGEST_DAY_CHOICES,
        help_text=(
            "Day of the week on which the volunteer digest email is sent. "
            "The scheduler fires the digest command daily at 09:00; this setting "
            "controls which day it actually sends. Set to Disabled to suppress sending "
            "without stopping the scheduler container."
        ),
    )

    # --- Guidance URLs ---
    image_copyright_guidance_url = models.URLField(
        blank=True,
        default="",
        max_length=500,
        help_text="Link shown next to the image upload field — e.g. a Nextcloud doc on image rights.",
    )
    alt_text_guidance_url = models.URLField(
        blank=True,
        default="https://design102.blog.gov.uk/2022/01/14/whats-the-alternative-how-to-write-good-alt-text/",
        max_length=500,
        help_text=(
            "Alt text (alternative text) is a short written description of an image, "
            "read aloud by screen readers for blind and partially-sighted users and shown "
            "when an image fails to load. This field sets a link shown next to the alt text "
            "input when uploading event images — point it at a guide to writing good alt text. "
            "Leave blank to hide the link."
        ),
    )
    access_rider_guidance_url = models.URLField(
        blank=True,
        default="https://weareunlimited.org.uk/resource/creating-your-own-access-rider/",
        max_length=500,
        help_text="Link shown in the Access Rider section of the volunteer profile — guidance on writing an access rider. Leave blank to hide the link.",
    )
    ticket_link_guidance_html = models.TextField(
        blank=True,
        default="",
        verbose_name="Ticket link setup guidance",
        help_text=(
            "HTML shown in a collapsible panel directly below the ticket link field on the "
            "event edit form. Use this to guide programmers through setting up tickets on "
            "your chosen platform. Leave blank to hide the panel entirely."
        ),
    )
    film_programming_guide_url = models.URLField(
        blank=True,
        default="",
        verbose_name="Film programming guide URL",
        help_text=(
            "URL linked at the bottom of the ticket link setup guide panel on the event edit form. "
            "Typically a full guide to your ticketing platform. Leave blank to omit the link."
        ),
    )

    # --- External APIs ---
    omdb_api_key = models.CharField(
        blank=True,
        default="",
        max_length=256,
        verbose_name="OMDb API key",
        help_text=(
            "API key for the Open Movie Database (OMDb). Used for film search and metadata import. "
            "Get a free key at https://www.omdbapi.com/apikey.aspx. "
            "If set here, this takes precedence over the OMDB_API_KEY environment variable."
        ),
    )
    certificate_lookup_url = models.CharField(
        blank=True,
        default="https://www.bbfc.co.uk/search?q={title}",
        max_length=512,
        verbose_name="Certificate lookup URL",
        help_text=(
            "URL template for looking up a film's certificate. "
            "Use {title} and {year} as placeholders — they will be URL-encoded and substituted when the link is generated. "
            "Example (BBFC): https://www.bbfc.co.uk/search?q={title} "
            "Leave blank to hide the lookup link."
        ),
    )

    # --- Collectives public page ---
    collectives_intro = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Introductory copy shown at the top of the public /labs/collectives/ page. "
            "Plain text. Leave blank to use the built-in default."
        ),
    )
    collectives_mailing_list_signup_url = models.URLField(
        blank=True,
        default="",
        max_length=500,
        verbose_name="Mailing list sign-up URL",
        help_text=(
            "URL for the mailing list sign-up page, shown in the help box on the "
            "<a href='/toolkit/labs/collectives/'>Collectives page</a>. "
            "Leave blank to hide the mailing list hint entirely."
        ),
    )

    # --- Donations page ---
    donations_intro = models.TextField(
        blank=True,
        default=(
            "<p>The most valuable things you can give us are your time, energy, and ideas. "
            "If you want to get involved, the best place to start is by volunteering at events "
            "or joining one of our working groups.</p>"
            "<p>That said, we do sometimes need physical things too, and this page lists what’s "
            "currently useful. Before bringing anything, please check the status: "
            "<strong>Wanted</strong> means yes please; <strong>Check first</strong> means it might "
            "work but talk to us first; <strong>Not needed</strong> means we’re already well "
            "supplied or can’t use it.</p>"
            "<p>One of our most precious resources as a DIY space is space itself. We share the "
            "building across a lot of different groups and uses, and it’s much easier to add "
            "things than to remove them. Please don’t drop anything off without checking first, "
            "even if it seems obviously useful.</p>"
        ),
        help_text="Introductory copy shown at the top of the public donations page. HTML.",
    )

    # --- Public site navigation ---
    show_donations_in_public_nav = models.BooleanField(
        default=False,
        help_text=(
            "Show a 'Donations wishlist' link in the public site navigation, "
            "pointing at the labs donations list. Off by default."
        ),
    )

    # --- Site-wide banner ---
    banner_active = models.BooleanField(
        default=False,
        help_text=(
            "Show a site-wide announcement banner at the top of every page "
            "(public and toolkit) for important notices."
        ),
    )
    BANNER_LEVEL_INFO = "info"
    BANNER_LEVEL_WARNING = "warning"
    BANNER_LEVEL_CRITICAL = "critical"
    BANNER_LEVEL_CHOICES = [
        (BANNER_LEVEL_INFO, "Info (blue)"),
        (BANNER_LEVEL_WARNING, "Warning (amber)"),
        (BANNER_LEVEL_CRITICAL, "Critical (red)"),
    ]
    banner_level = models.CharField(
        max_length=10,
        choices=BANNER_LEVEL_CHOICES,
        default=BANNER_LEVEL_INFO,
        help_text="Colour scheme for the banner.",
    )
    banner_text = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Banner content. Plain text; line breaks are preserved. "
            "Edit this and re-save to issue an updated notice — visitors who "
            "previously dismissed the banner will see the new version."
        ),
    )
    banner_dismissible = models.BooleanField(
        default=True,
        help_text=(
            "Allow visitors to dismiss the banner. Their choice is stored in "
            "their browser only, and resets when the banner text changes."
        ),
    )

    # --- Community exchange ---
    community_exchange_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable the community exchange — a browseable catalogue where volunteers can lend tools "
            "or give away items to one another. When off, the section is hidden from the nav."
        ),
    )

    # --- Lost & found ---
    lost_and_found_retain_days = models.PositiveSmallIntegerField(
        default=60,
        help_text=(
            "Number of days to retain unclaimed lost and found items before flagging for disposal. "
            "Set to 0 to disable flagging."
        ),
    )

    # --- Bulletins ---
    bulletin_default_expiry_days = models.PositiveSmallIntegerField(
        default=30,
        help_text=(
            "How many days a bulletin stays active if no explicit expiry is set. "
            "Default is 30. Set to 0 to keep bulletins active indefinitely by default."
        ),
    )
    bulletin_guidance = models.TextField(
        blank=True,
        default=(
            "Use bulletins for short notices relevant to the whole volunteer community: "
            "policy changes, updated contact details, new resources, or anything a volunteer "
            "needs to know before their next event.\n\n"
            "Good examples: \"Keyholders can now be contacted via keyholders@lists.example.com "
            "— please use this if your event needs a keyholder.\" / \"The Managing Immediate "
            "Risk Policy has been updated and applies to all volunteers: [link]\" / \"The "
            "projection booth door code has changed — use the code previously assigned to the "
            "cleaning cupboard.\"\n\n"
            "Before you post, remember that bulletins go to all 500+ active volunteers. "
            "If you need to send a callout ahead of an event, mailing lists are a better route."
        ),
        help_text=(
            "Guidance shown on the 'Post a bulletin' form. Use this to set local "
            "conventions: what kinds of notices belong here, how to write them, "
            "and examples of good and bad bulletins."
        ),
    )

    # --- Event links ---
    eventlink_extra_allowed_domains = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Extra domains allowed for event resource links, one per line. "
            "Subdomains are accepted (e.g. 'nextcloud.example.org' also allows "
            "'files.nextcloud.example.org'). Built-in domains (riseup.net, "
            "nextcloud.com/org, chat.whatsapp.com, linktr.ee) are always allowed."
        ),
    )

    BULLETIN_POST_ALL = "all"
    BULLETIN_POST_PROGRAMMER = "programmer"
    BULLETIN_POST_PANOPTICON = "panopticon"
    BULLETIN_POST_CHOICES = [
        (BULLETIN_POST_ALL, "All volunteers"),
        (BULLETIN_POST_PROGRAMMER, "Programmers and Panopticon"),
        (BULLETIN_POST_PANOPTICON, "Panopticon only"),
    ]
    bulletin_post_permission = models.CharField(
        max_length=12,
        choices=BULLETIN_POST_CHOICES,
        default=BULLETIN_POST_PROGRAMMER,
        help_text="Who can post new bulletins.",
    )

    # --- Runtime-configurable feature access levels ---
    PERM_VOLUNTEER = "volunteer"
    PERM_PROGRAMMER = "programmer"
    PERM_PANOPTICON = "panopticon"
    PERMISSION_LEVEL_CHOICES = [
        (PERM_VOLUNTEER, "All volunteers"),
        (PERM_PROGRAMMER, "Programmer+"),
        (PERM_PANOPTICON, "Panopticon only"),
    ]

    perm_diary_read = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_VOLUNTEER,
        verbose_name="Diary — view diary list",
        help_text="Who can view the diary editing list (read-only for volunteers; event editing always requires Programmer+).",
    )
    perm_diary_calendar = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — calendar",
        help_text="Who can access the calendar edit view.",
    )
    perm_programming_queue_read = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_VOLUNTEER,
        verbose_name="Diary — programming queue (view)",
        help_text="Who can view the programming queue.",
    )
    perm_programming_queue_write = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — programming queue (change status)",
        help_text="Who can approve, return, or skip events in the programming queue.",
    )
    perm_event_templates = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — event templates",
        help_text="Who can access event templates (list and detail). Template import always requires Panopticon.",
    )
    perm_event_tags = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — event tags",
        help_text="Who can edit event tags.",
    )
    perm_roles = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — roles",
        help_text="Who can edit rota roles.",
    )
    perm_rooms = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — rooms",
        help_text="Who can edit rooms.",
    )
    perm_diary_reports = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — reports",
        help_text="Who can access copy, terms, and text reports.",
    )
    perm_printed_programmes = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Diary — printed programmes",
        help_text="Who can upload printed programmes.",
    )
    perm_rota_vacancies = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_VOLUNTEER,
        verbose_name="Rota — vacancies page",
        help_text="Who can see the rota vacancies page.",
    )
    perm_donations_manage = models.CharField(
        max_length=12, choices=PERMISSION_LEVEL_CHOICES, default=PERM_PROGRAMMER,
        verbose_name="Website — donations manage",
        help_text="Who can access the donations management page.",
    )

    # --- Last-gasp re-engagement email ---
    last_gasp_email_enabled = models.BooleanField(
        default=False,
        verbose_name="Enable last-gasp email features",
        help_text=(
            "A last-gasp email is a final, optional re-engagement message sent to a volunteer "
            "before their account is anonymised or deleted under data-retention rules — a courtesy "
            "“we’re about to remove your data, here’s a chance to come back” note. "
            "When enabled, the pool health page shows a button to send one to each purge candidate. "
            "(The email-address export, for sending outside the toolkit, is always available regardless of this setting.)"
        ),
    )
    last_gasp_email_subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subject line. Use {name} for the volunteer's name and {venue} for the venue name.",
    )
    last_gasp_email_body = models.TextField(
        blank=True,
        help_text=(
            "Body text. Use {name} for the volunteer's name and {venue} for the venue name. "
            "Can be left blank even when the feature is enabled — the compose page will still open "
            "so you can write a message from scratch each time."
        ),
    )
    last_gasp_cooldown_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="How many days must pass before a second last-gasp email can be sent to the same volunteer.",
    )

    # --- Suspension email ---
    suspension_email_subject = models.CharField(
        max_length=300,
        blank=True,
        default="Your volunteer account at {venue}",
        verbose_name="Suspension email subject",
        help_text=(
            "Subject line for the email offered when suspending a volunteer. "
            "Supports {name} and {venue} variables."
        ),
    )
    suspension_email_body = models.TextField(
        blank=True,
        default=(
            "Hi {name},\n\n"
            "This is to let you know that your volunteer account at {venue} has been suspended. "
            "Your login is currently disabled and you have been removed from upcoming shifts.\n\n"
            "If you have any questions or would like to discuss this, please get in touch.\n\n"
            "Best wishes,\n{venue}"
        ),
        verbose_name="Suspension email body",
        help_text=(
            "Body of the email offered when suspending a volunteer. "
            "Supports {name} and {venue} variables."
        ),
    )

    # --- Structured cost terms ---
    structured_cost_terms_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable structured cost fields (cost type, flat fee, % split, etc.) on event edit forms. "
            "When on, programmers can record the deal type directly rather than free-texting it into Terms. "
            "The Terms textarea remains available for unusual arrangements and legacy records."
        ),
    )
    structured_cost_required = models.BooleanField(
        default=False,
        help_text=(
            "Require cost type to be set (to something other than TBC) before any showing can be confirmed. "
            "Only takes effect when structured cost terms are enabled above. "
            "When cost type is set, the terms word-count check is automatically waived; "
            "TBC still falls back to the terms word-count check."
        ),
    )

    _CACHE_KEY = "diary.site_config.v1"

    class Meta:
        db_table = "SiteConfiguration"
        verbose_name = "Site configuration"
        verbose_name_plural = "Site configuration"

    def __str__(self):
        return "Site configuration"

    @staticmethod
    def _passes_level(user, level):
        """Return True if user meets the given PERM_* access level."""
        if level == SiteConfiguration.PERM_VOLUNTEER:
            return user.has_perm("diary.change_rotaentry")
        if level == SiteConfiguration.PERM_PROGRAMMER:
            return user.has_perm("toolkit.write")
        return user.is_superuser

    def save(self, *args, **kwargs):
        # Singleton: always pk=1
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete(self._CACHE_KEY)

    def delete(self, *args, **kwargs):
        # Don't allow the singleton to be deleted
        pass

    @classmethod
    def load(cls):
        # Cache the singleton to avoid a SELECT per render. Local-memory
        # cache is per-worker; the 5-minute TTL bounds staleness in other
        # workers after a save.
        from django.core.cache import cache

        config = cache.get(cls._CACHE_KEY)
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls._CACHE_KEY, config, timeout=300)
        return config


def get_site_config():
    """Return the SiteConfiguration singleton, creating it on first call."""
    return SiteConfiguration.load()


class VolunteerEventMark(models.Model):
    """Per-user interest markers on events shown in the rota.

    ★ Star = bookmark / personal interest flag.
    🌙 Shadow = deprioritise; collapses the event to title-only in the rota view.
    """

    MARK_STAR = "star"
    MARK_SHADOW = "shadow"
    MARK_CHOICES = [(MARK_STAR, "Star"), (MARK_SHADOW, "Shadow")]

    volunteer = models.ForeignKey(
        "members.Volunteer",
        on_delete=models.CASCADE,
        related_name="event_marks",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="volunteer_marks",
    )
    mark_type = models.CharField(max_length=10, choices=MARK_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("volunteer", "event")]

    def __str__(self):
        return f"volunteer:{self.volunteer_id} {self.mark_type} event:{self.event_id}"
