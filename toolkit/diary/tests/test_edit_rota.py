from datetime import timedelta, datetime

import zoneinfo
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import RotaEntry, Showing, get_site_config
from toolkit.members.models import Member

from .common import DiaryTestsMixin


def _grant_rota_permission(user):
    ct = ContentType.objects.get(app_label="diary", model="rotaentry")
    perm = Permission.objects.get(codename="change_rotaentry", content_type=ct)
    user.user_permissions.add(perm)


class EditRotaViewGet(DiaryTestsMixin, TestCase):
    """Test that rota edit view loads"""

    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(
                username="rota_editor", password="T3stPassword!3"
            )
        )

    def tearDown(self):
        self.client.logout()

    @patch("django.utils.timezone.now")
    def test_default_date_range(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("rota-edit")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_rota.html")

        # Check date range (default_days_ahead=92, so Jun 1 + 92 days = Sep 1):
        self.assertContains(
            response,
            r'<input type="date" name="from_date" value="2013-06-01" '
            r'id="id_from_date" class="form-control form-control-sm" />',
            html=True,
        )
        self.assertContains(
            response,
            r'<input type="date" name="to_date" value="2013-09-01" '
            r'id="id_to_date" class="form-control form-control-sm" />',
            html=True,
        )

        # Check event listed (name visible; public link present as ↗ arrow):
        self.assertContains(response, "Event four titl\u0113")
        self.assertContains(response, "/programme/showing/id/7/")

        # Notes present:
        self.assertContains(response, "Some notes about the Rota!")

    @patch("django.utils.timezone.now")
    def test_rota_edit_context_prompt_enabled(self, now_patch):
        now_patch.return_value = self._fake_now
        config = get_site_config()
        config.rota_clear_email_prompt_enabled = True
        config.save()
        response = self.client.get(reverse("rota-edit"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context["rota_clear_email_prompt_enabled"], True)

    @patch("django.utils.timezone.now")
    def test_rota_edit_context_prompt_disabled(self, now_patch):
        now_patch.return_value = self._fake_now
        config = get_site_config()
        config.rota_clear_email_prompt_enabled = False
        config.save()
        response = self.client.get(reverse("rota-edit"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.context["rota_clear_email_prompt_enabled"], False)

    @patch("django.utils.timezone.now")
    def test_date_range(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("rota-edit")
        url = "{}/{}/{:02}/{:02}?daysahead=10".format(
            url,
            self._fake_now.year,
            self._fake_now.month,
            self._fake_now.day + 10,
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "edit_rota.html")

        # Check date range:
        self.assertContains(
            response,
            r'<input type="date" name="from_date" value="2013-06-11" '
            r'id="id_from_date" class="form-control form-control-sm" />',
            html=True,
        )
        self.assertContains(
            response,
            r'<input type="date" name="to_date" value="2013-06-21" '
            r'id="id_to_date" class="form-control form-control-sm" />',
            html=True,
        )

        # Check event not listed:
        self.assertNotContains(response, "EVENT FOUR TITL\u0112")
        self.assertNotContains(response, "Some notes about the Rota!")

    @patch("django.utils.timezone.now")
    def test_rota_name_pronouns_tooltip_via_name_match(self, now_patch):
        """Legacy path: name-dict lookup populates the tooltip when no FK is set."""
        now_patch.return_value = self._fake_now

        m = Member.objects.get(name="Volunteer One")
        m.personal_pronouns = "they/them"
        m.save()

        entry = RotaEntry.objects.filter(showing=self.e4s3).first()
        entry.name = "Volunteer One"
        entry.volunteer = None
        entry.save()

        response = self.client.get(reverse("rota-edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="they/them"')
        self.assertNotContains(response, 'title=""')

    @patch("django.utils.timezone.now")
    def test_rota_name_pronouns_tooltip_via_fk(self, now_patch):
        """FK path: pronouns are taken directly from the linked volunteer."""
        now_patch.return_value = self._fake_now

        m = Member.objects.get(name="Volunteer One")
        m.personal_pronouns = "she/her"
        m.save()

        vol1 = m.volunteer
        entry = RotaEntry.objects.filter(showing=self.e4s3).first()
        entry.name = "Volunteer One"
        entry.volunteer = vol1
        entry.save()

        response = self.client.get(reverse("rota-edit"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="she/her"')
        self.assertNotContains(response, 'title=""')


class EditRotaViewPost(DiaryTestsMixin, TestCase):
    """Test of rota edit posting"""

    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(
                username="rota_editor", password="T3stPassword!3"
            )
        )

    def tearDown(self):
        self.client.logout()

    @patch("django.utils.timezone.now")
    def test_edit_entry(self, now_patch):
        # rota_editor has no linked volunteer, so free-text mode applies.
        now_patch.return_value = self._fake_now

        url = reverse("rota-edit")

        rota_entry = self.e4s3.rotaentry_set.all()[0]
        self.assertEqual(rota_entry.name, "")

        entry = "\u01aeesty McTestingt\u01d2n III"

        response = self.client.post(
            url, data={"id": rota_entry.pk, "value": entry}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, entry.encode("utf-8"))

        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)
        self.assertEqual(rota_entry.name, entry)
        self.assertIsNone(rota_entry.volunteer)

    @patch("django.utils.timezone.now")
    def test_volunteer_signup(self, now_patch):
        # A logged-in volunteer's submission coerces the name to their own
        # canonical name and links the FK regardless of what was typed.
        now_patch.return_value = self._fake_now

        from django.contrib.auth.models import User
        _grant_rota_permission(User.objects.get(username="vol1"))

        self.client.logout()
        self.client.login(username="vol1", password="testpass")

        url = reverse("rota-edit")
        rota_entry = self.e4s3.rotaentry_set.all()[0]

        response = self.client.post(
            url, data={"id": rota_entry.pk, "value": "anything typed"}
        )

        self.assertEqual(response.status_code, 200)

        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)
        # Name is coerced to the volunteer's member name ("Volunteer One")
        self.assertEqual(rota_entry.name, "Volunteer One")
        self.assertEqual(response.content, b"Volunteer One")
        # FK is set to the correct volunteer (v1 \u2192 m3 "Volunteer One")
        vol1_volunteer = Member.objects.get(name="Volunteer One").volunteer
        self.assertEqual(rota_entry.volunteer, vol1_volunteer)

    @patch("django.utils.timezone.now")
    def test_volunteer_clears_slot(self, now_patch):
        now_patch.return_value = self._fake_now

        from django.contrib.auth.models import User
        _grant_rota_permission(User.objects.get(username="vol1"))

        self.client.logout()
        self.client.login(username="vol1", password="testpass")

        url = reverse("rota-edit")
        rota_entry = self.e4s3.rotaentry_set.all()[0]
        rota_entry.name = "Volunteer One"
        rota_entry.volunteer = Member.objects.get(name="Volunteer One").volunteer
        rota_entry.save()

        response = self.client.post(
            url, data={"id": rota_entry.pk, "value": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)
        self.assertEqual(rota_entry.name, "")
        self.assertIsNone(rota_entry.volunteer)

    @patch("django.utils.timezone.now")
    def test_superuser_free_text(self, now_patch):
        # Superusers bypass coercion: any text is accepted, FK stays None.
        now_patch.return_value = self._fake_now

        self.client.logout()
        self.client.login(username="admin", password="T3stPassword!")

        url = reverse("rota-edit")
        rota_entry = self.e4s3.rotaentry_set.all()[0]

        arbitrary = "External hire / Funzo Productions"
        response = self.client.post(
            url, data={"id": rota_entry.pk, "value": arbitrary}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, arbitrary.encode("utf-8"))

        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)
        self.assertEqual(rota_entry.name, arbitrary)
        self.assertIsNone(rota_entry.volunteer)

    @patch("django.utils.timezone.now")
    def test_clear_entry(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("rota-edit")

        # Set data that will be cleared:
        rota_entries = self.e4s3.rotaentry_set.all()
        self.assertEqual(len(rota_entries), 1)
        rota_entry = self.e4s3.rotaentry_set.all()[0]
        rota_entry.name = "Not going to work!"
        rota_entry.save()

        # New content

        response = self.client.post(
            url, data={"id": rota_entry.pk, "value": ""}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

        # Check edit happened:
        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)

    @patch("django.utils.timezone.now")
    def test_edit_entry_in_past(self, now_patch):

        url = reverse("rota-edit")

        # Get data that will be edited:
        rota_entries = self.e4s3.rotaentry_set.all()
        self.assertEqual(len(rota_entries), 1)
        rota_entry = self.e4s3.rotaentry_set.all()[0]
        self.assertEqual(rota_entry.name, "")

        # Make sure time is after the event:
        now_patch.return_value = self.e4s3.start + timedelta(seconds=1)

        response = self.client.post(
            url,
            data={
                "id": rota_entry.pk,
                "value": "Spang",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.content.decode("utf-8"),
            "Can't change rota for showings in the past",
        )

        # Check edit didn't happen:
        rota_entry = RotaEntry.objects.get(pk=rota_entry.pk)
        self.assertEqual(rota_entry.name, "")

    def test_missing_name_and_id(self):
        url = reverse("rota-edit")
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Invalid entry id")

    def test_missing_id(self):
        url = reverse("rota-edit")
        response = self.client.post(url, data={"name": "Whoops"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Invalid entry id")

    @patch("django.utils.timezone.now")
    def test_missing_name(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse("rota-edit")

        rota_entry = self.e4s3.rotaentry_set.all()[0]

        response = self.client.post(url, data={"id": rota_entry.pk})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Invalid request")

    def test_unknown_id(self):
        url = reverse("rota-edit")
        response = self.client.post(url, data={"id": "1001", "value": "Foo!"})
        self.assertEqual(response.status_code, 404)

    def test_invalid_id(self):
        url = reverse("rota-edit")
        response = self.client.post(
            url, data={"id": "spanner", "value": "Foo!"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode("utf-8"), "Invalid entry id")


class EditRotaNotes(DiaryTestsMixin, TestCase):
    """Test of editing per-showing rota notes"""

    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(
                username="rota_editor", password="T3stPassword!3"
            )
        )

    def tearDown(self):
        self.client.logout()

    @patch("django.utils.timezone.now")
    def test_get_forbidden(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": self.e4s3.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    @patch("django.utils.timezone.now")
    def test_post(self, now_patch):
        now_patch.return_value = self._fake_now

        new_notes = "Line 1\nLine 2\n ...etc. (\u01d4\u01cbcode!)"

        url = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": self.e4s3.pk}
        )

        response = self.client.post(
            url,
            data={
                "rota_notes": new_notes,
            },
        )
        self.assertEqual(response.status_code, 200)

        showing = Showing.objects.get(pk=self.e4s3.pk)
        self.assertEqual(showing.rota_notes, new_notes)

    @patch("django.utils.timezone.now")
    def test_edit_past_showing_fails(self, now_patch):
        now_patch.return_value = self.e4s3.start + timedelta(seconds=1)

        original_notes = self.e4s3.rota_notes

        url = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": self.e4s3.pk}
        )

        response = self.client.post(
            url,
            data={
                "rota_notes": "Nope",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.content.decode("utf-8"),
            "Can't change rota for showings in the past",
        )

        showing = Showing.objects.get(pk=self.e4s3.pk)
        self.assertEqual(showing.rota_notes, original_notes)

    @patch("django.utils.timezone.now")
    def test_post_clear_notes(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": self.e4s3.pk}
        )

        response = self.client.post(url, data={"rota_notes": ""})
        self.assertEqual(response.status_code, 200)

        showing = Showing.objects.get(pk=self.e4s3.pk)
        self.assertEqual(showing.rota_notes, "")

    @patch("django.utils.timezone.now")
    def test_post_clear_notes_no_data(self, now_patch):
        now_patch.return_value = self._fake_now

        url = reverse(
            "edit-showing-rota-notes", kwargs={"showing_id": self.e4s3.pk}
        )

        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 200)

        showing = Showing.objects.get(pk=self.e4s3.pk)
        self.assertEqual(showing.rota_notes, "")


class ViewRotaVacancies(DiaryTestsMixin, TestCase):
    """Test of view of upcoming vacancies"""

    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(
                username="rota_editor", password="T3stPassword!3"
            )
        )

    def tearDown(self):
        self.client.logout()

    @patch("django.utils.timezone.now")
    def test_get_nothing_upcoming(self, now_patch):
        now_patch.return_value = self._fake_now + timedelta(days=365)
        url = reverse("view-rota-vacancies")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota_vacancies.html")
        self.assertContains(response, "No vacancies in the next")

    @patch("django.utils.timezone.now")
    def test_get(self, now_patch):
        now_patch.return_value = datetime(
            2013, 4, 12, 11, 00, tzinfo=zoneinfo.ZoneInfo("Europe/London")
        )
        url = reverse("view-rota-vacancies")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "view_rota_vacancies.html")

        self.assertContains(response, "Sat 13 Apr, 18:00")
        self.assertContains(response, "Event three title")
        self.assertContains(response, "Role 1 (standard)")
