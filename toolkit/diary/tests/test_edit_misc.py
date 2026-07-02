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
    EventTag,
    EventTemplate,
    EventTemplateRole,
    Role,
    DiaryIdea,
    MediaItem,
    RotaEntry,
    Room,
    RoomBooking,
    get_site_config,
)

import toolkit.diary.edit_prefs
from toolkit.diary.form_widgets import JQueryDateTimePicker

from .common import DiaryTestsMixin, UKTZ

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


class EditIdeasViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_form_no_existing_ideas(self):
        # Confirm no ideas in the database for Jan 2012:
        self.assertQuerySetEqual(
            DiaryIdea.objects.all().filter(month=date(2012, 1, 1)), []
        )

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_idea.html")

        # There should now be a Jan 2012 entry in the DB:
        idea = DiaryIdea.objects.get(month=date(2012, 1, 1))
        # With no content:
        self.assertIsNone(idea.ideas)

    def test_get_json_no_existing_ideas(self):
        # Confirm no ideas in the database for Jan 2012:
        self.assertQuerySetEqual(
            DiaryIdea.objects.all().filter(month=date(2012, 1, 1)), []
        )

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(
            url,
            HTTP_ACCEPT="Accept: application/xml;q=0.9, */*;q=0.8, application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ideas": None,
                "month": "2012-01-01",
            },
        )
        self.assertTemplateNotUsed(response, "form_idea.html")

        # There should now be a Jan 2012 entry in the DB:
        idea = DiaryIdea.objects.get(month=date(2012, 1, 1))
        # With no content:
        self.assertIsNone(idea.ideas)

    def test_get_form_existing_ideas(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = "An ide\u0113 f\u014d\u0159 some \u20acvent"
        idea.save()

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_idea.html")

        self.assertContains(response, "An ide\u0113 f\u014d\u0159 some \u20acvent")

    def test_get_json_existing_idea(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = "An ide\u0113 f\u014d\u0159 some \u20acvent"
        idea.save()

        # Get the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.get(
            url,
            HTTP_ACCEPT="Accept: application/xml;q=0.9, */*;q=0.8, application/json",
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(
            response_data,
            {
                "ideas": "An ide\u0113 f\u014d\u0159 some \u20acvent",
                "month": "2012-01-01",
            },
        )
        self.assertTemplateNotUsed(response, "form_idea.html")

    def test_post_form_no_existing_idea(self):
        # Confirm no ideas in the database for Jan 2012:
        self.assertQuerySetEqual(
            DiaryIdea.objects.all().filter(month=date(2012, 1, 1)), []
        )

        # Post an idea to the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.post(
            url,
            data={
                "ideas": "An ide\u0113 f\u014d\u0159 some \u20acvent",
            },
        )

        # Check that's made it into the database:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertFalse(created)
        self.assertEqual(idea.ideas, "An ide\u0113 f\u014d\u0159 some \u20acvent")

        self.assert_redirect_to_index(response)

    def test_post_form_existing_idea(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = "Any old junk, which shall be overwritten"
        idea.save()

        # Post an idea to the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.post(
            url,
            data={
                "ideas": "An ide\u0113 f\u014d\u0159 some \u20acvent",
            },
        )

        # Check that's made it into the database:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertFalse(created)
        self.assertEqual(idea.ideas, "An ide\u0113 f\u014d\u0159 some \u20acvent")

        self.assert_redirect_to_index(response)

    def test_post_inline_existing_idea(self):
        # Ensure there's something in the DB for Jan 2012:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertTrue(created)  # Not strictly necessary
        idea.ideas = "Any old junk, which shall be overwritten"
        idea.save()

        new_idea = "An ide\u0113 f\u014d\u0159 some \u20acvent"

        # Post an idea to the corresponding edit form:
        url = reverse("edit-ideas", kwargs={"year": 2012, "month": 1})
        response = self.client.post(
            url,
            data={
                "ideas": new_idea,
                "source": "inline",
            },
        )

        # Check that's made it into the database:
        idea, created = DiaryIdea.objects.get_or_create(month=date(2012, 1, 1))
        self.assertFalse(created)
        self.assertEqual(idea.ideas, new_idea)

        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content, new_idea.encode("utf8"))


class ViewEventFieldTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

        # Fake "now()" function to return a fixed time:
        self.time_patch = patch("django.utils.timezone.now")
        self.time_mock = self.time_patch.start()
        self.time_mock.return_value = self._fake_now

    def tearDown(self):
        self.time_patch.stop()

    def test_view_event_field_rota(self):
        url = reverse("view_event_field", kwargs={"field": "rota"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertNotContains(response, "Event three title")
        self.assertContains(response, "Event four titl\u0113")
        self.assertContains(response, "Role 2 (nonstandard)")

    def test_view_event_field_copy(self):
        url = reverse("view_event_field", kwargs={"field": "copy"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_copy.html")

        self.assertNotContains(response, "EVENT THREE TITLE")
        self.assertContains(response, "Sun 09 18:00 .... Event four titl\u0113")
        self.assertContains(response, "<p>EVENT FOUR TITL\u0112</p>", html=True)
        self.assertContains(response, "<p>Event four C\u014dpy</p>", html=True)

    def test_view_event_field_copy_summary(self):
        url = reverse("view_event_field", kwargs={"field": "copy_summary"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_copy_summary.html")

        self.assertNotContains(response, "EVENT THREE TITLE")
        self.assertContains(
            response,
            "Sun 09 18:00 .... Pretitle four Event four titl\u0113 Posttitle four",
        )
        self.assertContains(
            response, '<p class="title">Event four titl\u0113</p>', html=True
        )
        self.assertContains(
            response,
            '<p class="copy_summary">\u010copy four summary</p>',
            html=True,
        )

        self.assertContains(response, "\u00a3milliion per thing")
        self.assertContains(response, "Pretitle four")
        self.assertContains(response, "Posttitle four")
        self.assertContains(response, "Film info for four")

    def test_view_event_field_terms(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertContains(response, "Sun 09 18:00 .... Event four titl\u0113")
        self.assertContains(response, "Cube event / Public event / Confirmed")
        self.assertContains(response, "Terminal price: \u00a31 / \u20ac3")

    def test_custom_start_date_rota_long_time(self):
        # Reverse doesn't work for full date, as regex is apparently too
        # complicated:
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/01/01?daysahead=365"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertContains(response, "Event three title")
        self.assertContains(response, "Event four titl\u0113")

    def test_custom_start_date_rota_less_long_time(self):
        # Now shorter date range, should find one fewer event
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/01/01?daysahead=120"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota.html")

        self.assertContains(response, "Event three title")
        self.assertNotContains(response, "Event four titl\u0113")

    def test_custom_start_date_rota_invalid_date(self):
        # Now shorter date range, should find one fewer event
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/99/99?daysahead=120"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_custom_start_date_terms_search_success(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        url += "/2013/01/01?daysahead=365&search=Terminal"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertNotContains(response, "EVENT THREE TITLE")
        self.assertContains(response, "EVENT FOUR TITL\u0112")

    def test_custom_start_date_terms_search_no_result(self):
        url = reverse("view_event_field", kwargs={"field": "terms"})
        url += "/2013/01/01?daysahead=365&search=elephant"

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_terms.html")

        self.assertNotContains(response, "EVENT THREE TITLE")
        self.assertNotContains(response, "EVENT FOUR TITL\u0112")

    def _add_private_showing_in_range(self):
        """Add a confirmed showing for the private event e5 within the default date range."""
        showing = Showing(
            start=datetime(2013, 6, 15, 19, 0, tzinfo=UKTZ),
            event=self.e5,
            booked_by="User",
            confirmed=True,
        )
        showing.save(force=True)
        return showing

    def test_copy_excludes_private_events(self):
        self._add_private_showing_in_range()
        url = reverse("view_event_field", kwargs={"field": "copy"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE Event FIVE")

    def test_copy_summary_excludes_private_events(self):
        self._add_private_showing_in_range()
        url = reverse("view_event_field", kwargs={"field": "copy_summary"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE Event FIVE")

    def test_terms_excludes_private_events(self):
        self._add_private_showing_in_range()
        url = reverse("view_event_field", kwargs={"field": "terms"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE Event FIVE")

    def test_rota_includes_private_events(self):
        # Private events still need to appear on the internal rota.
        self._add_private_showing_in_range()
        url = reverse("view_event_field", kwargs={"field": "rota"})
        url += "/2013/06/01?daysahead=30"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRIVATE Event FIVE")


class ViewTermsReportCsvTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_bad_dates(self):
        url = reverse(
            "view_terms_report_csv",
            kwargs={"year": "2020", "month": "100", "day": "15"},
        )
        url += "?daysahead=365"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_no_showings(self):
        url = reverse(
            "view_terms_report_csv",
            kwargs={"year": "1990", "month": "1", "day": "15"},
        )
        url += "?daysahead=365"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="terms-1990-01-15.csv"',
        )
        self.assertEqual(response.content.decode("utf-8"), "date,time,title,terms\r\n")

    def test_showings(self):
        url = reverse(
            "view_terms_report_csv",
            kwargs={"year": "2013", "month": "2", "day": "14"},
        )
        url += "?daysahead=2"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="terms-2013-02-14.csv"',
        )
        # Check that missing terms work as expected;
        self.assertIsNone(self.e1.terms)
        self.assertEqual(
            response.content.decode("utf-8"),
            "date,time,title,terms\r\n"
            f"2013-02-14,18:00,{self.e5.name},{self.e5.terms}\r\n"
            f"2013-02-15,18:00,{self.e1.name},\r\n",
        )


class DiaryCalendarViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def _get_room_list(self, response):
        # Match room list in init call, accounting for IIFE wrapper and initialFilters param
        match = re.search(
            r"init_calendar_view\(\s*'[^']*'\s*,\s*'[^']*'\s*,\s*'[^']*'\s*,\s*urls\s*,\s*(?P<room_list>\[.*?\])\s*,\s*initialFilters",  # noqa: E501
            response.content.decode("utf-8"),
            re.DOTALL,
        )
        return match.group("room_list")

    @override_settings(MULTIROOM_ENABLED=False)
    def test_view_default(self):
        url = reverse("diary-edit-calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_calendar_index.html")

        self.assertJSONEqual(self._get_room_list(response), [])

    @override_settings(MULTIROOM_ENABLED=True)
    def test_view_default_multiroom_enabled(self):
        url = reverse("diary-edit-calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_calendar_index.html")

        self.assertJSONEqual(
            self._get_room_list(response),
            [
                {"id": 1, "title": "Room one", "eventColor": "#Ff0000", "eventTextColor": "#ffffff"},
                {"id": 2, "title": "Room two", "eventColor": "#00abcd", "eventTextColor": "#ffffff"},
            ],
        )

    def test_view_year_month_day(self):
        url = reverse("diary-edit-calendar") + "/2013/1/30/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_calendar_index.html")

    def test_view_year_month(self):
        url = reverse("diary-edit-calendar") + "/2013/1/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_calendar_index.html")

    def test_view_year_bad_url(self):
        url = reverse("diary-edit-calendar") + "/2013/0/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = reverse("diary-edit-calendar") + "/2013/13/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

        url = reverse("diary-edit-calendar") + "/fruitbat"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_view_year(self):
        url = reverse("diary-edit-calendar") + "/2013/"
        response = self.client.get(url)
        # Shouldn't work!
        self.assertEqual(response.status_code, 404)


class DiaryDataViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_missing_params(self):
        url = reverse("edit-diary-data")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_invalid_end(self):
        # Valid start, invalid end
        url = reverse("edit-diary-data")
        response = self.client.get(url, data={"start": "2000-01-01", "end": "0"})
        self.assertEqual(response.status_code, 404)

    # Common code for following two tests
    def _common_test_valid_query(self, now_patch, multiroom_enabled):
        now_patch.return_value = self._fake_now

        # Create a RoomBooking for showing 2 so multi-room calendar data can be tested:
        from toolkit.diary.models import RoomBooking

        showing = Showing.objects.get(id=2)
        RoomBooking.objects.get_or_create(
            showing=showing,
            room=self.room_2,
            defaults={"start": showing.start},
        )

        FUTURE_COLOUR = "#cc3333"
        # Historic events now use the same colour as future events — the
        # past/future boundary is shown via the FullCalendar nowIndicator
        # line instead of a colour change.

        url = reverse("edit-diary-data")
        with self.settings(CALENDAR_DEFAULT_COLOUR=FUTURE_COLOUR):
            response = self.client.get(
                url,
                data={
                    "start": "2013-02-15",
                    "end": "2013-09-13",
                },
            )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        # In multiroom mode, room-booked showings get IDs like "rb-{pk}" rather
        # than integer showing PKs. Normalise both formats to showing PKs.
        from toolkit.diary.models import RoomBooking as _RB
        rb_to_showing = {rb.pk: rb.showing_id for rb in _RB.objects.all()}

        def _showing_id(id_val):
            s = str(id_val)
            if s.startswith("rb-"):
                return rb_to_showing[int(s[3:])]
            return int(id_val)

        data_by_showing = {_showing_id(i["id"]): i for i in data}

        expected_showings = {1, 2, 3, 4, 5, 6, 7, 10}

        self.assertEqual(set(data_by_showing.keys()), expected_showings)

        expected_data = {
            1: {
                "id": 1,
                "className": ["s_historic", "s_unconfirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-04-01T20:30:00+01:00",
                "start": "2013-04-01T19:00:00+01:00",
                "title": "Event two title",
                "url": "/diary/edit/event/id/2/view/",
                "hour": 19,
                "tags": [],
            },
            2: {
                "id": 2,
                "className": ["s_historic", "s_confirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-04-02T20:30:00+01:00",
                "start": "2013-04-02T19:00:00+01:00",
                "title": "Event two title",
                "url": "/diary/edit/event/id/2/view/",
                "hour": 19,
                "tags": [],
            },
            3: {
                "id": 3,
                "className": ["s_cancelled", "s_historic", "s_confirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-04-03T20:30:00+01:00",
                "start": "2013-04-03T19:00:00+01:00",
                "title": "Event two title",
                "url": "/diary/edit/event/id/2/view/",
                "hour": 19,
                "tags": [],
            },
            4: {
                "id": 4,
                "className": ["s_private", "s_historic", "s_confirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-04-04T20:30:00+01:00",
                "start": "2013-04-04T19:00:00+01:00",
                "title": "Event two title",
                "url": "/diary/edit/event/id/2/view/",
                "hour": 19,
                "tags": [],
            },
            5: {
                "id": 5,
                "className": [
                    "s_cancelled",
                    "s_private",
                    "s_historic",
                    "s_confirmed",
                ],
                "color": FUTURE_COLOUR,
                "end": "2013-04-05T20:30:00+01:00",
                "start": "2013-04-05T19:00:00+01:00",
                "title": "Event two title",
                "url": "/diary/edit/event/id/2/view/",
                "hour": 19,
                "tags": [],
            },
            6: {
                "id": 6,
                "className": ["s_historic", "s_confirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-04-13T21:00:00+01:00",
                "start": "2013-04-13T18:00:00+01:00",
                "title": "Event three title",
                "url": "/diary/edit/event/id/3/view/",
                "hour": 18,
                "tags": ["tag-two"],
            },
            7: {
                "id": 7,
                "className": ["s_confirmed"],
                "color": FUTURE_COLOUR,
                "end": "2013-06-09T19:00:00+01:00",
                "start": "2013-06-09T18:00:00+01:00",
                "title": "Event four titl\u0113",
                "url": "/diary/edit/event/id/4/view/",
                "hour": 18,
                "tags": ["tag-two"],
            },
            10: {
                "id": 10,
                "className": [
                    "s_private",
                    "s_outside_hire",
                    "s_historic",
                    "s_confirmed",
                ],
                "color": FUTURE_COLOUR,
                "end": "2013-02-15T19:30:00+00:00",
                "start": "2013-02-15T18:00:00+00:00",
                "title": "Event one title",
                "url": "/diary/edit/event/id/1/view/",
                "hour": 18,
                "tags": [],
            },
        }

        if multiroom_enabled:
            # All showings without room bookings are placed in the virtual "unroomed" lane.
            for sid in expected_showings - {2}:
                expected_data[sid]["resourceIds"] = ["unroomed"]
            # Showing 2 has a room booking → uses the room's resourceId and colour.
            expected_data[2]["resourceIds"] = [2]
            expected_data[2]["id"] = data_by_showing[2]["id"]  # "rb-{pk}" string
            # In multiroom mode, colour comes from the FC resource eventColor,
            # not the event's color key. s_auxiliary_room added (room not is_primary).
            del expected_data[2]["color"]
            expected_data[2]["className"] = expected_data[2]["className"] + [
                "s_auxiliary_room"
            ]

        for sid in expected_showings:
            s_data = data_by_showing[sid]
            self.assertEqual(expected_data[sid], s_data)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_valid_query(self, now_patch):
        self._common_test_valid_query(now_patch, False)

    @override_settings(MULTIROOM_ENABLED=True)
    @patch("django.utils.timezone.now")
    def test_valid_query_multiroom_enabled(self, now_patch):
        self._common_test_valid_query(now_patch, True)


class BatchAddShowingsTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("batch-add-showings", kwargs={"event_id": self.e4.pk})

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add showings on multiple dates")
        self.assertContains(response, "flatpickr-multidate")

    def test_get_404_for_unknown_event(self):
        url = reverse("batch-add-showings", kwargs={"event_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_permission_required(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_post_creates_showings(self):
        initial_count = Showing.objects.filter(event=self.e4).count()
        response = self.client.post(
            self.url,
            {
                "dates": "2099-03-01,2099-03-08",
                "start_time": "19:30",
                "booked_by": "Tester",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Showings added")
        new_count = Showing.objects.filter(event=self.e4).count()
        self.assertEqual(new_count, initial_count + 2)

    def test_created_showings_are_unconfirmed(self):
        self.client.post(
            self.url,
            {
                "dates": "2099-04-01,2099-04-08",
                "start_time": "20:00",
                "booked_by": "Tester",
            },
        )
        new_showings = Showing.objects.filter(
            event=self.e4, start__year=2099, start__month=4
        )
        self.assertEqual(new_showings.count(), 2)
        self.assertTrue(all(not s.confirmed for s in new_showings))

    def test_created_showings_have_correct_times(self):
        self.client.post(
            self.url,
            {
                "dates": "2099-05-10",
                "start_time": "18:00",
                "booked_by": "Tester",
            },
        )
        showing = Showing.objects.get(event=self.e4, start__year=2099, start__month=5)
        local_start = showing.start.astimezone()
        self.assertEqual(local_start.hour, 18)
        self.assertEqual(local_start.minute, 0)

    def test_created_showings_clone_rota(self):
        # Create an event where the latest showing has a known rota
        event = Event(name="Clone rota test event", duration="02:00:00")
        event.save()
        role = Role.objects.filter(standard=True).first()
        source = Showing(
            event=event,
            start=datetime(2099, 5, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
            booked_by="Tester",
            confirmed=True,
        )
        source.save(force=True)
        RotaEntry(showing=source, role=role, rank=1).save()

        url = reverse("batch-add-showings", kwargs={"event_id": event.pk})
        self.client.post(
            url,
            {
                "dates": "2099-06-01",
                "start_time": "19:00",
                "booked_by": "Tester",
            },
        )
        new_showing = Showing.objects.get(
            event=event, start__year=2099, start__month=6
        )
        self.assertEqual(new_showing.rotaentry_set.count(), 1)

    def test_post_with_room_creates_room_booking(self):
        response = self.client.post(
            self.url,
            {
                "dates": "2099-07-01",
                "start_time": "19:00",
                "booked_by": "Tester",
                "room": str(self.room_2.pk),
            },
        )
        self.assertEqual(response.status_code, 200)
        new_showing = Showing.objects.get(
            event=self.e4, start__year=2099, start__month=7
        )
        self.assertEqual(new_showing.room_bookings.count(), 1)

    def test_post_missing_dates_shows_error(self):
        response = self.client.post(
            self.url,
            {
                "dates": "",
                "start_time": "19:00",
                "booked_by": "Tester",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Showings added")

    def test_post_too_many_dates_shows_error(self):
        many_dates = ",".join(
            "2099-08-{:02d}".format(i) for i in range(1, 54)
        )
        response = self.client.post(
            self.url,
            {
                "dates": many_dates,
                "start_time": "19:00",
                "booked_by": "Tester",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Showings added")

    def test_success_page_lists_edit_links(self):
        response = self.client.post(
            self.url,
            {
                "dates": "2099-09-01,2099-09-08",
                "start_time": "20:00",
                "booked_by": "Tester",
            },
        )
        # Success page should include edit links (resolved URL contains /showing/id/)
        self.assertContains(response, "/diary/edit/showing/id/")

    def test_create_as_confirmed_rejected_when_no_terms(self):
        event = Event(name="No terms event")
        event.save()
        url = reverse("batch-add-showings", kwargs={"event_id": event.pk})
        initial_count = Showing.objects.filter(event=event).count()
        response = self.client.post(
            url,
            {
                "dates": "2099-10-01",
                "start_time": "19:00",
                "booked_by": "Tester",
                "confirmed": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add terms to the event before creating confirmed showings.")
        self.assertEqual(Showing.objects.filter(event=event).count(), initial_count)




class EventTemplateFormLayoutTests(DiaryTestsMixin, TestCase):
    """Cost fields are part of EventTemplateForm.Meta.fields but were not
    rendered anywhere on the template detail page - since they're
    non-required model fields, an un-rendered field is simply absent from
    POST data, and Django's ModelForm.save() then silently blanks it on
    every edit. Guard that they stay rendered."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_cost_fields_rendered_on_template_form(self):
        url = reverse(
            "edit_event_template_detail", kwargs={"template_id": self.tmpl1.pk}
        )
        response = self.client.get(url)
        self.assertContains(response, 'name="cost_type"')
        self.assertContains(response, 'name="cost_distributor"')
        self.assertContains(response, 'name="cost_flat_fee_gbp"')
        self.assertContains(response, 'name="cost_percentage_split"')
        self.assertContains(response, 'name="cost_minimum_guarantee_gbp"')
        self.assertContains(response, 'name="cost_total_gbp"')
        self.assertContains(response, 'name="cost_fee_includes_vat"')

    def test_saving_template_preserves_existing_cost_fields(self):
        self.tmpl1.cost_type = "venue_hire"
        self.tmpl1.cost_distributor = "Acme Distribution"
        self.tmpl1.cost_flat_fee_gbp = "150.00"
        self.tmpl1.save()

        url = reverse(
            "edit_event_template_detail", kwargs={"template_id": self.tmpl1.pk}
        )
        get_response = self.client.get(url)
        roles_fs = get_response.context["roles_formset"]
        links_fs = get_response.context["links_formset"]
        rooms_fs = get_response.context["rooms_formset"]

        post_data = {
            "name": self.tmpl1.name,
            "pricing": self.tmpl1.pricing or "",
            "film_information": self.tmpl1.film_information or "",
            "copy_summary": self.tmpl1.copy_summary or "",
            "copy": self.tmpl1.copy or "",
            "cost_type": "venue_hire",
            "cost_distributor": self.tmpl1.cost_distributor,
            "cost_flat_fee_gbp": self.tmpl1.cost_flat_fee_gbp,
            "cost_percentage_split": "",
            "cost_minimum_guarantee_gbp": "",
            "cost_total_gbp": "",
            "terms": self.tmpl1.terms or "",
            "rota_notes": self.tmpl1.rota_notes or "",
        }
        for tag in self.tmpl1.tags.all():
            post_data.setdefault("tags", []).append(tag.pk)
        for fs in (roles_fs, links_fs, rooms_fs):
            post_data[fs.add_prefix("TOTAL_FORMS")] = fs.total_form_count()
            post_data[fs.add_prefix("INITIAL_FORMS")] = fs.initial_form_count()
            post_data[fs.add_prefix("MIN_NUM_FORMS")] = 0
            post_data[fs.add_prefix("MAX_NUM_FORMS")] = 1000
            for f in fs.forms:
                for name in f.fields:
                    key = f.add_prefix(name)
                    value = f[name].value()
                    if value not in (None, ""):
                        post_data[key] = value

        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.tmpl1.refresh_from_db()
        self.assertEqual(self.tmpl1.cost_type, "venue_hire")
        self.assertEqual(self.tmpl1.cost_distributor, "Acme Distribution")
        self.assertEqual(str(self.tmpl1.cost_flat_fee_gbp), "150.00")


class TemplateExportImportTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    # ── Export ───────────────────────────────────────────────────────────────

    def test_export_json_appears_on_detail_page(self):
        url = reverse("edit_event_template_detail", kwargs={"template_id": self.tmpl1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '"name"')
        self.assertContains(response, "Template 1")

    def test_export_json_is_valid_json(self):
        from toolkit.diary.edit_views import _export_template_json
        j = _export_template_json(self.tmpl1)
        data = json.loads(j)
        self.assertEqual(data["name"], "Template 1")
        self.assertIn("role_slots", data)
        self.assertIn("tags", data)

    def test_export_includes_roles_and_tags(self):
        from toolkit.diary.edit_views import _export_template_json
        j = _export_template_json(self.tmpl2)
        data = json.loads(j)
        role_names = [s["role"] for s in data["role_slots"]]
        self.assertIn("Role 1 (standard)", role_names)
        tag_names = data["tags"]
        self.assertIn("tag one", tag_names)

    def test_export_not_shown_to_non_superuser(self):
        import django.contrib.auth.models as auth_models
        import django.contrib.contenttypes as contenttypes
        programmer = auth_models.User.objects.create_user(
            "programmer_test", "", "T3stPassword!X"
        )
        ct = contenttypes.models.ContentType.objects.get_or_create(
            model="", app_label="toolkit"
        )[0]
        write_permission = auth_models.Permission.objects.get(
            content_type=ct, codename="write"
        )
        programmer.user_permissions.add(write_permission)
        self.client.logout()
        self.client.login(username="programmer_test", password="T3stPassword!X")
        url = reverse("edit_event_template_detail", kwargs={"template_id": self.tmpl1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "import-event-template")

    # ── Import ───────────────────────────────────────────────────────────────

    def _import_url(self):
        return reverse("import-event-template")

    def _valid_json(self, name="Import Test"):
        return json.dumps({
            "name": name,
            "pricing": "£5",
            "film_information": "",
            "copy_summary": "A test.",
            "copy": "",
            "terms": "",
            "rota_notes": "",
            "private": False,
            "outside_hire": False,
            "tags": ["tag one"],
            "role_slots": [{"role": "Role 1 (standard)", "count": 2}],
        })

    def test_import_get_renders_form(self):
        response = self.client.get(self._import_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Import event template")

    def test_import_requires_superuser(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(self._import_url())
        self.assertEqual(response.status_code, 302)

    def test_import_creates_template(self):
        response = self.client.post(
            self._import_url(), {"json_text": self._valid_json(), "overwrite": ""}
        )
        self.assertEqual(response.status_code, 302)
        tmpl = EventTemplate.objects.get(name="Import Test")
        self.assertEqual(tmpl.pricing, "£5")

    def test_import_copies_roles(self):
        self.client.post(
            self._import_url(), {"json_text": self._valid_json(), "overwrite": ""}
        )
        tmpl = EventTemplate.objects.get(name="Import Test")
        slot = tmpl.role_slots.first()
        self.assertEqual(slot.role.name, "Role 1 (standard)")
        self.assertEqual(slot.count, 2)

    def test_import_copies_tags(self):
        self.client.post(
            self._import_url(), {"json_text": self._valid_json(), "overwrite": ""}
        )
        tmpl = EventTemplate.objects.get(name="Import Test")
        tag_names = list(tmpl.tags.values_list("name", flat=True))
        self.assertIn("tag one", tag_names)

    def test_import_creates_copy_when_name_exists(self):
        self.client.post(
            self._import_url(), {"json_text": self._valid_json("Template 1"), "overwrite": ""}
        )
        self.assertTrue(EventTemplate.objects.filter(name="Template 1 (copy)").exists())

    def test_import_overwrites_when_flag_set(self):
        initial_pricing = self.tmpl1.pricing
        new_json = json.dumps({
            "name": "Template 1",
            "pricing": "NEW PRICING",
            "role_slots": [],
            "tags": [],
        })
        self.client.post(self._import_url(), {"json_text": new_json, "overwrite": "1"})
        self.tmpl1.refresh_from_db()
        self.assertEqual(self.tmpl1.pricing, "NEW PRICING")

    def test_import_skips_unknown_roles(self):
        j = json.dumps({
            "name": "Unknown Role Test",
            "role_slots": [{"role": "Nonexistent Role XYZ", "count": 1}],
            "tags": [],
        })
        response = self.client.post(self._import_url(), {"json_text": j, "overwrite": ""})
        self.assertEqual(response.status_code, 302)
        tmpl = EventTemplate.objects.get(name="Unknown Role Test")
        self.assertEqual(tmpl.role_slots.count(), 0)

    def test_import_skips_unknown_tags(self):
        j = json.dumps({
            "name": "Unknown Tag Test",
            "role_slots": [],
            "tags": ["nonexistent-tag-xyz"],
        })
        response = self.client.post(self._import_url(), {"json_text": j, "overwrite": ""})
        self.assertEqual(response.status_code, 302)
        tmpl = EventTemplate.objects.get(name="Unknown Tag Test")
        self.assertEqual(tmpl.tags.count(), 0)

    def test_import_invalid_json_shows_error(self):
        response = self.client.post(
            self._import_url(), {"json_text": "not valid json", "overwrite": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid JSON")

    def test_import_empty_input_shows_error(self):
        response = self.client.post(
            self._import_url(), {"json_text": "", "overwrite": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paste a JSON template")


class CreateTemplateFromEventTests(DiaryTestsMixin, TestCase):
    """9.132: "Use as template" pre-fills a new template from an event."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def _url(self, event=None):
        url = reverse("add_event_template")
        if event is not None:
            url += f"?from_event={event.pk}"
        return url

    def test_button_appears_on_event_hub(self):
        response = self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(response, "Save as template")
        self.assertContains(response, self._url(self.e4))

    def test_get_without_from_event_is_unaffected(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial, {})

    def test_get_prefills_scalar_fields(self):
        response = self.client.get(self._url(self.e4))
        self.assertEqual(response.status_code, 200)
        initial = response.context["form"].initial
        self.assertEqual(initial["name"], self.e4.name)
        self.assertEqual(initial["copy"], self.e4.copy)
        self.assertEqual(initial["copy_summary"], self.e4.copy_summary)
        self.assertEqual(initial["terms"], self.e4.terms)
        self.assertEqual(initial["pricing"], self.e4.pricing)
        self.assertEqual(initial["film_information"], self.e4.film_information)
        self.assertEqual(initial["private"], self.e4.private)
        self.assertEqual(initial["outside_hire"], self.e4.outside_hire)

    def test_get_prefills_tags(self):
        response = self.client.get(self._url(self.e4))
        initial_tags = response.context["form"].initial["tags"]
        self.assertEqual(
            set(initial_tags), set(self.e4.tags.values_list("pk", flat=True))
        )

    def test_get_prefills_role_counts_from_latest_showing(self):
        role_1 = Role.objects.get(id=1)
        role_2 = Role.objects.get(id=2)
        # e4s4 is e4's latest showing (see common.py)
        RotaEntry(showing=self.e4s4, role=role_1, rank=1).save()
        RotaEntry(showing=self.e4s4, role=role_1, rank=2).save()
        RotaEntry(showing=self.e4s4, role=role_2, rank=1).save()

        response = self.client.get(self._url(self.e4))
        roles_formset = response.context["roles_formset"]
        counts = {
            form.initial["role"]: form.initial["count"]
            for form in roles_formset.forms
            if form.initial
        }
        self.assertEqual(counts.get(role_1.pk), 2)
        self.assertEqual(counts.get(role_2.pk), 1)

    def test_get_prefills_room_bookings_as_deltas(self):
        RoomBooking(
            showing=self.e4s4,
            room=self.room_2,
            start=self.e4s4.start - timedelta(minutes=30),
            end=self.e4s4.start + timedelta(hours=2),
        ).save()

        response = self.client.get(self._url(self.e4))
        rooms_formset = response.context["rooms_formset"]
        booking_forms = [f for f in rooms_formset.forms if f.initial]
        self.assertEqual(len(booking_forms), 1)
        initial = booking_forms[0].initial
        self.assertEqual(initial["room"], self.room_2.pk)
        self.assertEqual(initial["start_delta_minutes"], -30)
        self.assertEqual(initial["end_delta_minutes"], 120)

    def test_get_prefills_links(self):
        EventLink(event=self.e4, label="Crew chat", url="https://riseup.net/x").save()

        response = self.client.get(self._url(self.e4))
        links_formset = response.context["links_formset"]
        link_forms = [f for f in links_formset.forms if f.initial]
        self.assertEqual(len(link_forms), 1)
        self.assertEqual(link_forms[0].initial["label"], "Crew chat")
        self.assertEqual(link_forms[0].initial["url"], "https://riseup.net/x")

    def test_get_does_not_create_a_template(self):
        """Visiting the prefilled form is read-only - nothing is saved
        until the programmer explicitly submits it."""
        before = EventTemplate.objects.count()
        self.client.get(self._url(self.e4))
        self.assertEqual(EventTemplate.objects.count(), before)
        self.e4.refresh_from_db()
        self.assertIsNone(self.e4.template)
