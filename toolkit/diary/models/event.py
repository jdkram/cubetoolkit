import re
import logging

from django.db import models
import django.utils.timezone
import nh3
from django.utils.safestring import mark_safe
from django.conf import settings

from toolkit.diary.validators import validate_event_link_url
from .site_config import get_site_config

logger = logging.getLogger(__name__)


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
    tags = models.ManyToManyField(
        "diary.EventTag", db_table="Event_Tags", blank=True
    )

    duration = models.TimeField(null=True)

    outside_hire = models.BooleanField(default=False)
    hire_name = models.CharField(
        max_length=256,
        blank=True,
        verbose_name="Hirer name / organisation",
        help_text="Who is hiring the venue? Shown on the rota so everyone knows who to liaise with.",
    )
    private = models.BooleanField(default=False)

    media = models.ManyToManyField(
        "diary.MediaItem", db_table="Event_MediaItems"
    )

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
        _legacy = {
            "all_ages": "All ages welcome",
            "16_plus": "16+ only",
            "18_plus": "18+ only",
        }
        return _legacy.get(self.age_restriction, self.age_restriction)

    def all_showings_in_past(self):
        return all(s.in_past() for s in self.showings.all())

    def all_showings_confirmed(self) -> bool:
        return all(s.confirmed for s in self.showings.all())

    # Tags and attributes permitted in stored HTML copy.
    # Script tags, event-handler attributes (onclick etc.) and javascript:
    # hrefs are stripped by nh3 regardless of this allowlist.
    _COPY_ALLOWED_TAGS = {
        "a",
        "abbr",
        "b",
        "blockquote",
        "br",
        "cite",
        "code",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "i",
        "img",
        "li",
        "ol",
        "p",
        "s",
        "strike",
        "strong",
        "sub",
        "sup",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
    _COPY_ALLOWED_ATTRS = {
        "a": {"href", "title", "target"},
        "img": {"src", "alt", "width", "height", "border"},
        "td": {"colspan", "rowspan"},
        "th": {"colspan", "rowspan"},
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

        return mark_safe(
            nh3.clean(
                result,
                tags=self._COPY_ALLOWED_TAGS,
                attributes=self._COPY_ALLOWED_ATTRS,
            )
        )

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
        "diary.EventTemplate",
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
