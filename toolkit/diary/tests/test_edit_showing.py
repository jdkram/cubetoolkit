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


class EditShowing(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def tests_edit_showing_get(self):
        showing = Showing.objects.get(pk=7)

        url = reverse("edit-showing", kwargs={"showing_id": 7})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        # Edit should have existing values:
        self.assertContains(
            response,
            '<input type="datetime-local" name="start" value="2013-06-09T18:00"'
            ' class="jquerydatetimepicker form-control" required id="id_start">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="text" name="booked_by" value="\u0102nother \u0170ser"'
            ' maxlength="64" class="textinput textInput form-control"'
            ' required id="id_booked_by">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="confirmed" class="checkboxinput '
            'custom-control-input" id="id_confirmed" checked>',
            html=True,
            #'<input checked="checked" id="id_confirmed" name="confirmed" '
            #'type="checkbox" />',
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="hide_in_programme" class="checkboxinput '
            'custom-control-input" id="id_hide_in_programme">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="cancelled" class="checkboxinput '
            'custom-control-input" id="id_cancelled">',
            html=True,
        )
        self.assertContains(
            response,
            '<input type="checkbox" name="discounted" class="checkboxinput '
            'custom-control-input" id="id_discounted">',
            html=True,
        )

        # Rota notes should now appear in the form textarea:
        self.assertContains(response, showing.rota_notes)

        # Rota edit — number inputs with native up/down arrows:
        self.assertContains(
            response,
            '<input class="rota_count" id="id_role_1" max="8" min="0" '
            'name="role_1" type="number" value="0" />',
            html=True,
        )
        # Non-standard roles use the same number spinner UI:
        self.assertContains(
            response,
            '<input class="rota_count" id="id_other_2" max="8" min="0" '
            'name="other_2" type="number" value="1" />',
            html=True,
        )
        self.assertContains(
            response,
            '<input class="rota_count" id="id_other_3" max="8" min="0" '
            'name="other_3" type="number" value="0" />',
            html=True,
        )

    def _test_edit_showing_common(self, now_patch, multiroom_enabled):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 7})
        response = self.client.post(
            url,
            data={
                "start": "15/08/2013 19:30",
                "booked_by": "Yet \u0102nother \u0170ser",
                "confirmed": "on",
                "hide_in_programme": "on",
                "cancelled": "on",
                "discounted": "on",
                "role_1": "3",
                "other_3": "1",
                # RoomBookingInlineFormSet management form (no bookings submitted)
                "room_bookings-TOTAL_FORMS": "0",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": 4}),
        )

        # Check showing was updated:
        showing = Showing.objects.get(id=7)
        self.assertEqual(showing.start, datetime(2013, 8, 15, 18, 30, tzinfo=UTC))
        self.assertEqual(showing.booked_by, "Yet \u0102nother \u0170ser")
        self.assertEqual(showing.confirmed, True)
        self.assertEqual(showing.hide_in_programme, True)
        self.assertEqual(showing.cancelled, True)
        self.assertEqual(showing.discounted, True)
        # Room is now tracked via RoomBooking; no room bookings submitted so none should exist
        self.assertFalse(showing.room_bookings.exists())
        # Check rota is as expected:
        rota = list(showing.rotaentry_set.all())
        self.assertEqual(len(rota), 4)
        self.assertEqual(rota[0].role_id, 1)
        self.assertEqual(rota[0].rank, 1)
        self.assertEqual(rota[1].role_id, 1)
        self.assertEqual(rota[1].rank, 2)
        self.assertEqual(rota[2].role_id, 1)
        self.assertEqual(rota[2].rank, 3)
        self.assertEqual(rota[3].role_id, 3)
        self.assertEqual(rota[3].rank, 1)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def tests_edit_showing(self, now_patch):
        self._test_edit_showing_common(now_patch, False)

    @override_settings(MULTIROOM_ENABLED=True)
    @patch("django.utils.timezone.now")
    def tests_edit_showing_multiroom_enabled(self, now_patch):
        self._test_edit_showing_common(now_patch, True)

    @patch("django.utils.timezone.now")
    def tests_edit_showing_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 1})
        response = self.client.post(
            url,
            data={
                "start": "15/08/2013 19:30",
                "booked_by": "Valid",
                "role_1": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")
        self.assertFormError(
            response.context["form"], None, "Cannot amend a historic booking"
        )

    @patch("django.utils.timezone.now")
    def tests_edit_showing_missing_data(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(
            url,
            data={
                "start": "",
                "booked_by": "",
                "role_1": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(
            response.context["form"], "start", "This field is required."
        )
        self.assertFormError(
            response.context["form"], "booked_by", "This field is required."
        )

    @patch("django.utils.timezone.now")
    def tests_edit_showing_invalid_date_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(
            url,
            data={
                "start": "15/01/2013 19:30",
                "booked_by": "Valid",
                "role_1": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(response.context["form"], "start", "Must be in the future")

    @patch("django.utils.timezone.now")
    def tests_edit_showing_invalid_date_malformed(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 3})
        response = self.client.post(
            url,
            data={
                "start": "Spinach",
                "booked_by": "Valid",
                "role_1": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        self.assertFormError(
            response.context["form"], "start", "Enter a valid date/time."
        )

    @patch("django.utils.timezone.now")
    def tests_edit_showing_terms_too_short(self, now_patch):
        now_patch.return_value = self._fake_now

        self.e4s3.confirmed = False
        self.e4s3.save()

        event = self.e4s3.event
        event.terms = "too short"
        event.save()

        self.assertFalse(self.e4s3.event.terms_long_enough())

        url = reverse("edit-showing", kwargs={"showing_id": self.e4s3.id})
        response = self.client.post(
            url,
            data={
                "start": "15/08/2013 19:30",
                "booked_by": "lazy typist",
                "confirmed": "on",
                "role_1": "3",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_showing.html")

        # must still not be confirmed:
        self.e4s3.refresh_from_db()
        self.assertFalse(self.e4s3.confirmed)

        self.assertContains(
            response,
            "Events require terms information (unless they are tagged with one of meeting/training).",
        )

    @patch("django.utils.timezone.now")
    def tests_edit_showing_saves_rota_notes(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": self.e4s3.id})
        response = self.client.post(
            url,
            data={
                "start": "15/08/2013 19:30",
                "booked_by": "\u0102nother \u0170ser",
                "confirmed": "on",
                "role_1": "0",
                "rota_notes": "Updated rota notes via form.",
                "room_bookings-TOTAL_FORMS": "0",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.id}),
        )
        self.e4s3.refresh_from_db()
        self.assertEqual(self.e4s3.rota_notes, "Updated rota notes via form.")

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def tests_edit_showing_datetime_local_format(self, now_patch):
        """datetime-local T-format produces the same saved value as legacy format."""
        now_patch.return_value = self._fake_now

        url = reverse("edit-showing", kwargs={"showing_id": 7})
        response = self.client.post(
            url,
            data={
                "start": "2013-08-15T19:30",
                "booked_by": "T-format User",
                "confirmed": "on",
                "role_1": "0",
                "room_bookings-TOTAL_FORMS": "0",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": 4}),
        )
        showing = Showing.objects.get(id=7)
        self.assertEqual(showing.start, datetime(2013, 8, 15, 18, 30, tzinfo=UTC))


class JQueryDateTimePickerWidgetTest(TestCase):
    """Unit tests for JQueryDateTimePicker.value_from_datadict."""

    def setUp(self):
        self.widget = JQueryDateTimePicker()

    def test_t_format_normalised_to_space(self):
        result = self.widget.value_from_datadict(
            {"start": "2013-08-15T19:30"}, {}, "start"
        )
        self.assertEqual(result, "2013-08-15 19:30")

    def test_space_format_passthrough(self):
        result = self.widget.value_from_datadict(
            {"start": "2013-08-15 19:30"}, {}, "start"
        )
        self.assertEqual(result, "2013-08-15 19:30")

    def test_datetime_object_passthrough(self):
        dt = datetime(2013, 8, 15, 19, 30)
        result = self.widget.value_from_datadict({"start": dt}, {}, "start")
        self.assertIsInstance(result, datetime)
        self.assertEqual(result, dt)


class DeleteShowing(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_delete_showing_must_post(self):

        url = reverse("delete-showing", kwargs={"showing_id": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        # Will raise an exception if it doesn't exist
        Showing.objects.get(id=1)

    @patch("django.utils.timezone.now")
    def test_delete_showing_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("delete-showing", kwargs={"showing_id": 1})
        response = self.client.post(url)

        # Should redirect to edit page:
        self.assertRedirects(
            response, reverse("edit-showing", kwargs={"showing_id": 1})
        )

        # Showing should still exist:
        # Will raise an exception if it doesn't exist
        Showing.objects.get(id=1)

    @patch("django.utils.timezone.now")
    def test_delete_showing(self, now_patch):
        now_patch.return_value = self._fake_now

        self.assertTrue(Showing.objects.filter(id=7))

        url = reverse("delete-showing", kwargs={"showing_id": 7})
        response = self.client.post(url)

        # Showing should have been deleted
        self.assertFalse(Showing.objects.filter(id=7))

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )


class UpdateShowingStatus(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_not_allowed(self):
        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    @patch("django.utils.timezone.now")
    def test_confirm(self, now_patch):
        now_patch.return_value = self._fake_now
        self.e4s3.confirmed = False
        self.e4s3.save()

        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.post(url, data={"action": "confirm"})
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )
        self.e4s3.refresh_from_db()
        self.assertTrue(self.e4s3.confirmed)

    @patch("django.utils.timezone.now")
    def test_unconfirm(self, now_patch):
        now_patch.return_value = self._fake_now
        # e4s3 starts as confirmed=True
        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.post(url, data={"action": "unconfirm"})
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )
        self.e4s3.refresh_from_db()
        self.assertFalse(self.e4s3.confirmed)

    @patch("django.utils.timezone.now")
    def test_cancel(self, now_patch):
        now_patch.return_value = self._fake_now
        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.post(url, data={"action": "cancel"})
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )
        self.e4s3.refresh_from_db()
        self.assertTrue(self.e4s3.cancelled)
        self.assertFalse(self.e4s3.confirmed)

    @patch("django.utils.timezone.now")
    def test_uncancel(self, now_patch):
        now_patch.return_value = self._fake_now
        self.e4s3.cancelled = True
        self.e4s3.save()

        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.post(url, data={"action": "uncancel"})
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )
        self.e4s3.refresh_from_db()
        self.assertFalse(self.e4s3.cancelled)

    @patch("django.utils.timezone.now")
    def test_confirm_without_terms_blocked(self, now_patch):
        now_patch.return_value = self._fake_now
        self.e4.terms = ""
        self.e4.save()
        self.e4s3.confirmed = False
        self.e4s3.save()

        url = reverse("update-showing-status", kwargs={"showing_id": self.e4s3.pk})
        response = self.client.post(url, data={"action": "confirm"})
        # Redirects back to hub but showing should not be confirmed
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk}),
        )
        self.e4s3.refresh_from_db()
        self.assertFalse(self.e4s3.confirmed)

    @patch("django.utils.timezone.now")
    def test_confirm_meeting_without_terms_succeeds(self, now_patch):
        # e7 is tagged 'meeting', so terms are not required
        self.assertEqual(self.e7.all_showings_confirmed(), False)
        now_patch.return_value = self._fake_now

        url = reverse("update-showing-status", kwargs={"showing_id": self.e7s1.pk})
        response = self.client.post(url, data={"action": "confirm"})
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e7.pk}),
        )
        self.e7s1.refresh_from_db()
        self.assertTrue(self.e7s1.confirmed)

    @patch("django.utils.timezone.now")
    def test_past_showing_not_changed(self, now_patch):
        now_patch.return_value = self._fake_now
        # e2s1 is in the past (1/4/2013 < 1/6/2013)
        self.assertFalse(self.e2s1.confirmed)

        url = reverse("update-showing-status", kwargs={"showing_id": self.e2s1.pk})
        response = self.client.post(url, data={"action": "confirm"})
        # Still redirects to the hub, but status is unchanged
        self.assertEqual(response.status_code, 302)
        self.e2s1.refresh_from_db()
        self.assertFalse(self.e2s1.confirmed)


class EditShowingRoomBookingTests(DiaryTestsMixin, TestCase):
    """Integration tests for RoomBooking formset handling in edit_showing."""

    UTC = zoneinfo.ZoneInfo("UTC")

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        # e4s3 is showing pk=7 (event e4, start 2013-06-09 18:00 UTC)
        self.showing = Showing.objects.get(pk=7)
        self.url = reverse("edit-showing", kwargs={"showing_id": 7})

    def _base_post(self, extra=None):
        data = {
            "start": "09/06/2013 18:00",
            "booked_by": "Tester",
            "confirmed": "on",
            "role_1": "0",
            "room_bookings-TOTAL_FORMS": "0",
            "room_bookings-INITIAL_FORMS": "0",
            "room_bookings-MIN_NUM_FORMS": "0",
            "room_bookings-MAX_NUM_FORMS": "1000",
        }
        if extra:
            data.update(extra)
        return data

    @patch("django.utils.timezone.now")
    def test_post_creates_room_booking(self, now_patch):
        now_patch.return_value = datetime(2013, 1, 1, tzinfo=self.UTC)
        response = self.client.post(
            self.url,
            data={
                "start": "09/06/2013 18:00",
                "booked_by": "Tester",
                "confirmed": "on",
                "role_1": "0",
                "room_bookings-TOTAL_FORMS": "1",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
                "room_bookings-0-room": str(self.room_2.pk),
                "room_bookings-0-start_time": "19:00",
                "room_bookings-0-end_time": "",
                "room_bookings-0-notes": "",
                "room_bookings-0-DELETE": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        rb = self.showing.room_bookings.first()
        self.assertIsNotNone(rb)
        self.assertEqual(rb.room_id, self.room_2.pk)

    @patch("django.utils.timezone.now")
    def test_post_no_bookings_clears_existing(self, now_patch):
        now_patch.return_value = datetime(2013, 1, 1, tzinfo=self.UTC)
        RoomBooking.objects.create(
            showing=self.showing,
            room=self.room_2,
            start=self.showing.start,
        )
        self.assertEqual(self.showing.room_bookings.count(), 1)
        response = self.client.post(self.url, data=self._base_post({
            "room_bookings-INITIAL_FORMS": "1",
            "room_bookings-TOTAL_FORMS": "1",
            "room_bookings-0-id": str(self.showing.room_bookings.first().pk),
            "room_bookings-0-room": str(self.room_2.pk),
            "room_bookings-0-start": "09/06/2013 19:00",
            "room_bookings-0-end": "",
            "room_bookings-0-notes": "",
            "room_bookings-0-DELETE": "on",
        }))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.showing.room_bookings.exists())

    @patch("django.utils.timezone.now")
    def test_get_includes_room_booking_formset(self, now_patch):
        now_patch.return_value = datetime(2013, 1, 1, tzinfo=self.UTC)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("room_booking_formset", response.context)
        self.assertIn("rooms_json", response.context)

    @patch("django.utils.timezone.now")
    def test_overlapping_booking_shows_clash_warning(self, now_patch):
        now_patch.return_value = datetime(2013, 1, 1, tzinfo=self.UTC)
        # Create a confirmed showing in the same room for an overlapping time
        other_event = Event.objects.create(name="Other Event", duration="02:00:00")
        other_showing = Showing.objects.create(
            event=other_event,
            start=datetime(2013, 6, 9, 18, 0, tzinfo=self.UTC),
            booked_by="Other",
            confirmed=True,
        )
        RoomBooking.objects.create(
            showing=other_showing,
            room=self.room_2,
            start=datetime(2013, 6, 9, 18, 0, tzinfo=self.UTC),
            end=datetime(2013, 6, 9, 21, 0, tzinfo=self.UTC),
        )
        # Now submit the edit_showing form adding room_2 at an overlapping time
        response = self.client.post(
            self.url,
            data={
                "start": "09/06/2013 18:00",
                "booked_by": "Tester",
                "confirmed": "on",
                "role_1": "0",
                "room_bookings-TOTAL_FORMS": "1",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
                "room_bookings-0-room": str(self.room_2.pk),
                "room_bookings-0-start_time": "19:00",
                "room_bookings-0-end_time": "21:00",
                "room_bookings-0-notes": "",
                "room_bookings-0-DELETE": "",
            },
        )
        # Non-blocking: page re-renders with 200 and a clashes context
        self.assertEqual(response.status_code, 200)
        self.assertIn("clashes", response.context)
        self.assertTrue(len(response.context["clashes"]) > 0)
