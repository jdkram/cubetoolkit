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

    # Free text film information:
    film_information = models.CharField(max_length=256, null=False, blank=True)

    copy = models.TextField(max_length=8192, null=True, blank=True)
    copy_summary = models.TextField(max_length=4096, null=True, blank=True)

    # Following flag is True when the event copy has been imported from the
    # "legacy" toolkit; the bizarre text wrapping will be fixed up before
    # display, regex will be applied to turn http://.* into links, etc.
    legacy_copy = models.BooleanField(
        default=False, null=False, editable=False
    )

    terms = models.TextField(max_length=4096, null=True, blank=True)
    notes = models.TextField(
        max_length=4096,
        null=True,
        blank=True,
        verbose_name="Programmer's notes",
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
        # # If the media item isn't associated with any events, delete it:
        # # ACTUALLY: let's keep it. Disk space is cheap, etc.
        # if media_item.event_set.count() == 0:
        #    media_item.delete()

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
    """

    showing = models.ForeignKey(
        "Showing", on_delete=models.CASCADE, related_name="room_bookings"
    )
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

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
        if not force and (self.in_past() or self.original_start_in_past()):
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

    # created_at = models.DateTimeField(auto_now_add=True)
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
        help_text="Show event tag badges on the edit rota page.",
    )
    rota_clear_email_prompt_enabled = models.BooleanField(
        default=True,
        help_text="When clearing a rota slot, prompt the user to email the volunteers list.",
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

    # --- Calendar ---
    calendar_slot_min_hour = models.PositiveSmallIntegerField(
        default=10,
        help_text=(
            "Earliest hour shown in the 3-day and week calendar views (0–23). "
            "Events before this time are still shown but the grid starts here. "
            "Default 10 hides the dead early-morning hours."
        ),
    )

    # --- Programme limits ---
    max_count_per_role = models.PositiveSmallIntegerField(
        default=8,
        help_text="Maximum number of slots per role on a single showing's rota.",
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

    # --- Mailout ---
    mailout_details_days_ahead = models.PositiveSmallIntegerField(
        default=9,
        help_text="Days ahead to include detailed event copy in the members mailout.",
    )
    mailout_listings_days_ahead = models.PositiveSmallIntegerField(
        default=14,
        help_text="Days ahead to include listings in the members mailout.",
    )

    # --- Membership ---
    membership_length_days = models.PositiveSmallIntegerField(
        default=365,
        help_text="Default length of a new membership in days. Only used when membership expiry is enabled.",
    )
    default_training_expiry_months = models.PositiveSmallIntegerField(
        default=12,
        help_text="Months after which volunteer training records are considered expired.",
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

    # --- Volunteers ---
    volunteer_dormancy_months = models.PositiveSmallIntegerField(
        default=24,
        help_text=(
            "Mark active volunteers as Dormant if they have not logged in for this many months. "
            "Set to 0 to never auto-enforce dormancy. "
            "Run the 'auto_dormancy' management command periodically (e.g. via cron) to apply this rule."
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
        default="",
        max_length=500,
        help_text="Link shown next to the alt-text field — e.g. a guide to writing good alt text.",
    )

    _CACHE_KEY = "diary.site_config.v1"

    class Meta:
        db_table = "SiteConfiguration"
        verbose_name = "Site configuration"
        verbose_name_plural = "Site configuration"

    def __str__(self):
        return "Site configuration"

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
