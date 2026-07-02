# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^schedule/$", views.schedule, name="operations-schedule"),
    re_path(r"^schedule/add/$", views.task_add, name="operations-task-add"),
    re_path(r"^schedule/(?P<task_id>\d+)/edit/$", views.task_edit, name="operations-task-edit"),
    re_path(r"^schedule/(?P<task_id>\d+)/mark-done/$", views.task_mark_done, name="operations-task-mark-done"),
    re_path(r"^schedule/(?P<task_id>\d+)/commit/$", views.task_commit, name="operations-task-commit"),
    re_path(r"^schedule/(?P<task_id>\d+)/uncommit/$", views.task_uncommit, name="operations-task-uncommit"),
]
