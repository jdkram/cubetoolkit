import logging
import datetime

from django.db import models
import django.utils.timezone
from django.db.models.query import QuerySet

from toolkit.diary.validators import validate_in_future
from .rota import Role, RotaEntry

logger = logging.getLogger(__name__)


class FutureDateTimeField(models.DateTimeField):
    """DateTime field that can only be set to times in the future.
    Used for Showing start times"""

    default_error_messages = {
        "invalid": "Date may not be in the past",
    }
    default_validators = [validate_in_future]


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
    room = models.ForeignKey(
        Room, on_delete=models.PROTECT, related_name="bookings"
    )
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
    roles = models.ManyToManyField("diary.Role", through="diary.RotaEntry")

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
        if (
            not force
            and self.pk is not None
            and (self.in_past() or self.original_start_in_past())
        ):
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
            start_offset = datetime.timedelta(
                minutes=default.start_delta_minutes
            )
            booking_start = (
                self.start
                + datetime.timedelta(days=default.date_offset)
                + start_offset
            )
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
