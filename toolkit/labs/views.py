# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import permission_required

from .models import RoomNote, DonationItem, Job
from . import forms as lab_forms


@login_required
def floorplan(request):
    notes = {n.room_id: {"body": n.body, "updated_at": n.updated_at.isoformat(), "updated_by": n.updated_by.get_full_name() or n.updated_by.username if n.updated_by else None} for n in RoomNote.objects.select_related("updated_by").exclude(body="")}
    return render(request, "labs/floorplan.html", {"notes_json": json.dumps(notes)})


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
def job_list(request):
    open_jobs = Job.objects.filter(done=False).select_related("posted_by", "claimed_by")
    done_jobs = Job.objects.filter(done=True).select_related("posted_by", "claimed_by")[:20]
    return render(request, "labs/jobs.html", {
        "open_jobs": open_jobs,
        "done_jobs": done_jobs,
        "URGENCY_HIGH": Job.URGENCY_HIGH,
        "URGENCY_MEDIUM": Job.URGENCY_MEDIUM,
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
def job_done(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    job.done = True
    job.done_at = datetime.datetime.now()
    job.save()
    messages.success(request, f"'{job.title}' marked as done.")
    return redirect("labs-jobs")
