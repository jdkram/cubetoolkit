"""Simple filter for use in django templates that allows extraction of a given
key from a dictionary"""

from django import template

register = template.Library()


@register.filter(name="lookup")
def lookup(dictionary, key):
    """Simple filter for use in django templates that allows extraction of a
    given key from a dictionary"""
    if key in dictionary:
        return dictionary[key]
    else:
        return ""


@register.simple_tag
def showing_for_room_at(showings, room, time_slot):
    """Return the first showing with a RoomBooking for room starting at time_slot.

    Uses visible_room_bookings so cancelled/rejected dates free their rooms.
    """
    for showing in showings:
        if any(
            rb.room_id == room.pk and rb.start == time_slot
            for rb in showing.visible_room_bookings
        ):
            return showing
    return None


@register.simple_tag
def other_room_bookings_at(showings, time_slot):
    """Return (RoomBooking, Showing) pairs for non-column rooms booked at time_slot."""
    result = []
    seen = set()
    for showing in showings:
        for rb in showing.visible_room_bookings:
            key = (rb.room_id, showing.pk)
            if not rb.room.show_column and rb.start == time_slot and key not in seen:
                seen.add(key)
                result.append((rb, showing))
    return result
