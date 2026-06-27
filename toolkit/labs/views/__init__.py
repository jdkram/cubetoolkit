"""Labs views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; the one genuinely cross-module helper
(``_user_volunteer``) lives in ``_common``. This package re-exports every
public view name so ``labs/urls.py`` (which does ``from . import views``)
and the one external importer (``toolkit/index/views.py`` pulls
``_unread_bulletins_for``) keep working unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"

from ._common import _user_volunteer
from .area_photos import area_photo_delete, area_photo_upload
from .bulletins import (
    BULLETIN_RATE_LIMIT_PER_HOUR,
    _active_bulletins_qs,
    _unread_bulletins_for,
    _user_can_post_bulletin,
    bulletin_add,
    bulletin_archive,
    bulletin_delete,
    bulletin_expire,
    bulletin_list,
    bulletin_pin,
    bulletin_read,
    bulletin_read_all,
)
from .collectives import (
    collective_edit,
    collective_join,
    collective_leave,
    collectives,
    collectives_print,
    collectives_public,
)
from .donations import donation_list, donation_manage
from .exchange import (
    exchange_add,
    exchange_edit,
    exchange_item,
    exchange_list,
    exchange_mark_all_gone,
    exchange_mark_missing,
    exchange_mark_on_loan,
    exchange_mark_returned,
    exchange_withdraw,
)
from .floorplan import floorplan, room_note
from .jobs import (
    _urgency_order,
    job_add,
    job_claim,
    job_edit,
    job_list,
    job_resolve,
    job_unclaim,
)
from .loft import (
    _LOFT_ZONE_IDS,
    _LOFT_ZONE_SECTIONS,
    _LOFT_ZONES,
    _serialize_loft_items,
    loft_item,
    loft_item_create,
    loft_item_photo_upload,
    loft_photo_delete,
)
from .lost_found import (
    found_item_claim,
    found_item_detail,
    found_item_dispose,
    found_item_label,
    found_item_list,
    found_item_log,
)
from .shopping import (
    shopping_buy,
    shopping_buy_add,
    shopping_buy_supplier,
    shopping_buy_unsorted,
    shopping_flag,
    shopping_item,
    shopping_item_add,
    shopping_item_enrich,
    shopping_list,
    shopping_out_of_stock,
    shopping_pledge,
    shopping_pledge_cancel,
    shopping_resolve,
    shopping_supplier_add,
    shopping_supplier_delete,
)

__all__ = [
    "_user_volunteer",
    "_unread_bulletins_for",
    "_active_bulletins_qs",
    "_user_can_post_bulletin",
    "_urgency_order",
    "_serialize_loft_items",
    "_LOFT_ZONES",
    "_LOFT_ZONE_IDS",
    "_LOFT_ZONE_SECTIONS",
    "BULLETIN_RATE_LIMIT_PER_HOUR",
    "collectives",
    "collectives_public",
    "collective_edit",
    "collective_join",
    "collective_leave",
    "collectives_print",
    "floorplan",
    "room_note",
    "donation_list",
    "donation_manage",
    "job_list",
    "job_add",
    "job_edit",
    "job_claim",
    "job_unclaim",
    "job_resolve",
    "loft_item_create",
    "loft_item",
    "loft_item_photo_upload",
    "loft_photo_delete",
    "area_photo_upload",
    "area_photo_delete",
    "bulletin_list",
    "bulletin_archive",
    "bulletin_add",
    "bulletin_read_all",
    "bulletin_read",
    "bulletin_pin",
    "bulletin_expire",
    "bulletin_delete",
    "shopping_list",
    "shopping_item_add",
    "shopping_item",
    "shopping_flag",
    "shopping_resolve",
    "shopping_pledge",
    "shopping_pledge_cancel",
    "shopping_supplier_add",
    "shopping_supplier_delete",
    "shopping_buy",
    "shopping_buy_unsorted",
    "shopping_buy_supplier",
    "shopping_item_enrich",
    "shopping_buy_add",
    "shopping_out_of_stock",
    "found_item_log",
    "found_item_list",
    "found_item_detail",
    "found_item_claim",
    "found_item_dispose",
    "found_item_label",
    "exchange_list",
    "exchange_add",
    "exchange_item",
    "exchange_edit",
    "exchange_withdraw",
    "exchange_mark_on_loan",
    "exchange_mark_returned",
    "exchange_mark_all_gone",
    "exchange_mark_missing",
]
