# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import RoomNote


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
