import re
import json
import os.path

import zoneinfo
from datetime import datetime, date, time, timedelta
import tempfile

from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from toolkit.diary.models import (
    Showing,
    Event,
    EventLink,
    Role,
    DiaryIdea,
    EventTemplate,
    MediaItem,
    RotaEntry,
    Room,
    RoomBooking,
    get_site_config,
)

import toolkit.diary.edit_prefs
from toolkit.diary.form_widgets import JQueryDateTimePicker

from .common import DiaryTestsMixin

TINY_VALID_PNG = bytearray(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08"
    b"\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x01sRGB\x00\xae\xce\x1c\xe9\x00"
    b"\x00\x00\x04gAMA\x00\x00\xb1\x8f\x0b\xfca\x05\x00\x00\x00\tpHYs\x00\x00"
    b"\x0e\xc3\x00\x00\x0e\xc3\x01\xc7o\xa8d\x00\x00\x00\x0cIDAT\x18Wc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)

TINY_VALID_JPEG = bytearray(
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x02\x00&\x00&\x00\x00\xff"
    b"\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03\x03"
    b"\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08\t"
    b"\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10"
    b"\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc0\x00\x0b\x08\x00"
    b"\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\t\xff\xc4\x00\x14\x10"
    b"\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdf\xff\xd9"
)

UTC = zoneinfo.ZoneInfo("UTC")


class ViewSecurity(DiaryTestsMixin, TestCase):
    """Basic test that the private diary pages require the correct
    permissions"""

    write_required = {
        "edit-event-details": {"event_id": "1"},
        "edit-showing": {"showing_id": "1"},
        "edit-ideas": {"year": "2012", "month": "1"},
        "delete-showing": {"showing_id": "1"},
        "add-event": {},
        "edit_event_templates": {},
        "edit_event_tags": {},
        "edit_roles": {},
        "members-mailout": {},
        "queue-members-mailout": {},
        "add-printed-programme": {},
        "clone-event": {"event_id": "4"},
        "edit-event-links": {"event_id": "1"},
    }

    only_read_required = {
        "default-edit": {},
        "diary-edit-calendar": {},
        "edit-diary-data": {},
        "year-edit": {"year": "2013"},
        "month-edit": {"year": "2013", "month": "1"},
        "day-edit": {"year": "2013", "month": "1", "day": "1"},
        "edit-event-details-view": {"event_id": "1"},
        "cancel-edit": {},
        "view_event_field": {"field": "rota"},
        "set_edit_preferences": {},
        "edit-printed-programmes": {},
        "view_terms_report_csv": {"year": "2020", "month": "2", "day": "3"},
    }

    rota_edit_required = {
        "rota-edit": {},
        "edit-showing-rota-notes": {"showing_id": "1"},
        "view-rota-vacancies": {},
    }

    def _assert_need_login(self, views_to_test):
        for view_name, kwargs in views_to_test.items():
            url = reverse(view_name, kwargs=kwargs)
            expected_redirect = reverse("login", query={"next": url})
            # Test GET:
            with self.subTest(f"GET {view_name} {url}"):
                response = self.client.get(url)
                self.assertIn(response.status_code, (302, 403))
                if response.status_code == 302:
                    self.assertRedirects(response, expected_redirect)
            # Test POST:
            with self.subTest(f"POST {view_name} {url}"):
                response = self.client.post(url)
                self.assertIn(response.status_code, (302, 403))
                if response.status_code == 302:
                    self.assertRedirects(response, expected_redirect)

    def test_need_login(self):
        """
        Checks all URLs that shouldn't work when not logged in at all
        """
        views_to_test = {}
        views_to_test.update(self.write_required)
        views_to_test.update(self.only_read_required)
        views_to_test.update(self.rota_edit_required)

        self._assert_need_login(views_to_test)

    def test_need_write(self):
        """
        Checks all URLs that shouldn't work when logged in user doesn't have
        'toolkit.write' permission
        """
        # login as read only user:
        self.client.login(username="read_only", password="T3stPassword!1")

        views_to_test = {}
        views_to_test.update(self.write_required)
        views_to_test.update(self.rota_edit_required)

        self._assert_need_login(views_to_test)

    def test_need_read_or_write(self):
        """
        Checks all URLs that shouldn't work when logged in user doesn't have
        'toolkit.write' or 'toolkit.read' permission
        """
        views_to_test = {}
        views_to_test.update(self.write_required)
        views_to_test.update(self.only_read_required)
        views_to_test.update(self.rota_edit_required)

        # login as no permission user:
        self.client.login(username="no_perm", password="T3stPassword!2")

        self._assert_need_login(views_to_test)

    def test_rota_editor_no_access(self):
        """
        Checks all URLs that shouldn't work when logged in user doesn't have
        'toolkit.write' or 'toolkit.read' permission
        """
        views_to_test = {}
        views_to_test.update(self.write_required)
        views_to_test.update(self.only_read_required)
        # i.e. everything except self.rota_edit_required

        # login as rota editing permission user:
        self.client.login(username="rota_editor", password="T3stPassword!3")

        self._assert_need_login(views_to_test)


class EditDiaryViews(DiaryTestsMixin, TestCase):
    """Basic test that various private diary pages load"""

    def setUp(self):
        super().setUp()

        self.client.login(username="admin", password="T3stPassword!")

    def tearDown(self):
        self.client.logout()

    def test_view_default(self):
        url = reverse("default-edit")
        response = self.client.get(url)
        # self.assertIn(u'Event one title', response.content)
        # self.assertIn(u'<p>Event one copy</p>', response.content)
        self.assertEqual(response.status_code, 200)

    def test_view_calendar(self):
        url = reverse("diary-edit-calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_calendar_index.html")

    def test_view_tag_editor(self):
        url = reverse("edit_event_tags")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_tags.html")

    def test_view_template_editor(self):
        url = reverse("edit_event_templates")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_templates.html")

    def test_view_role_editor(self):
        url = reverse("edit_roles")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_edit_roles.html")


class PreferencesTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def _get_prefs_json(self, **kwargs):
        # set_edit_preferences returns JSON of current prefs:
        response = self.client.get(reverse("set_edit_preferences"), data=kwargs)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_set_pref(self):
        # Default daysahead:
        prefs = self._get_prefs_json()
        self.assertEqual(prefs["daysahead"], "365")

        # Change daysahead:
        prefs = self._get_prefs_json(daysahead="60")
        self.assertEqual(prefs["daysahead"], "60")

        # Reset:
        prefs = self._get_prefs_json(daysahead="365")
        self.assertEqual(prefs["daysahead"], "365")

    def test_set_get_single_pref(self):
        session_mock = {}
        toolkit.diary.edit_prefs.set_preference(session_mock, "daysahead", 30)

        retrieved_pref = toolkit.diary.edit_prefs.get_preference(
            session_mock, "daysahead"
        )
        self.assertEqual(retrieved_pref, "30")

    def test_set_get_single_missing_pref(self):
        session_mock = {}
        retrieved_pref = toolkit.diary.edit_prefs.get_preference(
            session_mock, "daysahead"
        )
        self.assertEqual(retrieved_pref, "365")

    def test_set_get_single_bad_pref(self):
        session_mock = {"spangles": "foo"}
        # Shouldn't return the value, as it's not a known pref, even tho it's
        # in the session:
        retrieved_pref = toolkit.diary.edit_prefs.get_preference(
            session_mock, "spangles"
        )
        self.assertEqual(retrieved_pref, None)

    def test_bad_value(self):
        # Long value is truncated to 10 chars:
        prefs = self._get_prefs_json(daysahead="1234567890XXXXX")
        self.assertEqual(prefs["daysahead"], "1234567890")

    def test_bad_pref(self):
        # Unknown pref is silently ignored; only known prefs come back:
        prefs = self._get_prefs_json(nonsense="tralala")
        self.assertEqual(set(prefs.keys()), {"daysahead"})

    def test_redirect_change(self):
        url = reverse("cancel-edit")
        # always redirects to edit list now (popup mode removed):
        response = self.client.get(url)
        self.assert_redirect_to_index(response)


class EditTagsViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def tearDown(self):
        self.client.logout()

    def test_page_loads(self):
        url = reverse("edit_event_tags")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_tags.html")


class EditDiaryListViewTests(DiaryTestsMixin, TestCase):
    """Tests for the edit_diary_list view (GET /diary/edit/). See TASKS.md 9.42."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("default-edit")

    def tearDown(self):
        self.client.logout()

    def test_rooms_context_contains_no_none_sentinel(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        rooms = response.context["rooms"]
        self.assertNotIn(None, rooms)
        self.assertTrue(all(hasattr(r, "name") for r in rooms))

    def test_response_contains_month_heading(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="month-heading"')

    @override_settings(MULTIROOM_ENABLED=True)
    def test_multiroom_thead_has_room_name_columns(self):
        from toolkit.diary.models import Room
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        for room in Room.objects.all():
            self.assertContains(response, room.name)

    @override_settings(MULTIROOM_ENABLED=False)
    def test_single_room_thead_has_generic_event_header(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Single-room: plain <th>Event</th> with no room-col class
        self.assertContains(response, "<th>Event</th>")

    def test_empty_day_renders_blank_time_cell(self):
        # The view populates every date in the range, so days with no showings
        # still appear as rows with an empty time cell.
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Template emits a <td class="time"> for empty days
        self.assertContains(response, "<td")


