import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from toolkit.toolkit_auth.decorators import (
    feature_required,
    write_required,
    write_required_strict,
)
from django.db import models
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Exists, OuterRef

from ..models import (
    AreaPhoto,
    Bulletin,
    BulletinRead,
    Collective,
    ConsumableItem,
    ExchangeItem,
    FoundItem,
    NeedFlag,
    ProcurementPledge,
    Supplier,
    SupplierRecord,
    RoomNote,
    DonationItem,
    Job,
    LoftItem,
    LoftItemPhoto,
)
from toolkit.diary.models import SiteConfiguration, get_site_config
from .. import forms as lab_forms
from .loft import (
    _LOFT_ZONE_SECTIONS,
    _LOFT_ZONES,
    _serialize_loft_items,
)

_FLOORPLAN_ROOMS = [
    # (room_id, display_name, category)
    # category: "primary" | "secondary" | "circulation"
    ("room-cinema", "Cinema", "primary"),
    ("room-venue", "Venue", "primary"),
    ("room-bar", "Bar", "primary"),
    ("room-cafe", "Café", "primary"),
    ("room-workshop", "Workshop", "primary"),
    ("room-screen-printing-room", "Screen Printing Room", "primary"),
    ("room-dark-room", "Dark Room", "primary"),
    ("room-meeting-room", "Meeting Room", "primary"),
    ("room-green-room", "Green Room", "primary"),
    ("room-projection-booth", "Projection Booth", "secondary"),
    ("room-cinema-stores", "Cinema Stores", "secondary"),
    ("room-kitchen", "Kitchen", "secondary"),
    ("room-volunteer-kitchen", "Volunteer Kitchen", "secondary"),
    ("room-venue-store-tech", "Venue Tech Store", "secondary"),
    ("room-snug", "Snug", "secondary"),
    ("room-balcony", "Balcony", "secondary"),
    ("room-cinema-entrance", "Cinema Entrance", "secondary"),
    ("room-venue-front-entrance", "Venue Front Entrance", "secondary"),
    ("room-venue-back-entrance", "Venue Back Entrance", "secondary"),
    ("room-it-cupboard", "IT Cupboard", "secondary"),
    ("room-store-cupboard", "Store Cupboard", "secondary"),
    (
        "room-projection-booth-entrance",
        "Projection Booth Entrance",
        "secondary",
    ),
    ("room-front-corridor", "Front Corridor", "circulation"),
    ("room-middle-corridor", "Middle Corridor", "circulation"),
    ("room-back-corridor", "Back Corridor", "circulation"),
    ("room-entry-ramp", "Entry Ramp", "circulation"),
    ("room-toilet-block-1", "Toilet Block 1", "circulation"),
    ("room-toilet-block-2-urinals", "Toilet Block 2 (Urinals)", "circulation"),
    (
        "room-toiler-block-3",
        "Toilet Block 3",
        "circulation",
    ),  # typo preserved from SVG id
    ("room-changing-places-toilet", "Changing Places Toilet", "circulation"),
    ("room-accessible-toilet", "Accessible Toilet", "circulation"),
    ("room-cleaning-cupboard", "Cleaning Cupboard", "circulation"),
    ("room-electrical-cupboard", "Electrical Cupboard", "circulation"),
]

_ROOM_SECTIONS = [
    {"key": "primary", "label": "Primary Spaces"},
    {"key": "secondary", "label": "Secondary Spaces"},
    {"key": "circulation", "label": "Corridors & Toilets"},
]


@login_required
def floorplan(request):
    notes = {
        n.room_id: {
            "body": n.body,
            "updated_at": n.updated_at.isoformat(),
            "updated_by": (
                n.updated_by.get_full_name() or n.updated_by.username
                if n.updated_by
                else None
            ),
        }
        for n in RoomNote.objects.select_related("updated_by").exclude(body="")
    }

    rooms_by_category: dict[str, list] = {s["key"]: [] for s in _ROOM_SECTIONS}
    for room_id, display_name, category in _FLOORPLAN_ROOMS:
        rooms_by_category[category].append(
            {"id": room_id, "name": display_name}
        )

    room_sections = [
        {**s, "rooms": rooms_by_category[s["key"]]} for s in _ROOM_SECTIONS
    ]

    loft_zones_by_section = {s["key"]: [] for s in _LOFT_ZONE_SECTIONS}
    for zone_id, display_name, section_key in _LOFT_ZONES:
        loft_zones_by_section[section_key].append(
            {"id": zone_id, "name": display_name}
        )
    loft_zone_sections = [
        {**s, "zones": loft_zones_by_section[s["key"]]}
        for s in _LOFT_ZONE_SECTIONS
    ]

    area_photos = {
        p.area_id: {
            "url": p.image.url,
            "uploaded_at": p.uploaded_at.isoformat(),
        }
        for p in AreaPhoto.objects.all()
    }

    return render(
        request,
        "labs/floorplan.html",
        {
            "notes_json": json.dumps(notes),
            "area_photos_json": json.dumps(area_photos),
            "room_sections": room_sections,
            "loft_items_json": json.dumps(_serialize_loft_items()),
            "loft_zone_sections": loft_zone_sections,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def room_note(request, room_id):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        body = data.get("body", "").strip()
        note, _ = RoomNote.objects.update_or_create(
            room_id=room_id,
            defaults={"body": body, "updated_by": request.user},
        )
        return JsonResponse(
            {
                "body": note.body,
                "updated_at": note.updated_at.isoformat(),
                "updated_by": note.updated_by.get_full_name()
                or note.updated_by.username,
            }
        )
    else:
        try:
            note = RoomNote.objects.get(room_id=room_id)
            return JsonResponse(
                {
                    "body": note.body,
                    "updated_at": note.updated_at.isoformat(),
                    "updated_by": (
                        note.updated_by.get_full_name()
                        or note.updated_by.username
                        if note.updated_by
                        else None
                    ),
                }
            )
        except RoomNote.DoesNotExist:
            return JsonResponse(
                {"body": "", "updated_at": None, "updated_by": None}
            )
