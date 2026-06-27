"""Diary data models, split per concern.

Cross-module ForeignKey/M2M targets use string references ("diary.ModelName")
so the submodules can be imported in any order without Python-level import
cycles; Django resolves them via the app registry.  Importers should use
``from toolkit.diary.models import X`` -- this package re-exports every public
name for back-compat with the old single-file models.py.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"

from .site_config import (
    DEFAULT_FILMS_START_BANNER_TEXT,
    SiteConfiguration,
    get_site_config,
)
from .event import (
    Event,
    EventLink,
    EventTemplateLink,
    EventTermsRevision,
    Film,
)
from .rota import (
    EventTemplate,
    EventTemplateRole,
    EventTemplateRoom,
    Role,
    RotaEntry,
)
from .showing import (
    FutureDateTimeField,
    Room,
    RoomBooking,
    Showing,
    ShowingQuerySet,
)
from .misc import (
    DiaryIdea,
    EventTag,
    EventTagQuerySet,
    MediaItem,
    PrintedProgramme,
    PrintedProgrammeQuerySet,
    VolunteerEventMark,
)

__all__ = [
    "DEFAULT_FILMS_START_BANNER_TEXT",
    "DiaryIdea",
    "Event",
    "EventLink",
    "EventTag",
    "EventTagQuerySet",
    "EventTemplate",
    "EventTemplateLink",
    "EventTemplateRole",
    "EventTemplateRoom",
    "EventTermsRevision",
    "Film",
    "FutureDateTimeField",
    "MediaItem",
    "PrintedProgramme",
    "PrintedProgrammeQuerySet",
    "Role",
    "Room",
    "RoomBooking",
    "RotaEntry",
    "Showing",
    "ShowingQuerySet",
    "SiteConfiguration",
    "VolunteerEventMark",
    "get_site_config",
]
