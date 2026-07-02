import os.path

from datetime import date
import tempfile

from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from toolkit.diary.models import PrintedProgramme

from .common import DiaryTestsMixin


class AddPrintedProgrammeTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.test_upload = None

    def tearDown(self):
        self.client.logout()
        try:
            if self.test_upload:
                os.unlink(self.test_upload)
        except OSError:
            pass

    def _write_pdf_magic(self, temp_pdf):
        temp_pdf.write(b"%PDF-1.3\r%\xe2\xe3\xcf\xd3\r\n")
        temp_pdf.seek(0)

    def test_view_loads(self):
        url = reverse("add-printed-programme")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_add_progamme_invalid_no_file(self):
        url = reverse("add-printed-programme")

        response = self.client.post(
            url,
            data={
                "start_form_month": "1",
                "start_year": "2010",
                "end_form_month": "1",
                "end_year": "2010",
                "designer": "Designer name",
                "notes": "Blah blah notes",
                "programme": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_printedprogramme_archive.html")
        self.assertFormError(
            response.context["new_programme_form"],
            "programme",
            "This field is required.",
        )
        self.assertEqual(PrintedProgramme.objects.count(), 0)

    def test_add_progamme_invalid_file_empty(self):
        url = reverse("add-printed-programme")

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-programme-", suffix=".pdf"
        ) as temp_pdf:
            response = self.client.post(
                url,
                data={
                    "start_form_month": "1",
                    "start_year": "2010",
                    "end_form_month": "1",
                    "end_year": "2010",
                    "designer": "Designer name",
                    "notes": "Blah blah notes",
                    "programme": temp_pdf,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_printedprogramme_archive.html")
        self.assertFormError(
            response.context["new_programme_form"],
            "programme",
            "The submitted file is empty.",
        )
        self.assertEqual(PrintedProgramme.objects.count(), 0)

    def test_add_progamme_invalid_end_before_start(self):
        url = reverse("add-printed-programme")

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-programme-", suffix=".pdf"
        ) as temp_pdf:
            self._write_pdf_magic(temp_pdf)
            response = self.client.post(
                url,
                data={
                    "start_form_month": "6",
                    "start_year": "2010",
                    "end_form_month": "3",
                    "end_year": "2010",
                    "designer": "Designer name",
                    "notes": "Blah blah notes",
                    "programme": temp_pdf,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_printedprogramme_archive.html")
        self.assertFormError(
            response.context["new_programme_form"],
            "end_form_month",
            "End month must not be before start month.",
        )
        self.assertEqual(PrintedProgramme.objects.count(), 0)

    def test_add_progamme_invalid_overlapping_season(self):
        # Add season covering Dec 1998 - Feb 1999
        PrintedProgramme(
            start_month=date(1998, 12, 1),
            end_month=date(1999, 2, 1),
            designer="What?",
            programme="fake/fake",
        ).save()
        url = reverse("add-printed-programme")

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-programme-", suffix=".pdf"
        ) as temp_pdf:
            self._write_pdf_magic(temp_pdf)
            response = self.client.post(
                url,
                data={
                    "start_form_month": "1",
                    "start_year": "1999",
                    "end_form_month": "1",
                    "end_year": "1999",
                    "designer": "Designer name",
                    "notes": "Blah blah notes",
                    "programme": temp_pdf,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_printedprogramme_archive.html")
        self.assertFormError(
            response.context["new_programme_form"],
            None,
            "This date range overlaps with an existing printed "
            "programme entry.",
        )
        # No more objects should have been added:
        self.assertEqual(PrintedProgramme.objects.count(), 1)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_add_progamme(self):
        self.assertEqual(PrintedProgramme.objects.count(), 0)

        url = reverse("add-printed-programme")

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-programme-", suffix=".pdf"
        ) as temp_pdf:
            self._write_pdf_magic(temp_pdf)
            response = self.client.post(
                url,
                data={
                    "start_form_month": "4",
                    "start_year": "2010",
                    "end_form_month": "6",
                    "end_year": "2010",
                    "designer": "Designer namę",
                    "notes": "Blah blah noŧes",
                    "programme": temp_pdf,
                },
            )
            filename = os.path.basename(temp_pdf.name)
        self.assertRedirects(response, reverse("edit-printed-programmes"))
        # Check file upload:
        expected_upload = os.path.join("printedprogramme", filename)
        self.test_upload = os.path.join("/tmp", expected_upload)

        self.assertTrue(os.path.isfile(self.test_upload))

        # Check item was added:
        self.assertEqual(PrintedProgramme.objects.count(), 1)
        pp = PrintedProgramme.objects.all()[0]
        self.assertEqual(pp.start_month, date(2010, 4, 1))
        self.assertEqual(pp.end_month, date(2010, 6, 1))
        self.assertEqual(pp.designer, "Designer namę")
        self.assertEqual(pp.notes, "Blah blah noŧes")
        self.assertEqual(pp.programme.name, expected_upload)


class EditPrintedProgrammeTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.test_upload = None
        self._add_data()

    def tearDown(self):
        self.client.logout()
        try:
            if self.test_upload:
                os.unlink(self.test_upload)
        except OSError:
            pass

    def _write_pdf_magic(self, temp_pdf):
        temp_pdf.write("%PDF-1.3\r%\xe2\xe3\xcf\xd3\r\n")
        temp_pdf.seek(0)

    def _add_data(self):
        PrintedProgramme(
            start_month=date(2010, 6, 1),
            end_month=date(2010, 6, 1),
            designer="Loop lop loop",
            programme="/foo/bar",
        ).save()
        PrintedProgramme(
            start_month=date(2010, 7, 1),
            end_month=date(2010, 8, 1),
            designer="Can be yours for €10",
            programme="/what/bar/Nun",
        ).save()

    def test_edit_view_loads_no_data(self):
        PrintedProgramme.objects.all().delete()
        url = reverse("edit-printed-programmes")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_edit_view_loads_with_data(self):
        url = reverse("edit-printed-programmes")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Loop lop loop")
        self.assertContains(response, "Can be yours for €10")

    def test_edit_view_edit_data(self):
        url = reverse("edit-printed-programmes")
        response = self.client.post(
            url,
            data={
                "form-TOTAL_FORMS": "2",
                "form-INITIAL_FORMS": "2",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-start_form_month": "7",
                "form-0-start_year": "2010",
                "form-0-end_form_month": "8",
                "form-0-end_year": "2010",
                # "form-0-programme": "",
                "form-0-designer": "Someonē",
                "form-0-notes": "",
                "form-0-id": "2",
                "form-1-start_form_month": "6",
                "form-1-start_year": "2010",
                "form-1-end_form_month": "6",
                "form-1-end_year": "2010",
                # "form-1-programme": "",
                # "form-1-designer": "Socks",
                "form-1-notes": "Sm€lt TERRIBLE",
                "form-1-id": "1",
            },
        )
        self.assertRedirects(response, reverse("edit-printed-programmes"))
        # Check edits saved
        pp1 = PrintedProgramme.objects.get(pk=1)
        self.assertEqual(pp1.notes, "Sm€lt TERRIBLE")
        self.assertEqual(pp1.designer, "")
        self.assertEqual(pp1.programme, "/foo/bar")

        pp2 = PrintedProgramme.objects.get(pk=2)
        self.assertEqual(pp2.notes, "")
        self.assertEqual(pp2.designer, "Someonē")
        self.assertEqual(pp2.programme, "/what/bar/Nun")
