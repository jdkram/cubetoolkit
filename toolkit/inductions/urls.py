# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.urls import path

from . import views

app_name = "inductions"

urlpatterns = [
    # Panopticon management — must come before <slug:slug> wildcard patterns
    path("manage/", views.manage_session_list, name="manage_session_list"),
    path("manage/settings/", views.manage_settings, name="manage_settings"),
    path("manage/settings/test-email/", views.manage_send_test_email, name="manage_send_test_email"),
    path("manage/new/", views.manage_session_new, name="manage_session_new"),
    path("manage/access-needs/", views.manage_access_needs_list, name="manage_access_needs_list"),
    path("manage/access-needs/<int:request_id>/", views.manage_access_needs_detail, name="manage_access_needs_detail"),
    path("manage/<slug:slug>/", views.manage_session_detail, name="manage_session_detail"),
    path("manage/<slug:slug>/edit/", views.manage_session_edit, name="manage_session_edit"),
    path("manage/<slug:slug>/close/", views.manage_session_close, name="manage_session_close"),
    path("manage/<slug:slug>/purge/", views.manage_session_purge, name="manage_session_purge"),
    path("manage/<slug:slug>/export.csv", views.manage_export_csv, name="manage_export_csv"),
    path("manage/<slug:slug>/check-in/<int:signup_id>/", views.manage_check_in, name="manage_check_in"),
    path("manage/<slug:slug>/mark-attendance/<int:signup_id>/", views.manage_mark_attendance, name="manage_mark_attendance"),
    path("manage/<slug:slug>/create-accounts/", views.manage_create_accounts, name="manage_create_accounts"),
    path("manage/<slug:slug>/edit-signup/<int:signup_id>/", views.manage_edit_signup, name="manage_edit_signup"),
    path("manage/<slug:slug>/no-show/<int:signup_id>/", views.manage_no_show, name="manage_no_show"),
    path("manage/<slug:slug>/add-walkin/", views.manage_add_walkin, name="manage_add_walkin"),
    path("manage/<slug:slug>/signups/<int:signup_id>/link-existing/", views.manage_link_existing, name="manage_link_existing"),
    path("manage/<slug:slug>/signups/<int:signup_id>/remove/", views.manage_remove_signup, name="manage_remove_signup"),

    # Public listing of open sessions
    path("", views.session_list_public, name="session_list_public"),

    # Public — wildcard slug patterns must come last
    path("access-needs/", views.access_needs_signup, name="access_needs_signup"),
    path("access-needs/thanks/", views.access_needs_thanks, name="access_needs_thanks"),
    path("<slug:slug>/", views.signup, name="signup"),
    path("<slug:slug>/thanks/", views.signup_thanks, name="signup_thanks"),
    path("<slug:slug>/calendar.ics", views.calendar_ics, name="calendar_ics"),
]
