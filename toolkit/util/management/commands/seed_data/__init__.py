"""
Seed data loader for S&S Toolkit development database.

Loads TOML data files and exposes them as Python constants for use
by seed_dev_data.py management command.
"""

import tomllib
from pathlib import Path

DATA_DIR = Path(__file__).parent


def _load_toml(filename):
    """Load a TOML file from the seed_data directory."""
    with open(DATA_DIR / filename, "rb") as f:
        return tomllib.load(f)


# Roles
roles_data = _load_toml("roles.toml")
ROLES = roles_data["roles"]

# Rooms
rooms_data = _load_toml("rooms.toml")
ROOMS = rooms_data["rooms"]

# Tags
tags_data = _load_toml("tags.toml")
TAGS = tags_data["tags"]
TAG_COLOURS = {tc["tag"]: tuple(tc["rgb"]) for tc in tags_data["tag_colours"]}

# Volunteers
volunteers_data = _load_toml("volunteers.toml")
VOLUNTEERS = volunteers_data["volunteers"]

# Event Templates
templates_data = _load_toml("templates.toml")
EVENT_TEMPLATES = templates_data["templates"]

# Events (one-off and special events)
events_data = _load_toml("events.toml")
EVENTS = events_data["events"]

# Recurring events (weekly, biweekly, monthly)
recurring_data = _load_toml("recurring.toml")
WEEKLY_SUNDAY_EVENTS = recurring_data.get("weekly_sunday_events", [])
BIWEEKLY_SUNDAY_EVENTS = recurring_data.get("biweekly_sunday_events", [])
MONTHLY_EVENTS = recurring_data.get("monthly_events", [])

# Films (curated film pools for Sunday and Thursday screenings)
films_data = _load_toml("films.toml")
SUNDAY_FILMS = films_data.get("sunday_films", [])
THURSDAY_FILMS = films_data.get("thursday_films", [])

# Collectives
collectives_data = _load_toml("collectives.toml")
COLLECTIVES = collectives_data["collectives"]

# Donation items
donations_data = _load_toml("donations.toml")
DONATION_ITEMS = donations_data["items"]

# Generic cinema image used for all recurring film events
_RECURRING_FILM_IMAGE_URL = "https://images.pexels.com/photos/7991579/pexels-photo-7991579.jpeg?auto=compress&cs=tinysrgb&w=800"

__all__ = [
    "ROLES",
    "ROOMS",
    "TAGS",
    "TAG_COLOURS",
    "VOLUNTEERS",
    "EVENT_TEMPLATES",
    "EVENTS",
    "WEEKLY_SUNDAY_EVENTS",
    "BIWEEKLY_SUNDAY_EVENTS",
    "MONTHLY_EVENTS",
    "SUNDAY_FILMS",
    "THURSDAY_FILMS",
    "_RECURRING_FILM_IMAGE_URL",
    "COLLECTIVES",
    "DONATION_ITEMS",
]
