# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
from django.db.models import Q

from .models import RoomBooking


def find_clashes(room_booking):
    """Return a QuerySet of confirmed RoomBookings in the same room that overlap
    with room_booking's time window.

    If room_booking itself has no end time, there is nothing meaningful to compare
    against, so return an empty set.

    For existing bookings: a booking with a known end overlaps if
    start_A < end_B AND start_B < end_A (half-open interval condition).
    An open-ended existing booking (end=None) is conservatively treated as a
    clash if it starts before room_booking ends — it may never finish.
    """
    if room_booking.end is None:
        return RoomBooking.objects.none()

    bounded_clashes = Q(
        end__isnull=False,
        start__lt=room_booking.end,
        end__gt=room_booking.start,
    )
    open_ended_clashes = Q(
        end__isnull=True,
        start__lt=room_booking.end,
    )

    return (
        RoomBooking.objects.filter(
            room=room_booking.room,
            showing__confirmed=True,
        )
        .filter(bounded_clashes | open_ended_clashes)
        .exclude(pk=room_booking.pk)
        .select_related("showing__event", "room")
    )
