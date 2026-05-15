# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
from django.db.models import Q

from .models import RoomBooking


def find_clashes(room_booking):
    """Return a QuerySet of confirmed RoomBookings in the same room that overlap
    with room_booking's time window.

    Overlap logic (open-interval at end):
      existing.start < booking.end  AND  (existing.end IS NULL OR existing.end > booking.start)

    If room_booking.end is None it is treated as open-ended (overlaps anything
    that starts after room_booking.start).
    """
    qs = (
        RoomBooking.objects.filter(
            room=room_booking.room,
            showing__confirmed=True,
        )
        .exclude(pk=room_booking.pk)
        .select_related("showing__event", "room")
    )

    # If our booking has an end, any existing booking that starts before it overlaps.
    if room_booking.end is not None:
        qs = qs.filter(start__lt=room_booking.end)

    # The existing booking must end after our start (or have no end — open-ended).
    qs = qs.filter(Q(end__isnull=True) | Q(end__gt=room_booking.start))

    return qs
