# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from .models import RoomNote, DonationItem, Job
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

    return render(request, "labs/floorplan.html", {
        "notes_json": json.dumps(notes),
        "room_sections": room_sections,
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
