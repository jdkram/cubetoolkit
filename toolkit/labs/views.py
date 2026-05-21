# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from .models import AreaPhoto, Collective, RoomNote, DonationItem, Job, LoftItem, LoftItemPhoto
from . import forms as lab_forms


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
    ("room-projection-booth-entrance", "Projection Booth Entrance", "secondary"),
    ("room-front-corridor", "Front Corridor", "circulation"),
    ("room-middle-corridor", "Middle Corridor", "circulation"),
    ("room-back-corridor", "Back Corridor", "circulation"),
    ("room-entry-ramp", "Entry Ramp", "circulation"),
    ("room-toilet-block-1", "Toilet Block 1", "circulation"),
    ("room-toilet-block-2-urinals", "Toilet Block 2 (Urinals)", "circulation"),
    ("room-toiler-block-3", "Toilet Block 3", "circulation"),  # typo preserved from SVG id
    ("room-changing-places-toilet", "Changing Places Toilet", "circulation"),
    ("room-accessible-toilet", "Accessible Toilet", "circulation"),
    ("room-cleaning-cupboard", "Cleaning Cupboard", "circulation"),
    ("room-electrical-cupboard", "Electrical Cupboard", "circulation"),
]

_LOFT_ZONES = [
    # (zone_id, display_name, section_key)
    ("loft-raised-west", "Raised West", "raised"),
    ("loft-raised-mid", "Raised Mid", "raised"),
    ("loft-raised-east", "Raised East", "raised"),
    ("loft-low-west", "Low West", "low"),
    ("loft-low-mid", "Low Mid", "low"),
    ("loft-low-east", "Low East", "low"),
]

_LOFT_ZONE_IDS = {z[0] for z in _LOFT_ZONES}

_LOFT_ZONE_SECTIONS = [
    {"key": "raised", "label": "Raised section (ladder access)"},
    {"key": "low", "label": "Low section (direct access)"},
]


def _serialize_loft_items():
    items_qs = (
        LoftItem.objects.filter(zone_id__in=_LOFT_ZONE_IDS)
        .prefetch_related("photos")
        .select_related("added_by")
    )
    result = {z: [] for z in _LOFT_ZONE_IDS}
    for item in items_qs:
        result[item.zone_id].append({
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "added_by": (
                item.added_by.get_full_name() or item.added_by.username
                if item.added_by else None
            ),
            "added_at": item.added_at.isoformat(),
            "photos": [
                {"id": p.id, "url": p.image.url, "caption": p.caption}
                for p in item.photos.all()
            ],
        })
    return result


_ROOM_SECTIONS = [
    {"key": "primary", "label": "Primary Spaces"},
    {"key": "secondary", "label": "Secondary Spaces"},
    {"key": "circulation", "label": "Corridors & Toilets"},
]


@login_required
def collectives(request):
    items = Collective.objects.filter(active=True).select_related("updated_by").prefetch_related("links")
    try:
        user_collective_slugs = frozenset(
            request.user.volunteer.collectives.values_list("slug", flat=True)
        )
        user_is_volunteer = True
    except Exception:
        user_collective_slugs = frozenset()
        user_is_volunteer = False
    return render(request, "labs/collectives.html", {
        "collectives": items,
        "user_collective_slugs": user_collective_slugs,
        "user_is_volunteer": user_is_volunteer,
    })


@login_required
@require_POST
def collective_join(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    if collective.invite_only:
        messages.error(request, f"{collective.name} is invite-only — membership is managed by admins.")
        return redirect("labs-collectives")
    try:
        request.user.volunteer.collectives.add(collective)
        messages.success(request, f"You've joined {collective.name}.")
    except Exception:
        messages.error(request, "You need a volunteer profile to join a collective.")
    return redirect("labs-collectives")


@login_required
@require_POST
def collective_leave(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    try:
        request.user.volunteer.collectives.remove(collective)
        messages.success(request, f"You've left {collective.name}.")
    except Exception:
        messages.error(request, "You need a volunteer profile to leave a collective.")
    return redirect("labs-collectives")


@login_required
def collectives_print(request):
    items = Collective.objects.filter(active=True)
    return render(request, "labs/collectives_print.html", {"collectives": items})


@login_required
@require_http_methods(["GET", "POST"])
def collective_edit(request, slug):
    collective = get_object_or_404(Collective, slug=slug, active=True)
    if request.method == "POST":
        form = lab_forms.CollectiveForm(request.POST, instance=collective)
        links_formset = lab_forms.CollectiveLinkFormSet(request.POST, instance=collective)
        if form.is_valid() and links_formset.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            links_formset.save()
            messages.success(request, f"'{collective.name}' updated.")
            return redirect("labs-collectives")
    else:
        form = lab_forms.CollectiveForm(instance=collective)
        links_formset = lab_forms.CollectiveLinkFormSet(instance=collective)
    return render(request, "labs/collective_edit.html", {
        "collective": collective,
        "form": form,
        "links_formset": links_formset,
    })


@login_required
def floorplan(request):
    notes = {
        n.room_id: {
            "body": n.body,
            "updated_at": n.updated_at.isoformat(),
            "updated_by": n.updated_by.get_full_name() or n.updated_by.username if n.updated_by else None,
        }
        for n in RoomNote.objects.select_related("updated_by").exclude(body="")
    }

    rooms_by_category: dict[str, list] = {s["key"]: [] for s in _ROOM_SECTIONS}
    for room_id, display_name, category in _FLOORPLAN_ROOMS:
        rooms_by_category[category].append({"id": room_id, "name": display_name})

    room_sections = [
        {**s, "rooms": rooms_by_category[s["key"]]}
        for s in _ROOM_SECTIONS
    ]

    loft_zones_by_section = {s["key"]: [] for s in _LOFT_ZONE_SECTIONS}
    for zone_id, display_name, section_key in _LOFT_ZONES:
        loft_zones_by_section[section_key].append({"id": zone_id, "name": display_name})
    loft_zone_sections = [
        {**s, "zones": loft_zones_by_section[s["key"]]}
        for s in _LOFT_ZONE_SECTIONS
    ]

    area_photos = {
        p.area_id: {"url": p.image.url, "uploaded_at": p.uploaded_at.isoformat()}
        for p in AreaPhoto.objects.all()
    }

    return render(request, "labs/floorplan.html", {
        "notes_json": json.dumps(notes),
        "area_photos_json": json.dumps(area_photos),
        "room_sections": room_sections,
        "loft_items_json": json.dumps(_serialize_loft_items()),
        "loft_zone_sections": loft_zone_sections,
    })


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
        return JsonResponse({
            "body": note.body,
            "updated_at": note.updated_at.isoformat(),
            "updated_by": note.updated_by.get_full_name() or note.updated_by.username,
        })
    else:
        try:
            note = RoomNote.objects.get(room_id=room_id)
            return JsonResponse({
                "body": note.body,
                "updated_at": note.updated_at.isoformat(),
                "updated_by": note.updated_by.get_full_name() or note.updated_by.username if note.updated_by else None,
            })
        except RoomNote.DoesNotExist:
            return JsonResponse({"body": "", "updated_at": None, "updated_by": None})


def donation_list(request):
    items = DonationItem.objects.filter(active=True)
    categories = {}
    for item in items:
        cat = item.category or "General"
        categories.setdefault(cat, []).append(item)
    return render(request, "labs/donations.html", {
        "categories": categories,
        "STATUS_WANTED": DonationItem.STATUS_WANTED,
        "STATUS_CHECK_FIRST": DonationItem.STATUS_CHECK_FIRST,
        "STATUS_NOT_NEEDED": DonationItem.STATUS_NOT_NEEDED,
    })


@login_required
def donation_manage(request):
    items = DonationItem.objects.select_related("last_edited_by").order_by("category", "display_order", "name")
    if request.method == "POST":
        action = request.POST.get("_action")

        if action == "add":
            form = lab_forms.DonationItemForm(request.POST)
            if form.is_valid():
                item = form.save(commit=False)
                item.last_edited_by = request.user
                item.save()
                messages.success(request, f"'{item.name}' added.")
                return redirect("labs-donations-manage")
            else:
                return render(request, "labs/donations_manage.html", {
                    "items": items,
                    "add_form": form,
                    "STATUS_CHOICES": DonationItem.STATUS_CHOICES,
                })

        elif action == "edit":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(DonationItem, pk=item_id)
            form = lab_forms.DonationItemForm(request.POST, instance=item)
            if form.is_valid():
                obj = form.save(commit=False)
                obj.last_edited_by = request.user
                obj.save()
                messages.success(request, f"'{obj.name}' updated.")
            return redirect("labs-donations-manage")

        elif action == "delete":
            item_id = request.POST.get("item_id")
            item = get_object_or_404(DonationItem, pk=item_id)
            name = item.name
            item.delete()
            messages.success(request, f"'{name}' removed.")
            return redirect("labs-donations-manage")

    add_form = lab_forms.DonationItemForm()
    return render(request, "labs/donations_manage.html", {
        "items": items,
        "add_form": add_form,
        "STATUS_CHOICES": DonationItem.STATUS_CHOICES,
        "STATUS_WANTED": DonationItem.STATUS_WANTED,
        "STATUS_CHECK_FIRST": DonationItem.STATUS_CHECK_FIRST,
        "STATUS_NOT_NEEDED": DonationItem.STATUS_NOT_NEEDED,
    })


def _urgency_order():
    return Case(
        When(urgency=Job.URGENCY_HIGH, then=Value(0)),
        When(urgency=Job.URGENCY_MEDIUM, then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )


@login_required
def job_list(request):
    open_jobs = (
        Job.objects.filter(resolved=False)
        .annotate(urgency_order=_urgency_order())
        .select_related("posted_by", "claimed_by")
        .order_by("urgency_order", "-posted_at")
    )
    done_jobs = (
        Job.objects.filter(resolved=True)
        .select_related("posted_by", "claimed_by")
        .order_by("-resolved_at")[:20]
    )
    return render(request, "labs/jobs.html", {
        "open_jobs": open_jobs,
        "done_jobs": done_jobs,
        "URGENCY_HIGH": Job.URGENCY_HIGH,
        "URGENCY_MEDIUM": Job.URGENCY_MEDIUM,
        "LOCATION_BUILDING": Job.LOCATION_BUILDING,
        "LOCATION_REMOTE": Job.LOCATION_REMOTE,
    })


@login_required
@permission_required("toolkit.write", raise_exception=True)
def job_add(request):
    if request.method == "POST":
        form = lab_forms.JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.posted_by = request.user
            job.save()
            messages.success(request, f"Job '{job.title}' added.")
            return redirect("labs-jobs")
    else:
        form = lab_forms.JobForm()
    return render(request, "labs/job_form.html", {"form": form, "action": "Add"})


@login_required
@permission_required("toolkit.write", raise_exception=True)
def job_edit(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if request.method == "POST":
        form = lab_forms.JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, f"Job '{job.title}' updated.")
            return redirect("labs-jobs")
    else:
        form = lab_forms.JobForm(instance=job)
    return render(request, "labs/job_form.html", {"form": form, "job": job, "action": "Edit"})


@login_required
@require_POST
def job_claim(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if job.claimed_by is None:
        job.claimed_by = request.user
        job.save()
        messages.success(request, f"You've claimed '{job.title}'.")
    return redirect("labs-jobs")


@login_required
@require_POST
def job_unclaim(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    if job.claimed_by == request.user or request.user.has_perm("toolkit.write"):
        job.claimed_by = None
        job.save()
        messages.success(request, f"'{job.title}' unclaimed.")
    return redirect("labs-jobs")


@login_required
@require_POST
def job_resolve(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    job.resolved = True
    job.resolved_at = datetime.datetime.now()
    job.save()
    messages.success(request, f"'{job.title}' marked as resolved.")
    return redirect("labs-jobs")


# ── Loft inventory ────────────────────────────────────────────────────────────

@login_required
@require_POST
def loft_item_create(request, zone_id):
    if zone_id not in _LOFT_ZONE_IDS:
        return JsonResponse({"error": "Unknown zone"}, status=404)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Name is required"}, status=400)
    item = LoftItem.objects.create(
        zone_id=zone_id,
        name=name,
        description=data.get("description", "").strip(),
        added_by=request.user,
    )
    return JsonResponse({
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "added_by": item.added_by.get_full_name() or item.added_by.username,
        "added_at": item.added_at.isoformat(),
        "photos": [],
    }, status=201)


@login_required
@require_http_methods(["POST", "DELETE"])
def loft_item(request, item_id):
    item = get_object_or_404(LoftItem, pk=item_id)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"deleted": True})
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    item.name = data.get("name", item.name).strip() or item.name
    item.description = data.get("description", item.description).strip()
    item.save()
    return JsonResponse({"id": item.id, "name": item.name, "description": item.description})


@login_required
@require_POST
def loft_item_photo_upload(request, item_id):
    item = get_object_or_404(LoftItem, pk=item_id)
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file"}, status=400)
    photo = LoftItemPhoto.objects.create(
        item=item,
        image=request.FILES["image"],
        caption=request.POST.get("caption", "").strip(),
        uploaded_by=request.user,
    )
    return JsonResponse({"id": photo.id, "url": photo.image.url, "caption": photo.caption}, status=201)


@login_required
@require_POST
def loft_photo_delete(request, photo_id):
    photo = get_object_or_404(LoftItemPhoto, pk=photo_id)
    photo.image.delete(save=False)
    photo.delete()
    return JsonResponse({"deleted": True})


# ── Area photos (one per room / loft zone) ────────────────────────────────────

@login_required
@require_POST
def area_photo_upload(request, area_id):
    if "image" not in request.FILES:
        return JsonResponse({"error": "No image file"}, status=400)
    try:
        existing = AreaPhoto.objects.get(area_id=area_id)
        existing.image.delete(save=False)
        existing.delete()
    except AreaPhoto.DoesNotExist:
        pass
    photo = AreaPhoto.objects.create(
        area_id=area_id,
        image=request.FILES["image"],
        caption=request.POST.get("caption", "").strip(),
        uploaded_by=request.user,
    )
    return JsonResponse({"url": photo.image.url, "uploaded_at": photo.uploaded_at.isoformat()}, status=201)


@login_required
@require_POST
def area_photo_delete(request, area_id):
    photo = get_object_or_404(AreaPhoto, area_id=area_id)
    photo.image.delete(save=False)
    photo.delete()
    return JsonResponse({"deleted": True})
