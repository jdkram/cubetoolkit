# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^floorplan/$", views.floorplan, name="labs-floorplan"),
    re_path(r"^note/(?P<room_id>[\w-]+)/$", views.room_note, name="labs-room-note"),
]
