# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-written"
"""Tests for the per-showing 'Add to calendar' MVP (TASKS.md 9.10.4a)."""

from urllib.parse import urlparse, parse_qs

from django.test import TestCase
from django.urls import reverse

from toolkit.diary.calendar_links import (
    build_ics,
    google_calendar_url,
    outlook_calendar_url,
)

from .common import DiaryTestsMixin


class CalendarLinksTests(DiaryTestsMixin, TestCase):
    def _fresh_showing(self):
        # Fixture sets duration as a string; refetch so TimeField resolves
        from toolkit.diary.models import Showing
        return Showing.objects.select_related("event").prefetch_related("room_bookings__room").get(pk=self.e2s2.pk)

    def test_ics_view_returns_calendar_mime(self):
        url = reverse("single-showing-ics", kwargs={"showing_id": self.e2s2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response["Content-Type"].startswith("text/calendar")
        )
        self.assertIn(
            f'showing-{self.e2s2.pk}.ics',
            response["Content-Disposition"],
        )

    def test_ics_view_404_for_hidden_showing(self):
        # e2s1 is unconfirmed → not public()
        url = reverse("single-showing-ics", kwargs={"showing_id": self.e2s1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_ics_payload_structure(self):
        body = build_ics(self._fresh_showing())
        # CRLF line endings per RFC 5545
        self.assertIn("\r\n", body)
        self.assertTrue(body.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(body.rstrip("\r\n").endswith("END:VCALENDAR"))
        self.assertIn("BEGIN:VEVENT", body)
        self.assertIn("END:VEVENT", body)
        self.assertIn(f"UID:showing-{self.e2s2.pk}@", body)
        # 2 April 2013 19:00 BST = 18:00 UTC
        self.assertIn("DTSTART:20130402T180000Z", body)
        # Event two has duration 01:30:00 → end 20:30 BST = 19:30 UTC
        self.assertIn("DTEND:20130402T193000Z", body)
        self.assertIn("SUMMARY:Event two title", body)

    def test_ics_escapes_special_chars(self):
        self.e2.name = "Title; with, commas\nand newline"
        self.e2.save()
        body = build_ics(self._fresh_showing())
        self.assertIn(
            "SUMMARY:Title\\; with\\, commas\\nand newline", body
        )

    def test_google_calendar_url_has_required_params(self):
        url = google_calendar_url(self._fresh_showing())
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "calendar.google.com")
        self.assertEqual(parsed.path, "/calendar/render")
        qs = parse_qs(parsed.query)
        self.assertEqual(qs["action"], ["TEMPLATE"])
        self.assertEqual(qs["text"], ["Event two title"])
        self.assertEqual(
            qs["dates"], ["20130402T180000Z/20130402T193000Z"]
        )

    def test_outlook_calendar_url_has_required_params(self):
        url = outlook_calendar_url(self._fresh_showing())
        parsed = urlparse(url)
        self.assertEqual(parsed.netloc, "outlook.live.com")
        qs = parse_qs(parsed.query)
        self.assertEqual(qs["rru"], ["addevent"])
        self.assertEqual(qs["subject"], ["Event two title"])
        self.assertEqual(qs["startdt"], ["2013-04-02T18:00:00Z"])
        self.assertEqual(qs["enddt"], ["2013-04-02T19:30:00Z"])

    def test_event_view_renders_calendar_links_for_upcoming_showing(self):
        # Move e2s2 into the future so it counts as upcoming
        from datetime import datetime
        import zoneinfo
        future = datetime(2099, 4, 2, 19, 0, tzinfo=zoneinfo.ZoneInfo("Europe/London"))
        self.e2s2.start = future
        self.e2s2.save(force=True)

        url = reverse("single-event-view", kwargs={"event_id": self.e2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Compact disclosure: aria-label on the icon trigger + the three URLs.
        self.assertContains(response, 'aria-label="Add to calendar"')
        self.assertContains(
            response,
            reverse("single-showing-ics", kwargs={"showing_id": self.e2s2.pk}),
        )
        self.assertContains(response, "calendar.google.com/calendar/render")
        self.assertContains(response, "outlook.live.com/calendar/0/deeplink/compose")
