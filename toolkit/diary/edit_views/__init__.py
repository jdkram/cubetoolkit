"""Diary edit views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; cross-module helpers live in _common.
The package re-exports every public name so urls.py and tests keep using
``from toolkit.diary.edit_views import X`` unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"

from .events import (
    _create_room_booking,
    event_detail_view,
    update_showing_status,
    confirm_all_showings,
    clone_event,
    batch_add_showings,
    edit_event_links,
    quick_create_open_session,
    _template_data,
    add_event,
    EditEventView,
    _build_cert_lookup_url,
)

from .diary_overview import (
    _return_to_editindex,
    cancel_edit,
    edit_diary_list,
    _is_light_colour,
    edit_diary_data,
    edit_diary_calendar,
    set_edit_preferences,
    edit_ideas,
)

from .showings import (
    _get_oneshot_roles_for_showing,
    _parse_oneshot_roles,
    edit_showing,
    _rooms_json,
    delete_showing,
)

from .reports import (
    view_terms_report_csv,
    view_event_field,
)

from .templates import (
    edit_event_templates,
    edit_event_template_detail,
    _export_template_json,
    import_event_template,
)

from .tags_roles_rooms import (
    edit_event_tags,
    edit_roles,
    printed_programme_edit,
    edit_rooms,
    edit_room_detail,
)

from .rota import (
    view_rota_vacancies,
    EditRotaView,
    edit_showing_rota_notes,
)

from .misc import (
    get_messages,
    toggle_event_mark,
    view_force_error,
)

from .site_config import (
    edit_site_configuration,
    generate_event_poster,
    programming_queue,
    update_event_programming_status,
)

from ._common import (
    _get_omdb_api_key,
    _film_json,
)

from .film import (
    omdb_search,
    _post_int_or_none,
    link_film,
    unlink_film,
)

__all__ = [
    "_return_to_editindex",
    "_create_room_booking",
    "cancel_edit",
    "edit_diary_list",
    "_is_light_colour",
    "edit_diary_data",
    "edit_diary_calendar",
    "set_edit_preferences",
    "event_detail_view",
    "update_showing_status",
    "confirm_all_showings",
    "clone_event",
    "batch_add_showings",
    "edit_event_links",
    "quick_create_open_session",
    "_template_data",
    "add_event",
    "_get_oneshot_roles_for_showing",
    "_parse_oneshot_roles",
    "edit_showing",
    "_rooms_json",
    "EditEventView",
    "edit_ideas",
    "delete_showing",
    "view_terms_report_csv",
    "view_event_field",
    "edit_event_templates",
    "edit_event_template_detail",
    "_export_template_json",
    "import_event_template",
    "edit_event_tags",
    "edit_roles",
    "printed_programme_edit",
    "view_rota_vacancies",
    "EditRotaView",
    "edit_showing_rota_notes",
    "get_messages",
    "toggle_event_mark",
    "view_force_error",
    "edit_site_configuration",
    "generate_event_poster",
    "edit_rooms",
    "edit_room_detail",
    "programming_queue",
    "update_event_programming_status",
    "_build_cert_lookup_url",
    "_get_omdb_api_key",
    "omdb_search",
    "_post_int_or_none",
    "link_film",
    "unlink_film",
    "_film_json",
]
