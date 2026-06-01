# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Tests for file/image uploads in Labs views.

Covers ExchangeItem and FoundItem photo uploads. Uses MEDIA_ROOT=/tmp (set in
test_settings.py) so the container's /site/media/ directory is never touched.
Files written to /tmp are cleaned up in tearDown.

The TINY_VALID_JPEG constant is a minimal 1x1-pixel JPEG that passes Django's
ImageField content validation (which uses Pillow under the hood).
"""
import datetime
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import ExchangeItem, FoundItem
from .common import LabsTestsMixin


# Minimal 1x1-pixel JPEG — passes Pillow's image-format check.
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


def _jpeg(name="test.jpg"):
    return SimpleUploadedFile(name, TINY_VALID_JPEG, content_type="image/jpeg")


def _cleanup_media_file(field):
    """Delete a model's ImageField file if it was written to disk."""
    if field and field.name:
        try:
            field.delete(save=False)
        except Exception:
            pass


# ── Community exchange photo uploads ─────────────────────────────────────────

class ExchangePhotoAddTests(LabsTestsMixin, TestCase):
    """Adding an exchange listing with a photo attached."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self._uploaded_files = []

    def tearDown(self):
        for f in self._uploaded_files:
            _cleanup_media_file(f)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_add_item_with_photo_saves_image(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-exchange-add"), {
            "listing_type": ExchangeItem.TYPE_GIVE,
            "name": "Photo upload test item",
            "description": "Testing photo upload",
            "category": ExchangeItem.CATEGORY_OTHER,
            "condition": ExchangeItem.CONDITION_GOOD,
            "owner_type": ExchangeItem.OWNER_VOLUNTEER,
            "owner_volunteer": self.vol.pk,
            "location_notes": "",
            "status": ExchangeItem.STATUS_AVAILABLE,
            "notes": "",
            "image": _jpeg("exchange-test.jpg"),
        })
        self.assertEqual(response.status_code, 302)

        item = ExchangeItem.objects.get(name="Photo upload test item")
        self._uploaded_files.append(item.image)
        self.assertTrue(item.image.name, "image field should be set")
        self.assertIn("exchange/", item.image.name)
        self.assertTrue(
            os.path.exists(item.image.path),
            f"Uploaded file should exist at {item.image.path}",
        )

    @override_settings(MEDIA_ROOT="/tmp")
    def test_add_item_without_photo_succeeds(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-exchange-add"), {
            "listing_type": ExchangeItem.TYPE_GIVE,
            "name": "No photo item",
            "description": "",
            "category": ExchangeItem.CATEGORY_OTHER,
            "condition": ExchangeItem.CONDITION_GOOD,
            "owner_type": ExchangeItem.OWNER_VOLUNTEER,
            "owner_volunteer": self.vol.pk,
            "location_notes": "",
            "status": ExchangeItem.STATUS_AVAILABLE,
            "notes": "",
        })
        self.assertEqual(response.status_code, 302)
        item = ExchangeItem.objects.get(name="No photo item")
        self.assertFalse(item.image.name)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_add_item_with_non_image_rejected(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        not_an_image = SimpleUploadedFile("test.jpg", b"not image data", content_type="image/jpeg")
        response = self.client.post(reverse("labs-exchange-add"), {
            "listing_type": ExchangeItem.TYPE_GIVE,
            "name": "Bad file item",
            "description": "",
            "category": ExchangeItem.CATEGORY_OTHER,
            "condition": ExchangeItem.CONDITION_GOOD,
            "owner_type": ExchangeItem.OWNER_VOLUNTEER,
            "owner_volunteer": self.vol.pk,
            "location_notes": "",
            "status": ExchangeItem.STATUS_AVAILABLE,
            "notes": "",
            "image": not_an_image,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ExchangeItem.objects.filter(name="Bad file item").exists())


class ExchangePhotoEditTests(LabsTestsMixin, TestCase):
    """Editing an exchange listing to add / replace a photo."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self.item = ExchangeItem.objects.create(
            name="Editable item",
            listing_type=ExchangeItem.TYPE_GIVE,
            category=ExchangeItem.CATEGORY_OTHER,
            condition=ExchangeItem.CONDITION_GOOD,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
            added_by=self.user_vol,
        )
        self._uploaded_files = []

    def tearDown(self):
        for f in self._uploaded_files:
            _cleanup_media_file(f)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_edit_adds_photo(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(
            reverse("labs-exchange-edit", kwargs={"item_id": self.item.pk}),
            {
                "listing_type": ExchangeItem.TYPE_GIVE,
                "name": "Editable item",
                "description": "Now with a photo",
                "category": ExchangeItem.CATEGORY_OTHER,
                "condition": ExchangeItem.CONDITION_GOOD,
                "owner_type": ExchangeItem.OWNER_VOLUNTEER,
                "owner_volunteer": self.vol.pk,
                "location_notes": "",
                "status": ExchangeItem.STATUS_AVAILABLE,
                "notes": "",
                "image": _jpeg("exchange-edit-test.jpg"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self._uploaded_files.append(self.item.image)
        self.assertTrue(self.item.image.name)
        self.assertIn("exchange/", self.item.image.name)
        self.assertTrue(os.path.exists(self.item.image.path))


# ── Lost & found photo uploads ────────────────────────────────────────────────

class FoundItemPhotoTests(LabsTestsMixin, TestCase):
    """Logging a found item with and without an attached photo."""

    def setUp(self):
        super().setUp()
        self._uploaded_files = []

    def tearDown(self):
        for f in self._uploaded_files:
            _cleanup_media_file(f)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_log_found_item_with_photo(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-found-item-log"), {
            "report_type": FoundItem.TYPE_FOUND,
            "description": "Blue umbrella",
            "location_found": "Café",
            "found_on": datetime.date.today().isoformat(),
            "logged_by": "Test Volunteer",
            "photo": _jpeg("laf-test.jpg"),
        })
        self.assertEqual(response.status_code, 302)

        item = FoundItem.objects.get(description="Blue umbrella")
        self._uploaded_files.append(item.photo)
        self.assertTrue(item.photo.name)
        self.assertIn("lost-and-found/", item.photo.name)
        self.assertTrue(
            os.path.exists(item.photo.path),
            f"Uploaded photo should exist at {item.photo.path}",
        )

    @override_settings(MEDIA_ROOT="/tmp")
    def test_log_found_item_without_photo_succeeds(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-found-item-log"), {
            "report_type": FoundItem.TYPE_FOUND,
            "description": "Red scarf",
            "location_found": "Cinema",
            "found_on": datetime.date.today().isoformat(),
            "logged_by": "Test Volunteer",
        })
        self.assertEqual(response.status_code, 302)
        item = FoundItem.objects.get(description="Red scarf")
        self.assertFalse(item.photo.name)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_log_lost_report_with_photo(self):
        """Reporter can attach a photo of the lost item to aid identification."""
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-found-item-log"), {
            "report_type": FoundItem.TYPE_LOST,
            "description": "Black leather wallet",
            "location_found": "Unknown",
            "found_on": datetime.date.today().isoformat(),
            "logged_by": "Worried Person",
            "reporter_contact": "worried@example.com",
            "photo": _jpeg("wallet.jpg"),
        })
        self.assertEqual(response.status_code, 302)
        item = FoundItem.objects.get(description="Black leather wallet")
        self._uploaded_files.append(item.photo)
        self.assertTrue(item.photo.name)
        self.assertTrue(os.path.exists(item.photo.path))


# ── Anonymous access ──────────────────────────────────────────────────────────

class PhotoUploadAnonTests(LabsTestsMixin, TestCase):
    """Unauthenticated users cannot reach any upload endpoint."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()

    def test_anon_cannot_add_exchange_item(self):
        response = self.client.post(reverse("labs-exchange-add"), {})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_anon_cannot_log_found_item(self):
        response = self.client.post(reverse("labs-found-item-log"), {})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])
