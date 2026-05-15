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


@register.filter(name="showing_for_room")
def showing_for_room(showings, room):
    """Return the first showing in the list that has a RoomBooking for room, or None."""
    for showing in showings:
        if any(rb.room_id == room.pk for rb in showing.room_bookings.all()):
            return showing
    return None
