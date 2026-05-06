# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^floorplan/$", views.floorplan, name="labs-floorplan"),
    re_path(r"^note/(?P<room_id>[\w-]+)/$", views.room_note, name="labs-room-note"),
    re_path(r"^donations/$", views.donation_list, name="labs-donations"),
    re_path(r"^jobs/$", views.job_list, name="labs-jobs"),
    re_path(r"^jobs/add/$", views.job_add, name="labs-job-add"),
    re_path(r"^jobs/(?P<job_id>\d+)/edit/$", views.job_edit, name="labs-job-edit"),
    re_path(r"^jobs/(?P<job_id>\d+)/claim/$", views.job_claim, name="labs-job-claim"),
    re_path(r"^jobs/(?P<job_id>\d+)/done/$", views.job_done, name="labs-job-done"),
]
