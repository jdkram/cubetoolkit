import os.path

from datetime import date

from django.core.files.base import ContentFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from toolkit.diary.models import PrintedProgramme, get_site_config
from .common import DiaryTestsMixin


class PrintedProgrammeGalleryViewTests(TestCase):
    def _enable_gallery(self):
        config = get_site_config()
        config.printed_programme_archive_enabled = True
        config.save()

    def test_gallery_disabled_by_default(self):
        # Off by default — not publicly reachable until a superuser opts in
        # via SiteConfiguration.
        response = self.client.get(reverse("printed-programme-archive"))
        self.assertEqual(response.status_code, 404)

    def test_gallery_view_loads_no_data(self):
        self._enable_gallery()
        response = self.client.get(reverse("printed-programme-archive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No printed programmes")

    def test_gallery_view_shows_seasons(self):
        self._enable_gallery()
        PrintedProgramme(
            start_month=date(2025, 2, 1),
            end_month=date(2025, 4, 1),
            designer="Ada Lovelace",
            programme="printedprogramme/spring25.pdf",
        ).save()

        response = self.client.get(reverse("printed-programme-archive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring 2025 · Feb–Apr")
        self.assertContains(response, "Ada Lovelace")

    def test_gallery_view_placeholder_when_no_thumbnail(self):
        self._enable_gallery()
        PrintedProgramme(
            start_month=date(2025, 2, 1),
            end_month=date(2025, 2, 1),
            programme="printedprogramme/nothumb.pdf",
        ).save()

        response = self.client.get(reverse("printed-programme-archive"))
        self.assertContains(response, "thumb-placeholder")


class PrintedProgrammeNavLinkTests(DiaryTestsMixin, TestCase):
    def _enable_gallery(self):
        config = get_site_config()
        config.printed_programme_archive_enabled = True
        config.save()

    def test_nav_link_hidden_by_default(self):
        response = self.client.get(reverse("default-view"))
        self.assertNotContains(response, "Printed programme archive")

    def test_nav_link_shown_when_enabled(self):
        self._enable_gallery()
        response = self.client.get(reverse("default-view"))
        self.assertContains(response, "Printed programme archive")
        self.assertContains(
            response, reverse("printed-programme-archive")
        )


class PrintedProgrammeThumbnailGenerationTests(TestCase):
    @override_settings(MEDIA_ROOT="/tmp")
    def test_invalid_pdf_skips_thumbnail_without_error(self):
        # Not a real PDF - poppler will fail to render it. Saving must not
        # raise, and the entry should be left without a thumbnail.
        pp = PrintedProgramme(
            start_month=date(2025, 2, 1),
            end_month=date(2025, 2, 1),
        )
        pp.programme.save(
            "toolkit-test-not-a-pdf.pdf",
            ContentFile(b"not actually a pdf"),
            save=False,
        )
        pp.save()

        uploaded_path = os.path.join("/tmp", pp.programme.name)

        try:
            self.assertFalse(pp.thumbnail)
        finally:
            try:
                os.unlink(uploaded_path)
            except OSError:
                pass
