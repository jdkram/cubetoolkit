# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.db import models
from django.contrib.auth.models import User


class RoomNote(models.Model):
    room_id = models.CharField(max_length=100, unique=True)
    body = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        db_table = "labs_room_notes"

    def __str__(self):
        return f"{self.room_id}: {self.body[:60]}"
