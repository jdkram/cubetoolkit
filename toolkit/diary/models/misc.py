import io
import logging
import datetime
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import models
from django.conf import settings
from django.db.models.query import QuerySet
from django.utils.text import slugify

import toolkit.util.image as imagetools

from .event import Event

logger = logging.getLogger(__name__)


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
            'E.g. "People sitting in an outdoor cinema under a night sky."'
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
        # TAGS_WITHOUT_TERMS is settings-only — no SiteConfiguration counterpart.
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


class DiaryIdea(models.Model):
    month = models.DateField(editable=False)
    ideas = models.TextField(max_length=16384, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "DiaryIdeas"

    def __str__(self):
        return f"{self.month.month}/{self.month.year}"


try:
    import pdf2image

    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    # poppler isn't installed on this host — thumbnails are skipped and the
    # gallery falls back to a placeholder icon.
    _PDF2IMAGE_AVAILABLE = False


class PrintedProgrammeQuerySet(QuerySet):
    def seasons_overlapping(self, start, end):
        """Select printed programme seasons whose month range overlaps [start, end]"""
        # The idea being that even if 'start' is some day after the first of
        # the month, the season covering that month is still returned
        start_date = datetime.date(start.year, start.month, 1)
        end_date = datetime.date(end.year, end.month, 1)

        return self.filter(start_month__lte=end_date, end_month__gte=start_date)


class PrintedProgramme(models.Model):
    # Both stored as the 1st of the month. A "season" is the inclusive
    # month range [start_month, end_month]; single-month entries have
    # start_month == end_month.
    start_month = models.DateField(editable=False)
    end_month = models.DateField(editable=False)
    programme = models.FileField(
        upload_to="printedprogramme",
        max_length=256,
        null=False,
        blank=False,
        verbose_name="Programme PDF",
    )
    # First page of the PDF, rendered on save() for the public gallery.
    # Left blank if pdf2image/poppler isn't available on this host.
    thumbnail = models.ImageField(
        upload_to="printedprogramme_thumbnails",
        max_length=256,
        null=True,
        blank=True,
        editable=False,
    )
    designer = models.CharField(max_length=256, blank=True)
    notes = models.TextField(max_length=8192, null=True, blank=True)

    objects = PrintedProgrammeQuerySet.as_manager()

    class Meta:
        db_table = "PrintedProgrammes"

    def __str__(self):
        if self.start_month == self.end_month:
            return f"Printed programme for {self.start_month.month}/{self.start_month.year}"
        return (
            f"Printed programme for {self.start_month:%b %Y}"
            f"–{self.end_month:%b %Y}"
        )

    def season_name(self):
        """Approximate season name for the start month.

        Nov-Jan = Winter, Feb-Apr = Spring, May-Jul = Summer, Aug-Oct = Autumn.
        This is a display label, not a precision astronomical calendar.
        """
        index = ((self.start_month.month - 11) % 12) // 3
        return ("Winter", "Spring", "Summer", "Autumn")[index]

    def season_label(self):
        """E.g. "Spring 2025 · Feb–Apr" for the public gallery."""
        if self.start_month.month == self.end_month.month:
            months = self.start_month.strftime("%b")
        else:
            months = (
                f"{self.start_month.strftime('%b')}"
                f"–{self.end_month.strftime('%b')}"
            )
        return f"{self.season_name()} {self.start_month.year} · {months}"

    def save(self, *args, **kwargs):
        # Enforce start/end month columns always being the 1st of the month:
        if self.start_month.day != 1:
            logger.error(
                "PrintedProgramme has start_month value which isn't the 1st"
                " of the month"
            )
            self.start_month = datetime.date(
                self.start_month.year, self.start_month.month, 1
            )
        if self.end_month.day != 1:
            logger.error(
                "PrintedProgramme has end_month value which isn't the 1st"
                " of the month"
            )
            self.end_month = datetime.date(
                self.end_month.year, self.end_month.month, 1
            )
        self._generate_thumbnail()
        return super().save(*args, **kwargs)

    def _generate_thumbnail(self):
        # Render the first page of the uploaded PDF as a JPEG thumbnail.
        # Recomputed on every save, since the file may have been replaced
        # without the name changing (same reasoning as MediaItem.mimetype).
        if not _PDF2IMAGE_AVAILABLE or not self.programme:
            return

        try:
            self.programme.seek(0)
            pages = pdf2image.convert_from_bytes(
                self.programme.read(), first_page=1, last_page=1
            )
            self.programme.seek(0)
        except Exception:
            logger.exception(
                f"Failed to render thumbnail for {self.programme.name}"
            )
            return

        if not pages:
            return

        buffer = io.BytesIO()
        pages[0].convert("RGB").save(buffer, format="JPEG", quality=85)
        filename = f"{Path(self.programme.name).stem}.jpg"
        self.thumbnail.save(
            filename, ContentFile(buffer.getvalue()), save=False
        )


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
        "diary.Event",
        on_delete=models.CASCADE,
        related_name="volunteer_marks",
    )
    mark_type = models.CharField(max_length=10, choices=MARK_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("volunteer", "event")]

    def __str__(self):
        return f"volunteer:{self.volunteer_id} {self.mark_type} event:{self.event_id}"
