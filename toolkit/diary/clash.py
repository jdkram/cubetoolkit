# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
from django.db.models import Q

from .models import RoomBooking


def find_clashes(room_booking):
    """Return a QuerySet of confirmed RoomBookings in the same room that overlap
    with room_booking's time window.

    Both bookings must have a known end time to be compared; open-ended bookings
    (end=None) are excluded on both sides to avoid false positives.

    Overlap condition (half-open intervals): start_A < end_B AND start_B < end_A
    """
    if room_booking.end is None:
        return RoomBooking.objects.none()

    return (
        RoomBooking.objects.filter(
            room=room_booking.room,
            showing__confirmed=True,
            end__isnull=False,
            start__lt=room_booking.end,
            end__gt=room_booking.start,
        )
        .exclude(pk=room_booking.pk)
        .select_related("showing__event", "room")
    )
