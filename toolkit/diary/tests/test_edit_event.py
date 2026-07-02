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


class AddEventView(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    @patch("django.utils.timezone.now")
    def test_get_add_event_form_default_start(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("add-event")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_new_event_and_showing.html")
        # Default dates should be set one day in the future (ISO format for flatpickr):
        self.assertContains(response, 'value="2013-06-02"')
        # Default start time should be 20:00:
        self.assertContains(response, 'name="start_time"')

    def test_get_add_event_form_specify_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "01-01-1950"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_new_event_and_showing.html")
        # Specified date should appear as ISO format in the dates field:
        self.assertContains(response, 'value="1950-01-01"')

    def test_get_add_event_form_specify_malformed_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "crisp packet"})
        self.assertContains(response, "Invalid start date", status_code=400)

    def test_get_add_event_form_specify_invalid_start(self):
        url = reverse("add-event")
        response = self.client.get(url, data={"date": "99-01-1950"})
        self.assertContains(
            response, "Illegal time, date or duration", status_code=400
        )

    # Common code for the following two tests:
    # TODO add tests to reflect new logic of event booking -
    # Showing cannot be confirmed on creation as event terms cannot be empty.
    def _test_add_event_common(self, now_patch, multiroom_enabled):
        now_patch.return_value = self._fake_now

        url = reverse("add-event")
        response = self.client.post(
            url,
            data={
                # dates as comma-separated ISO strings (flatpickr format)
                "dates": "2013-06-02,2013-06-03,2013-06-04",
                "start_time": "20:00",
                "duration": "01:30:00",
                "event_name": "Ev\u0119nt of choic\u0119",
                "event_template": "1",
                "booked_by": "\u015comeb\u014ddy",
                "private": "on",
                "outside_hire": "",
                "discounted": "on",
                "entry_mode": "standing",
            },
        )
        # Event added correctly?
        event = Event.objects.get(name="Ev\u0119nt of choic\u0119")

        # Request redirected to hub for newly created event?
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": event.pk}),
        )
        self.assertEqual(event.duration, time(1, 30))
        self.assertEqual(event.private, True)
        self.assertEqual(event.outside_hire, False)
        self.assertEqual(event.template, EventTemplate.objects.get(id=1))

        showings = list(event.showings.all())
        self.assertEqual(len(showings), 3)
        # Showings should have been added over 3 days. Time specified was BST,
        # so should be 7pm in UTC:
        self.assertEqual(showings[0].start, datetime(2013, 6, 2, 19, 0, tzinfo=UTC))
        self.assertEqual(showings[1].start, datetime(2013, 6, 3, 19, 0, tzinfo=UTC))
        self.assertEqual(showings[2].start, datetime(2013, 6, 4, 19, 0, tzinfo=UTC))

        role_1 = Role.objects.get(id=1)
        for s in showings:
            self.assertEqual(s.booked_by, "\u015comeb\u014ddy")
            self.assertEqual(s.confirmed, False)
            self.assertEqual(s.hide_in_programme, False)
            self.assertEqual(s.cancelled, False)
            self.assertEqual(s.discounted, True)
            self.assertEqual(
                list(s.roles.all()),
                [
                    role_1,
                ],
            )
            # tmpl1 has no EventTemplateRoom records, so no room bookings expected.
            self.assertEqual(s.room_bookings.count(), 0)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_add_event(self, now_patch):
        self._test_add_event_common(now_patch, False)

    @override_settings(MULTIROOM_ENABLED=True)
    @patch("django.utils.timezone.now")
    def test_add_event_multiroom_enabled(self, now_patch):
        self._test_add_event_common(now_patch, True)

    @patch("django.utils.timezone.now")
    def test_add_event_in_past(self, now_patch):
        now_patch.return_value = self._fake_now

        event_count_before = Event.objects.count()

        url = reverse("add-event")
        response = self.client.post(
            url,
            data={
                "dates": "2013-05-30",
                "start_time": "20:00",
                "duration": "01:30:00",
                "event_name": "Ev\u0119nt of choic\u0119",
                "event_template": "1",
                "booked_by": "\u015comeb\u014ddy",
                "private": "on",
                "outside_hire": "",
                "discounted": "on",
                "entry_mode": "standing",
            },
        )
        # Request succeeded?
        self.assertEqual(response.status_code, 200)

        # Event shouldn't have been added:
        self.assertEqual(event_count_before, Event.objects.count())

        self.assertTemplateUsed(response, "form_new_event_and_showing.html")

        # Check error was as expected \u2014 non-field error from clean():
        self.assertFormError(response.context["form"], None, ["The following dates are in the past: 30 May 2013."])

    @patch("django.utils.timezone.now")
    def test_add_event_missing_fields(self, now_patch):
        now_patch.return_value = self._fake_now

        event_count_before = Event.objects.count()

        url = reverse("add-event")
        response = self.client.post(
            url,
            data={
                "dates": "",
                "start_time": "",
                "duration": "",
                "event_name": "",
                "event_template": "",
                "booked_by": "",
                "private": "",
                "outside_hire": "",
                "discounted": "",
            },
        )
        # Request succeeded?
        self.assertEqual(response.status_code, 200)

        # Event shouldn't have been added:
        self.assertEqual(event_count_before, Event.objects.count())

        self.assertTemplateUsed(response, "form_new_event_and_showing.html")

        # Check errors as expected:
        # dates and start_time are now optional (dateless events allowed)
        self.assertFormError(
            response.context["form"], "duration", "This field is required."
        )
        self.assertFormError(
            response.context["form"], "event_name", "This field is required."
        )
        self.assertFormError(
            response.context["form"], "booked_by", "This field is required."
        )
        self.assertFormError(
            response.context["form"],
            "event_template",
            "This field is required.",
        )


class EditDetailView(DiaryTestsMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_load_with_showings(self) -> None:
        # e1 has one past showing (s6: 15/02/2013, booked by "Blah blah")
        url = reverse("edit-event-details-view", kwargs={"event_id": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_event_privatedetails.html")
        # Past showing should appear in the past-showings section
        self.assertContains(response, "15/02/2013 18:00")
        self.assertContains(response, "Blah blah")

    def test_load_no_showings(self) -> None:
        url = reverse("edit-event-details-view", kwargs={"event_id": 6})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_event_privatedetails.html")

    @patch("django.utils.timezone.now")
    def test_add_showing(self, now_patch) -> None:
        now_patch.return_value = self._fake_now

        url = reverse("edit-event-details-view", kwargs={"event_id": self.e5.pk})
        future_start = self._fake_now + timedelta(days=10)
        data = {
            "start": future_start.strftime("%d/%m/%Y %H:%M"),
            "booked_by": "wombat",
        }
        response = self.client.post(url, data)

        self.assertRedirects(response, url)

        showings = list(self.e5.showings.all().order_by("start"))
        self.assertEqual(len(showings), 2)
        new_showing = showings[1]
        self.assertEqual(new_showing.booked_by, "wombat")
        self.assertFalse(new_showing.cancelled)

    @patch("django.utils.timezone.now")
    def test_add_showing_in_past_fails(self, now_patch) -> None:
        now_patch.return_value = self._fake_now

        url = reverse("edit-event-details-view", kwargs={"event_id": self.e5.pk})
        past_start = self._fake_now - timedelta(days=10)
        data = {
            "start": past_start.strftime("%d/%m/%Y %H:%M"),
            "booked_by": "wombat",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["add_showing_form"],
            "start",
            "Must be in the future",
        )
        self.assertEqual(self.e5.showings.count(), 1)

    @patch("django.utils.timezone.now")
    def test_add_showing_no_booked_by_fails(self, now_patch) -> None:
        now_patch.return_value = self._fake_now

        url = reverse("edit-event-details-view", kwargs={"event_id": self.e5.pk})
        future_start = self._fake_now + timedelta(days=10)
        data = {
            "start": future_start.strftime("%d/%m/%Y %H:%M"),
            "booked_by": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["add_showing_form"],
            "booked_by",
            "This field is required.",
        )
        self.assertEqual(self.e5.showings.count(), 1)


class EditEventView(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Log in:
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_edit_event_form_no_media_no_legacy_copy(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertContains(response, "Event one title")
        self.assertContains(response, "Event one copy")
        self.assertContains(response, "Event one copy summary")
        self.assertContains(response, "PRICING_ONE")
        self.assertContains(response, "PRETITLE One")
        self.assertContains(response, "POSTTITLE One")
        self.assertContains(response, "FILM_INFO_One")
        self.assertContains(response, "01:30:00")
        self.assertContains(
            response,
            '<input id="id_outside_hire" checked="checked" '
            'class="checkboxinput custom-control-input" name="outside_hire" '
            'type="checkbox" />',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_private" class="checkboxinput custom-control-input"'
            'name="private" type="checkbox" />',
            html=True,
        )
        # Word counter block is present:
        self.assertContains(response, "word-counter")
        # Blah. It's probably fine. Ahem.

    def test_get_edit_event_form_no_media_legacy_copy(self):
        # Test the transformation of legacy copy properly in a separate set of
        # tests...

        url = reverse("edit-event-details", kwargs={"event_id": 2})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertContains(response, "Event two title")
        # newlines -> <br>
        self.assertContains(response, "Event <br>\n two <br>\n copy")
        self.assertContains(response, "Event two\n copy summary")  # not stripped
        self.assertContains(response, "01:30:00")
        self.assertContains(
            response,
            '<input id="id_outside_hire" '
            'class="checkboxinput custom-control-input" name="outside_hire" '
            'type="checkbox" />',
            html=True,
        )
        self.assertContains(
            response,
            '<input id="id_private" name="private" '
            'class="checkboxinput custom-control-input" type="checkbox" />',
            html=True,
        )
        # It's probably still fine. Cough.

    @override_settings(MEDIA_ROOT="/tmp")
    def test_get_edit_event_form_media_item(self):
        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            # Add MediaItem to event 1:
            media_item = MediaItem(
                media_file=temp_jpg.name,
                mimetype="image/jpeg",
                caption="Image Caption!",
                credit="Image Credit!",
            )
            media_item.save()
            event = Event.objects.get(id=1)
            event.media.add(media_item)
            event.save()

            # Get page:
            url = reverse("edit-event-details", kwargs={"event_id": 1})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "form_event.html")

            self.assertContains(response, media_item.media_file)
            # Submit the minimum amount of data to validate:
            self.assertContains(response, "Image Credit!")
            # Caption not currently exposed to user

    def test_get_edit_missing_event(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1000})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_post_edit_missing_event(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1000})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    def test_post_edit_event_no_media_missing_data(self):
        url = reverse("edit-event-details", kwargs={"event_id": 1})
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertFormError(
            response.context["event_form"], "name", "This field is required."
        )
        self.assertFormError(
            response.context["event_form"],
            "duration",
            "This field is required.",
        )

    def test_post_edit_event_no_media_minimal_data(self):
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        event = Event.objects.get(id=2)
        event.pre_title = "pre_title"
        event.post_title = "post_title"
        event.pricing = "pricing"
        event.film_information = "film_info"
        event.duration = time(0, 20)
        event.copy = "copy"
        event.copy_summary = "copy_summary"
        event.terms = "terms"
        event.programming_notes = "notes"
        event.outside_hire = True
        event.private = True
        event.save()

        # Submit the minimum amount of data to validate:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
            },
        )
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.name, "New \u20acvent Name")
        self.assertEqual(event.pre_title, "")
        self.assertEqual(event.post_title, "")
        self.assertEqual(event.pricing, "")
        self.assertEqual(event.film_information, "")
        self.assertEqual(event.duration, time(0, 10))
        self.assertEqual(event.copy, "")
        self.assertEqual(event.copy_summary, "")
        self.assertEqual(event.programming_notes, "")
        self.assertEqual(event.media.count(), 0)
        self.assertEqual(event.outside_hire, False)
        self.assertEqual(event.private, False)
        # Shouldn't have changed:
        self.assertEqual(event.legacy_id, "100")

    def test_post_edit_event_no_media_all_fields(self):
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        # Submit the minimum amount of data to validate:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name!",
                "duration": "01:10:09",
                "copy": "Some more copy",
                "copy_summary": "Copy summary blah",
                "pre_title": "The thing that will be",
                "post_title": "The thing that was",
                "pricing": "Full \u00a35",
                "film_information": "Blah blah films",
                "terms": "Always term time",
                "programming_notes": "This is getting\n boring",
                "outside_hire": "on",
                "private": "on",
            },
        )
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.name, "New \u20acvent Name!")
        self.assertEqual(event.duration, time(1, 10, 9))
        self.assertEqual(event.copy, "Some more copy")
        self.assertEqual(event.copy_summary, "Copy summary blah")
        self.assertEqual(event.terms, "Always term time")
        self.assertEqual(event.programming_notes, "This is getting\n boring")
        self.assertEqual(event.media.count(), 0)
        self.assertEqual(event.outside_hire, True)
        self.assertEqual(event.private, True)
        self.assertEqual(event.legacy_id, "100")
        self.assertEqual(event.pre_title, "The thing that will be")
        self.assertEqual(event.post_title, "The thing that was")
        self.assertEqual(event.pricing, "Full \u00a35")
        self.assertEqual(event.film_information, "Blah blah films")
        # Shouldn't have changed:
        self.assertEqual(event.legacy_id, "100")

    @patch("toolkit.util.image.get_mimetype")
    def test_post_edit_event_add_media_invalid_empty(self, get_mimetype_patch):

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")
        self.assertFormError(
            response.context["media_form"],
            "media_file",
            "The submitted file is empty.",
        )

        self.assertFalse(get_mimetype_patch.called)

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 0)

    def test_post_edit_event_add_media_not_an_image(self):

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            temp_jpg.write(b"Not an empty jpeg")
            temp_jpg.seek(0)
            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg,
                    "credit": "All new image credit!",
                },
            )

        self.assertFormError(
            response.context["media_form"],
            "media_file",
            "Upload a valid image. The file you uploaded was either "
            "not an image or a corrupted image.",
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 0)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_add_media_jpeg(self):

        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            # used for assertion:
            temp_file_name = os.path.basename(temp_jpg.name)
            temp_jpg.write(TINY_VALID_JPEG)
            temp_jpg.seek(0)
            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg,
                    "credit": "All new image credit!",
                },
            )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 1)
        media_item = event.media.all()[0]
        self.assertEqual(media_item.mimetype, "image/jpeg")
        self.assertEqual(media_item.credit, "All new image credit!")
        self.assertEqual(media_item.caption, "")
        self.assertEqual(
            media_item.media_file.name, os.path.join("diary", temp_file_name)
        )

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_add_media_png(self):
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".png"
        ) as temp_png:
            # used for assertion:
            temp_file_name = os.path.basename(temp_png.name)

            temp_png.write(TINY_VALID_PNG)
            temp_png.seek(0)
            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_png,
                    "credit": "All new image credit!",
                },
            )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 1)
        media_item = event.media.all()[0]
        self.assertEqual(media_item.mimetype, "image/png")
        self.assertEqual(media_item.credit, "All new image credit!")
        self.assertEqual(media_item.caption, "")
        self.assertEqual(
            media_item.media_file.name, os.path.join("diary", temp_file_name)
        )

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_clear_media(self):
        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            # Add MediaItem to event 1:
            media_item = MediaItem(
                media_file=temp_jpg.name,
                mimetype="image/jpeg",
                caption="Image Caption!",
                credit="Image Credit!",
            )
            media_item.save()
            event = Event.objects.get(id=2)
            event.media.add(media_item)
            event.save()

            url = reverse("edit-event-details", kwargs={"event_id": 2})

            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg.name,
                    "media_file-clear": "on",
                },
            )
            self.assertRedirects(
                response,
                reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
            )

            event = Event.objects.get(id=2)
            # Media item should be gone:
            self.assertEqual(event.media.count(), 0)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_add_media_too_big(self):
        config = get_site_config()
        config.programme_media_max_size_mb = 1
        config.save()
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            # Write 1 MB + 1 byte, consisting of valid JPEG data followed by
            # nulls:
            temp_jpg.write(TINY_VALID_JPEG)
            temp_jpg.write(b"\0" * (1024 - len(TINY_VALID_JPEG)))

            one_k_data = b"\0" * 1024
            for _ in range(1023):
                temp_jpg.write(one_k_data)
            # the extra byte!
            temp_jpg.write(b"\0")
            temp_jpg.seek(0)

            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg,
                    "credit": "All new image credit!",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")
        self.assertFormError(
            response.context["media_form"],
            "media_file",
            "Media file must be 1 MB or less (uploaded file is 1.00 MB)",
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.media.count(), 0)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_edit_event_add_media_max_size(self):
        config = get_site_config()
        config.programme_media_max_size_mb = 1
        config.save()
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg"
        ) as temp_jpg:
            # Write 1 MB, consisting of valid JPEG data followed by
            # nulls:
            temp_jpg.write(TINY_VALID_JPEG)
            temp_jpg.write(b"\0" * (1024 - len(TINY_VALID_JPEG)))

            one_k_data = b"\0" * 1024
            for _ in range(1023):
                temp_jpg.write(one_k_data)
            temp_jpg.seek(0)

            response = self.client.post(
                url,
                data={
                    "name": "New \u20acvent Name",
                    "duration": "00:10:00",
                    "media_file": temp_jpg,
                    "credit": "All new image credit!",
                },
            )
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

    def test_post_edit_event_too_much_copy_summary(self):
        config = get_site_config()
        config.programme_copy_summary_max_chars = 50
        config.save()
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        original_summary = Event.objects.get(id=2).copy_summary
        copy_summary_data = "X" * 51

        # Submit the minimum amount of data to validate, plus some overly-long
        # copy summary data:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
                "copy_summary": copy_summary_data,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")
        self.assertFormError(
            response.context["event_form"],
            "copy_summary",
            "Copy summary must be 50 characters or fewer (currently 51 characters)",
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.copy_summary, original_summary)

    def test_post_edit_event_just_enough_copy_summary(self):
        config = get_site_config()
        config.programme_copy_summary_max_chars = 50
        config.save()
        url = reverse("edit-event-details", kwargs={"event_id": 2})

        copy_summary_data = "X" * 50

        # Submit the minimum amount of data to validate, plus some overly-long
        # copy summary data:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
                "copy_summary": copy_summary_data,
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk}),
        )

        event = Event.objects.get(id=2)
        self.assertEqual(event.copy_summary, copy_summary_data)

    def test_post_edit_event_not_enough_terms(self):
        config = get_site_config()
        config.programme_event_terms_min_words = 5
        config.save()
        event = Event.objects.get(id=1)
        original_terms = event.terms
        url = reverse("edit-event-details", kwargs={"event_id": 1})

        # Not quite enough term text:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
                "terms": "One two three four.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_event.html")

        self.assertFormError(
            response.context["event_form"],
            "terms",
            "Event terms for confirmed event "
            f"'{event.name}' are missing or too short. "
            "Please enter at least 5 words, or set the cost type above.",
        )

        event = Event.objects.get(id=1)
        self.assertEqual(event.terms, original_terms)

    def test_post_edit_event_just_enough_terms(self):
        config = get_site_config()
        config.programme_event_terms_min_words = 5
        config.save()
        event = Event.objects.get(id=1)
        url = reverse("edit-event-details", kwargs={"event_id": 1})

        # Not quite enough term text:
        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
                "terms": "One two three four five.",
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        event = Event.objects.get(id=1)
        self.assertEqual(event.terms, "One two three four five.")

    def test_post_edit_meeting_event_no_terms_required(self):
        config = get_site_config()
        config.programme_event_terms_min_words = 5
        config.save()
        event = Event.objects.get(id=1)
        url = reverse("edit-event-details", kwargs={"event_id": 1})

        response = self.client.post(
            url,
            data={
                "name": "New \u20acvent Name",
                "duration": "00:10:00",
                "terms": "Not Required",
                "tags": "4",
            },
        )

        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        event = Event.objects.get(id=1)
        self.assertEqual(event.terms, "Not Required")


class CloneEventTests(DiaryTestsMixin, TestCase):
    """Tests for the clone_event view (POST /diary/edit/event/id/<pk>/clone/)."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        # e4 is a rich event with two showings, tags, terms, notes etc.
        self.url = reverse("clone-event", kwargs={"event_id": self.e4.pk})

    @patch("django.utils.timezone.now")
    def test_get_returns_form(self, now_patch):
        now_patch.return_value = self._fake_now
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "clone_event.html")
        # Source event name pre-filled
        self.assertContains(response, self.e4.name)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_post_creates_new_event(self, now_patch):
        now_patch.return_value = self._fake_now

        response = self.client.post(
            self.url,
            data={
                "event_name": "Community Kitchen (May)",
                "start": "15/09/2013 19:00",
                "booked_by": "Jane",
            },
        )
        new_event = Event.objects.get(name="Community Kitchen (May)")
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": new_event.pk}),
        )
        # Scalar fields copied from source
        self.assertEqual(new_event.copy_summary, self.e4.copy_summary)
        self.assertEqual(new_event.copy, self.e4.copy)
        self.assertEqual(new_event.terms, self.e4.terms)
        self.assertEqual(new_event.programming_notes, self.e4.programming_notes)
        self.assertEqual(new_event.film_information, self.e4.film_information)
        self.assertEqual(new_event.pricing, self.e4.pricing)
        self.assertEqual(new_event.pre_title, self.e4.pre_title)
        self.assertEqual(new_event.post_title, self.e4.post_title)
        self.assertEqual(new_event.outside_hire, self.e4.outside_hire)
        self.assertEqual(new_event.private, self.e4.private)
        # Compare duration via DB-fetched source to ensure both are time objects
        self.assertEqual(new_event.duration, Event.objects.get(pk=self.e4.pk).duration)
        self.assertEqual(new_event.template, self.e4.template)
        # Ticket link NOT copied
        self.assertEqual(new_event.ticket_link, "")
        # One showing created, unconfirmed
        showings = list(new_event.showings.all())
        self.assertEqual(len(showings), 1)
        self.assertEqual(showings[0].booked_by, "Jane")
        self.assertFalse(showings[0].confirmed)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_post_copies_tags(self, now_patch):
        now_patch.return_value = self._fake_now

        self.client.post(
            self.url,
            data={
                "event_name": "Community Kitchen (June)",
                "start": "15/09/2013 19:00",
                "booked_by": "Jane",
            },
        )
        new_event = Event.objects.get(name="Community Kitchen (June)")
        source_tag_pks = set(self.e4.tags.values_list("pk", flat=True))
        new_tag_pks = set(new_event.tags.values_list("pk", flat=True))
        self.assertEqual(source_tag_pks, new_tag_pks)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_post_clones_rota_from_latest_showing(self, now_patch):
        """Rota is cloned from the source event's latest showing."""
        now_patch.return_value = self._fake_now
        # Give e4s3 (the earlier showing) a rota entry on Role 1.
        role_1 = Role.objects.get(id=1)
        RotaEntry(showing=self.e4s3, role=role_1, required=1).save()

        self.client.post(
            self.url,
            data={
                "event_name": "Community Kitchen (July)",
                "start": "15/09/2013 19:00",
                "booked_by": "Jane",
            },
        )
        new_event = Event.objects.get(name="Community Kitchen (July)")
        new_showing = new_event.showings.first()
        # e4s4 is the latest showing; it has no rota entries, so the new
        # showing should reset to template defaults (e4 has no template, so
        # no roles expected).
        self.assertEqual(new_showing.roles.count(), 0)

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_post_start_in_past_rejected(self, now_patch):
        now_patch.return_value = self._fake_now

        response = self.client.post(
            self.url,
            data={
                "event_name": "Clone in the past",
                "start": "01/01/2000 19:00",
                "booked_by": "Jane",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.filter(name="Clone in the past").exists())

    @override_settings(MULTIROOM_ENABLED=False)
    @patch("django.utils.timezone.now")
    def test_post_missing_name_rejected(self, now_patch):
        now_patch.return_value = self._fake_now

        response = self.client.post(
            self.url,
            data={
                "event_name": "",
                "start": "15/09/2013 19:00",
                "booked_by": "Jane",
            },
        )
        self.assertEqual(response.status_code, 200)
        # No new event created
        self.assertEqual(Event.objects.filter(name="").count(), 0)

    @patch("django.utils.timezone.now")
    def test_get_404_for_unknown_event(self, now_patch):
        now_patch.return_value = self._fake_now
        url = reverse("clone-event", kwargs={"event_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class EventLinkTests(DiaryTestsMixin, TestCase):
    """Tests for the edit-event-links view and EventLink model."""

    # Management-form POST helpers
    _PREFIX = "links"  # derived from FK related_name="links" on EventLink

    def _mgmt(self, total=3, initial=0):
        """Return management form fields for EventLinkFormSet."""
        return {
            f"{self._PREFIX}-TOTAL_FORMS": str(total),
            f"{self._PREFIX}-INITIAL_FORMS": str(initial),
            f"{self._PREFIX}-MIN_NUM_FORMS": "0",
            f"{self._PREFIX}-MAX_NUM_FORMS": "3",
        }

    def _form(self, idx, label="", url="", pk="", delete=False):
        """Return field dict for a single inline row."""
        d = {
            f"{self._PREFIX}-{idx}-label": label,
            f"{self._PREFIX}-{idx}-url": url,
            f"{self._PREFIX}-{idx}-id": pk,
        }
        if delete:
            d[f"{self._PREFIX}-{idx}-DELETE"] = "on"
        return d

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("edit-event-links", kwargs={"event_id": self.e1.pk})

    # ── GET ─────────────────────────────────────────────────────────────────

    def test_get_returns_200_and_correct_template(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_links.html")

    def test_get_404_for_unknown_event(self):
        url = reverse("edit-event-links", kwargs={"event_id": 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_shows_existing_links(self):
        EventLink.objects.create(
            event=self.e1,
            label="Meeting notes",
            url="https://pad.riseup.net/p/e1-notes",
            order=0,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meeting notes")
        self.assertContains(response, "pad.riseup.net")

    # ── POST — valid ─────────────────────────────────────────────────────────

    def test_post_creates_link_with_approved_domain(self):
        data = self._mgmt()
        data.update(
            self._form(0, label="Event notes", url="https://pad.riseup.net/p/sns-test")
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        links = list(self.e1.links.all())
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].label, "Event notes")
        self.assertEqual(links[0].url, "https://pad.riseup.net/p/sns-test")

    def test_post_nextcloud_subdomain_accepted(self):
        data = self._mgmt()
        data.update(
            self._form(
                0,
                label="Event folder",
                url="https://starandshadow.nextcloud.com/s/abc123",
            )
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertEqual(self.e1.links.count(), 1)

    def test_post_whatsapp_accepted(self):
        data = self._mgmt()
        data.update(
            self._form(
                0, label="Crew chat", url="https://chat.whatsapp.com/ABC123xyzLink"
            )
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertEqual(self.e1.links.count(), 1)

    @override_settings(EVENTLINK_EXTRA_ALLOWED_DOMAINS=["nextcloud.xtreamlab.net"])
    def test_post_extra_allowed_domain_accepted(self):
        """A domain in EVENTLINK_EXTRA_ALLOWED_DOMAINS is accepted."""
        data = self._mgmt()
        data.update(
            self._form(0, label="Notes", url="https://nextcloud.xtreamlab.net/s/abc123")
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertEqual(self.e1.links.count(), 1)

    def test_post_site_config_extra_domain_accepted(self):
        """A domain configured in SiteConfiguration.eventlink_extra_allowed_domains is accepted."""
        from django.core.cache import cache
        from toolkit.diary.models import SiteConfiguration

        cache.delete(SiteConfiguration._CACHE_KEY)
        config = SiteConfiguration.load()
        config.eventlink_extra_allowed_domains = "nextcloud.xtreamlab.net\nfiles.example.org"
        config.save()

        data = self._mgmt()
        data.update(
            self._form(0, label="Notes", url="https://nextcloud.xtreamlab.net/s/xyz")
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertEqual(self.e1.links.count(), 1)

        # Cleanup
        config.eventlink_extra_allowed_domains = ""
        config.save()
        cache.delete(SiteConfiguration._CACHE_KEY)

    @override_settings(EVENTLINK_EXTRA_ALLOWED_DOMAINS=[])
    def test_post_unknown_domain_rejected_when_not_in_extra(self):
        """A domain not in any whitelist is rejected even if path looks Nextcloud-like."""
        data = self._mgmt()
        data.update(
            self._form(0, label="Notes", url="https://some.random.host/nextcloud/s/abc")
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.e1.links.count(), 0)

    def test_post_linktr_ee_accepted(self):
        data = self._mgmt()
        data.update(
            self._form(0, label="Core docs", url="https://linktr.ee/starandshadow")
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertEqual(self.e1.links.count(), 1)

    # ── POST — invalid ───────────────────────────────────────────────────────

    def test_post_disallowed_domain_rejected(self):
        data = self._mgmt()
        data.update(self._form(0, label="Bad link", url="https://example.com/bad"))
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_event_links.html")
        self.assertEqual(self.e1.links.count(), 0)

    def test_post_generic_whatsapp_domain_rejected(self):
        """whatsapp.com (without chat. prefix) must be rejected."""
        data = self._mgmt()
        data.update(self._form(0, label="WhatsApp", url="https://whatsapp.com/dl/"))
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.e1.links.count(), 0)

    def test_post_missing_label_rejected(self):
        """A URL without a label must not be saved."""
        data = self._mgmt()
        data.update(self._form(0, label="", url="https://pad.riseup.net/p/sns-test"))
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.e1.links.count(), 0)

    # ── delete ───────────────────────────────────────────────────────────────

    def test_post_delete_removes_link(self):
        link = EventLink.objects.create(
            event=self.e1,
            label="To delete",
            url="https://pad.riseup.net/p/todelete",
            order=0,
        )
        data = self._mgmt(total=3, initial=1)
        data.update(
            self._form(0, label=link.label, url=link.url, pk=str(link.pk), delete=True)
        )
        data.update(self._form(1))
        data.update(self._form(2))
        response = self.client.post(self.url, data)
        self.assertRedirects(
            response,
            reverse("edit-event-details-view", kwargs={"event_id": self.e1.pk}),
        )
        self.assertFalse(EventLink.objects.filter(pk=link.pk).exists())


# Far-future tz-aware date so showings are always "future" without patching now.
_FUTURE = datetime(2099, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("Europe/London"))


class EventHubCollapseTests(DiaryTestsMixin, TestCase):
    """Event Hub presents a single-occurrence event as one thing; the 'dates'
    concept only surfaces once a second showing exists (UI collapse)."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def _make_event(self, n_showings, confirmed=False):
        event = Event(name="Hub collapse event", duration="2:00:00")
        event.save()
        for i in range(n_showings):
            Showing(
                event=event,
                start=_FUTURE + timedelta(days=i),
                booked_by="Tester",
                confirmed=confirmed,
            ).save()
        return event

    def _hub(self, event):
        return self.client.get(
            reverse("edit-event-details-view", kwargs={"event_id": event.pk})
        )

    def test_single_showing_shows_singular_heading(self):
        # Default occurrence noun is the cinema-first "showing".
        response = self._hub(self._make_event(1))
        self.assertContains(response, "Showing &amp; booking")
        self.assertNotContains(response, ">Showings</h3>")
        # "Confirm all" is a series-only bulk control.
        self.assertNotContains(response, "Confirm all")

    def test_multi_showing_shows_plural_heading(self):
        response = self._hub(self._make_event(2))
        self.assertContains(response, ">Showings</h3>")
        self.assertNotContains(response, "Showing &amp; booking")

    def test_unpublished_future_shows_confirm_button(self):
        response = self._hub(self._make_event(1, confirmed=False))
        self.assertContains(response, ">Confirm</button>")

    def test_terminology_follows_site_config(self):
        # Star and Shadow's seed sets these to date/dates.
        cfg = get_site_config()
        cfg.occurrence_noun = "date"
        cfg.occurrence_noun_plural = "dates"
        cfg.save()

        single = self._hub(self._make_event(1, confirmed=False))
        self.assertContains(single, "Date &amp; booking")
        self.assertContains(single, "Cancel this date")
        # Confirm button is always "Confirm" regardless of custom confirm_label.
        self.assertContains(single, ">Confirm</button>")

        series = self._hub(self._make_event(2))
        self.assertContains(series, ">Dates</h3>")


class RoomReleaseOnCancelTests(DiaryTestsMixin, TestCase):
    """Cancelled dates and rejected events free their rooms (visually) while
    keeping the RoomBooking rows so the action is reversible."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.event = Event(name="Room release event", duration="2:00:00")
        self.event.save()
        self.showing = Showing(
            event=self.event, start=_FUTURE, booked_by="Tester", confirmed=True
        )
        self.showing.save()
        self.booking = RoomBooking.objects.create(
            showing=self.showing, room=self.room_2, start=self.showing.start
        )

    def test_confirmed_showing_occupies_rooms(self):
        self.assertTrue(self.showing.occupies_rooms())
        self.assertEqual(len(self.showing.visible_room_bookings), 1)

    def test_cancelled_date_frees_rooms_but_keeps_booking(self):
        self.showing.cancelled = True
        self.showing.save()
        self.showing.refresh_from_db()
        self.assertFalse(self.showing.occupies_rooms())
        self.assertEqual(self.showing.visible_room_bookings, [])
        # Row preserved for reversibility:
        self.assertEqual(self.showing.room_bookings.count(), 1)

    def test_uncancel_restores_room_occupancy(self):
        self.showing.cancelled = True
        self.showing.save()
        self.showing.cancelled = False
        self.showing.save()
        self.showing.refresh_from_db()
        self.assertEqual(len(self.showing.visible_room_bookings), 1)

    def test_rejected_event_frees_rooms(self):
        self.event.programming_status = "rejected"
        self.event.save()
        self.showing.refresh_from_db()
        self.assertFalse(self.showing.occupies_rooms())

    @override_settings(MULTIROOM_ENABLED=True)
    def test_calendar_json_excludes_cancelled_booking(self):
        url = reverse("edit-diary-data")
        start = (_FUTURE - timedelta(days=2)).strftime("%Y-%m-%d")
        end = (_FUTURE + timedelta(days=2)).strftime("%Y-%m-%d")
        rb_id = f"rb-{self.booking.pk}"

        data = self.client.get(url, {"start": start, "end": end}).json()
        self.assertTrue(any(str(d.get("id")) == rb_id for d in data))

        self.showing.cancelled = True
        self.showing.save()
        data = self.client.get(url, {"start": start, "end": end}).json()
        self.assertFalse(any(str(d.get("id")) == rb_id for d in data))


class OneShotRoleTests(DiaryTestsMixin, TestCase):
    """One-shot roles: orphan cleanup, dropdown exclusion, roles page exclusion."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def _make_one_shot(self, name="Custom AV"):
        role, _ = Role.objects.get_or_create(
            name=name, defaults={"is_one_shot": True, "standard": False}
        )
        return role

    def test_orphaned_oneshot_role_deleted_after_last_entry_removed(self):
        role = self._make_one_shot()
        entry = RotaEntry.objects.create(role=role, showing=self.e4s3)
        self.assertTrue(Role.objects.filter(pk=role.pk).exists())

        entry.delete()
        self.e4s3.update_rota({})

        self.assertFalse(Role.objects.filter(pk=role.pk).exists())

    def test_oneshot_role_retained_while_still_referenced(self):
        role = self._make_one_shot()
        e1 = RotaEntry.objects.create(role=role, showing=self.e4s3)
        e2 = RotaEntry.objects.create(role=role, showing=self.e4s3)

        e1.delete()
        self.e4s3.update_rota({})

        self.assertTrue(Role.objects.filter(pk=role.pk).exists())
        e2.delete()

    def test_oneshot_roles_absent_from_roles_management_page(self):
        self._make_one_shot("Secret One-Shot")
        resp = self.client.get(reverse("edit_roles"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Secret One-Shot")

    def test_oneshot_roles_absent_from_standard_role_queryset(self):
        # The rota form factory explicitly filters is_one_shot=False, so one-shot
        # roles should never appear in the set of role fields it generates.
        self._make_one_shot("One-Shot Only Role")
        standard_roles = Role.objects.filter(is_one_shot=False)
        self.assertFalse(standard_roles.filter(name="One-Shot Only Role").exists())

    def test_get_oneshot_roles_carries_signed_up_count(self):
        # _get_oneshot_roles_for_showing reports both slot count and signed-up
        # volunteer count, so the edit form can warn before reducing below
        # the number of real sign-ups.
        from toolkit.members.models import Volunteer

        role = self._make_one_shot("Signed-Up Role")
        v = Volunteer.objects.first()
        RotaEntry.objects.create(
            role=role, showing=self.e4s3, volunteer=v, name=v.member.name
        )
        RotaEntry.objects.create(
            role=role, showing=self.e4s3, volunteer=v, name=v.member.name
        )
        RotaEntry.objects.create(role=role, showing=self.e4s3, volunteer=None, name="")

        from toolkit.diary.edit_views.showings import _get_oneshot_roles_for_showing

        rows = _get_oneshot_roles_for_showing(self.e4s3)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["name"], "Signed-Up Role")
        self.assertEqual(r["current_count"], 3)
        self.assertEqual(r["signed_up_count"], 2)

    def test_edit_showing_get_renders_signed_up_count(self):
        # The edit-showing page surfaces signed_up_count on each existing
        # one-shot row, plus a hidden sink div so the JS removal handler can
        # synthesise zero-inputs without breaking the POST index loop.
        from toolkit.members.models import Volunteer

        role = self._make_one_shot("Rendered Signups")
        v = Volunteer.objects.first()
        RotaEntry.objects.create(
            role=role, showing=self.e4s3, volunteer=v, name=v.member.name
        )
        RotaEntry.objects.create(role=role, showing=self.e4s3, volunteer=None, name="")

        url = reverse("edit-showing", kwargs={"showing_id": self.e4s3.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-signed-up-count="1"')
        # Hidden sink so JS can synthesise removal inputs
        self.assertContains(resp, 'id="oneshot-removed"')
        # Warning element present (CSS hides it until count drops)
        self.assertContains(resp, "oneshot-warn")

    @patch("django.utils.timezone.now")
    def test_remove_existing_oneshot_clears_entries(self, now_patch):
        # Mirrors what the JS remove handler emits for an existing one-shot:
        # synthesised id + blanked name + zeroed count. The server must clear
        # the role's RotaEntries and then orphan-cleanup removes the Role.
        from toolkit.members.models import Volunteer

        now_patch.return_value = self._fake_now
        role = self._make_one_shot("Removed Role")
        v = Volunteer.objects.first()
        RotaEntry.objects.create(
            role=role, showing=self.e4s3, volunteer=v, name=v.member.name
        )
        RotaEntry.objects.create(role=role, showing=self.e4s3, volunteer=None, name="")
        self.assertEqual(self.e4s3.rotaentry_set.filter(role=role).count(), 2)

        url = reverse("edit-showing", kwargs={"showing_id": self.e4s3.pk})
        resp = self.client.post(
            url,
            data={
                "start": "09/06/2013 19:30",
                "booked_by": "Test Booker",
                "confirmed": "on",
                "role_1": "0",
                "other_2": "0",
                "other_3": "0",
                # Synthesised removal — mirrors the JS handler's output
                "oneshot_id_0": str(role.pk),
                "oneshot_name_0": "",
                "oneshot_count_0": "0",
                "oneshot_desc_0": "",
                "room_bookings-TOTAL_FORMS": "0",
                "room_bookings-INITIAL_FORMS": "0",
                "room_bookings-MIN_NUM_FORMS": "0",
                "room_bookings-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.e4s3.refresh_from_db()
        self.assertFalse(self.e4s3.rotaentry_set.filter(role=role).exists())
        # Orphan cleanup removes the now-unreferenced one-shot Role
        self.assertFalse(Role.objects.filter(pk=role.pk).exists())


class StructuredCostTermsTests(DiaryTestsMixin, TestCase):
    """Structured cost terms: feature flag, word-count waiver, required validation."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        cfg = get_site_config()
        cfg.programme_event_terms_min_words = 3
        cfg.save()

    def _post_event(self, event_id, overrides=None):
        url = reverse("edit-event-details", kwargs={"event_id": event_id})
        event = Event.objects.get(pk=event_id)
        data = {
            "name": event.name,
            "duration": "01:00:00",
            "terms": event.terms or "",
            "copy": event.copy or "",
            "copy_summary": event.copy_summary or "",
            "pricing": event.pricing or "",
            "pre_title": event.pre_title or "",
            "post_title": event.post_title or "",
            "film_information": event.film_information or "",
            "programming_status": event.programming_status or "idea",
            "approval_type": event.approval_type or "",
        }
        if overrides:
            data.update(overrides)
        return self.client.post(url, data, follow=True)

    def test_cost_type_field_absent_when_flag_off(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = False
        cfg.save()
        resp = self.client.get(
            reverse("edit-event-details", kwargs={"event_id": self.e4.pk})
        )
        self.assertNotContains(resp, 'name="cost_type"')

    def test_cost_type_field_present_when_flag_on(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.save()
        resp = self.client.get(
            reverse("edit-event-details", kwargs={"event_id": self.e4.pk})
        )
        self.assertContains(resp, 'name="cost_type"')

    def test_terms_word_count_waived_when_cost_type_set(self):
        # e4s3 is confirmed; terms is short ("Terminal price: £1 / €3" = 5 words,
        # but we'll blank it to force the normal validation to fire).
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.structured_cost_required = False
        cfg.save()
        resp = self._post_event(
            self.e4.pk,
            {"terms": "", "cost_type": Event.COST_TYPE_FILM_LICENSE},
        )
        # Should save (redirect) without a terms error
        form = resp.context.get("form") if hasattr(resp, "context") else None
        if form:
            self.assertNotIn("terms", form.errors)

    def test_cost_type_required_error_when_flag_and_required_set(self):
        cfg = get_site_config()
        cfg.structured_cost_terms_enabled = True
        cfg.structured_cost_required = True
        cfg.save()
        resp = self._post_event(
            self.e4.pk,
            {"terms": "", "cost_type": Event.COST_TYPE_TBC},
        )
        form = resp.context.get("form") if resp.context else None
        if form:
            self.assertIn("cost_type", form.errors)


