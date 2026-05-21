# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r"^collectives/$", views.collectives, name="labs-collectives"),
    re_path(r"^collectives/(?P<slug>[\w-]+)/edit/$", views.collective_edit, name="labs-collective-edit"),
    re_path(r"^collectives/(?P<slug>[\w-]+)/join/$", views.collective_join, name="labs-collective-join"),
    re_path(r"^collectives/(?P<slug>[\w-]+)/leave/$", views.collective_leave, name="labs-collective-leave"),
    re_path(r"^collectives/print/$", views.collectives_print, name="labs-collectives-print"),
    re_path(r"^floorplan/$", views.floorplan, name="labs-floorplan"),
    re_path(r"^note/(?P<room_id>[\w-]+)/$", views.room_note, name="labs-room-note"),
    re_path(r"^donations/$", views.donation_list, name="labs-donations"),
    re_path(r"^donations/manage/$", views.donation_manage, name="labs-donations-manage"),
    re_path(r"^jobs/$", views.job_list, name="labs-jobs"),
    re_path(r"^jobs/add/$", views.job_add, name="labs-job-add"),
    re_path(r"^jobs/(?P<job_id>\d+)/edit/$", views.job_edit, name="labs-job-edit"),
    re_path(r"^jobs/(?P<job_id>\d+)/claim/$", views.job_claim, name="labs-job-claim"),
    re_path(r"^jobs/(?P<job_id>\d+)/unclaim/$", views.job_unclaim, name="labs-job-unclaim"),
    re_path(r"^jobs/(?P<job_id>\d+)/resolve/$", views.job_resolve, name="labs-job-resolve"),
    re_path(r"^loft/zone/(?P<zone_id>[\w-]+)/items/$", views.loft_item_create, name="labs-loft-item-create"),
    re_path(r"^loft/item/(?P<item_id>\d+)/$", views.loft_item, name="labs-loft-item"),
    re_path(r"^loft/item/(?P<item_id>\d+)/photo/$", views.loft_item_photo_upload, name="labs-loft-item-photo"),
    re_path(r"^loft/photo/(?P<photo_id>\d+)/delete/$", views.loft_photo_delete, name="labs-loft-photo-delete"),
    re_path(r"^area/(?P<area_id>[\w-]+)/photo/$", views.area_photo_upload, name="labs-area-photo-upload"),
    re_path(r"^area/(?P<area_id>[\w-]+)/photo/delete/$", views.area_photo_delete, name="labs-area-photo-delete"),
]
