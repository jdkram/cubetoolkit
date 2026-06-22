import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Set of known preferences and default values:
KNOWN_PREFS = {
    "daysahead": str(settings.EDIT_INDEX_DEFAULT_DAYS_AHEAD),
}


def get_preferences(session, volunteer=None):
    return {pref: get_preference(session, pref, volunteer=volunteer) for pref in KNOWN_PREFS}


def get_preference(session, name, volunteer=None):
    if name == "daysahead" and volunteer is not None:
        return str(volunteer.diary_days_ahead)
    if name in KNOWN_PREFS:
        return session.get(f"editpref_{name}", KNOWN_PREFS[name])
    return None


def set_preferences(session, prefs_requested, volunteer=None):
    for name, value in prefs_requested.items():
        set_preference(session, name, value, volunteer=volunteer)


def set_preference(session, name, value, volunteer=None):
    if name in KNOWN_PREFS:
        logger.debug(f"Set pref {name} to '{value}'")
        value = str(value)[:10]
        session[f"editpref_{name}"] = value
        if name == "daysahead" and volunteer is not None:
            try:
                volunteer.diary_days_ahead = int(value)
                volunteer.save(update_fields=["diary_days_ahead"])
            except Exception:
                pass
