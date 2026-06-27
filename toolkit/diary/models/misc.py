import logging
import datetime

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
