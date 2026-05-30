import shutil
import os.path
import tempfile
import binascii
import datetime
import zoneinfo

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.conf import settings

from toolkit.members.models import AnonymisationLog, Member, Volunteer, TrainingRecord
from toolkit.diary.models import Role, RotaEntry, Showing, Event

from .common import MembersTestsMixin

TINY_VALID_BASE64_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAAXNSR0IArs4c6QAAAARnQU1BA"
    "ACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAAMSURBVBhXY/j//z8ABf4C/qc1gYQAAA"
    "AASUVORK5CYII="
)


class TestVolunteerListViews(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def _test_list_page_common(self, url, include_retired):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Volunteer One")
        self.assertContains(response, "Volunteer Two")
        self.assertContains(response, "Volunteer Three")
        if include_retired:
            self.assertContains(response, "Volunteer Four")
        else:
            self.assertNotContains(response, "Volunteer Four")

        self.assertTemplateUsed(response, "volunteer_list.html")

    def test_list_page_loads_default(self):
        url = reverse("view-volunteer-list")
        self._test_list_page_common(url, include_retired=False)

    def test_list_page_loads_include_inactive(self):
        url = reverse("view-volunteer-list", query={"show-retired": "true"})
        self._test_list_page_common(url, include_retired=True)

    def test_role_report_loads(self):
        url = reverse("view-volunteer-role-report")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertContains(response, "Volunteer One")
        self.assertContains(response, "Volunteer Three")
        # No role assigned:
        self.assertNotContains(response, "Volunteer Two")

        self.assertTemplateUsed(response, "volunteer_role_report.html")


class TestVolunteerEditViews(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()

        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def _post_status(self, volunteer, status):
        # Retirement, dormancy and reactivation are all done by editing the
        # volunteer's status on their profile page. Posts the edit form with
        # just the fields needed to change status.
        url = reverse("edit-volunteer", kwargs={"volunteer_id": volunteer.id})
        return self.client.post(
            url,
            data={
                "mem-name": volunteer.member.name,
                "mem-email": volunteer.member.email,
                "vol-status": status,
            },
            follow=True,
        )

    def test_retire_via_profile(self):
        v = Volunteer.objects.get(id=1)
        self.assertTrue(v.is_active)

        self._post_status(v, Volunteer.STATUS_RETIRED)

        v.refresh_from_db()
        self.assertEqual(v.status, Volunteer.STATUS_RETIRED)
        self.assertFalse(v.is_active)

    def test_unretire_via_profile(self):
        v = Volunteer.objects.get(id=1)
        v.status = Volunteer.STATUS_RETIRED
        v.save()

        self._post_status(v, Volunteer.STATUS_ACTIVE)

        v.refresh_from_db()
        self.assertEqual(v.status, Volunteer.STATUS_ACTIVE)
        self.assertTrue(v.is_active)

    def test_leaving_active_roster_notifies_vols_admin(self):
        # Moving a volunteer off the active roster emails the volunteers admin
        # so the mailing list can be kept in step.
        v = Volunteer.objects.get(id=1)
        mail.outbox = []
        self._post_status(v, Volunteer.STATUS_RETIRED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Change in volunteer status", mail.outbox[0].subject)

    def test_status_unchanged_does_not_notify(self):
        v = Volunteer.objects.get(id=1)  # already active
        mail.outbox = []
        self._post_status(v, Volunteer.STATUS_ACTIVE)
        self.assertEqual(len(mail.outbox), 0)


class TestVolunteerSuspension(MembersTestsMixin, TestCase):
    """Suspension is a safeguarding action. It must, at the model layer,
    immediately lock the login account and release upcoming shifts, and be
    fully reversible — independent of any view or form plumbing."""

    def setUp(self):
        super().setUp()
        self.future = datetime.datetime(
            2035, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC")
        )
        self.past = datetime.datetime(
            2010, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC")
        )

    def _make_entry_for(self, volunteer, start):
        event = Event(
            name="Ev", copy="c", copy_summary="s", duration=None,
            outside_hire=False, private=False,
        )
        event.save()
        # Showing.start is a FutureDateTimeField, so always create in the
        # future, then drop a past start in via .update() (bypassing validation)
        # when we need to simulate a historical shift.
        showing = Showing(event=event, start=self.future, confirmed=True)
        showing.save()
        if start != self.future:
            Showing.objects.filter(pk=showing.pk).update(start=start)
        return RotaEntry.objects.create(
            showing=showing,
            role=Role.objects.first(),
            volunteer=volunteer,
            name=volunteer.member.name,
            rank=1,
        )

    def test_suspend_disables_login(self):
        self.assertTrue(self.vol_1.user.is_active)
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        self.vol_1.user.refresh_from_db()
        self.assertFalse(self.vol_1.user.is_active)

    def test_suspend_marks_inactive(self):
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        self.assertFalse(self.vol_1.is_active)

    def test_reinstate_restores_login(self):
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        self.vol_1.status = Volunteer.STATUS_ACTIVE
        self.vol_1.save()
        self.vol_1.user.refresh_from_db()
        self.assertTrue(self.vol_1.user.is_active)

    def test_suspend_clears_future_shifts(self):
        entry = self._make_entry_for(self.vol_1, self.future)
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        entry.refresh_from_db()
        self.assertIsNone(entry.volunteer)
        self.assertEqual(entry.name, "")

    def test_suspend_keeps_past_shifts(self):
        entry = self._make_entry_for(self.vol_1, self.past)
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        entry.refresh_from_db()
        self.assertEqual(entry.volunteer_id, self.vol_1.pk)

    def test_suspend_leaves_other_volunteers_future_shifts(self):
        entry = self._make_entry_for(self.vol_2, self.future)
        self.vol_1.status = Volunteer.STATUS_SUSPENDED
        self.vol_1.save()
        entry.refresh_from_db()
        self.assertEqual(entry.volunteer_id, self.vol_2.pk)

    def test_save_does_not_reenable_independently_disabled_account(self):
        # A non-suspend save must never silently re-enable a login that was
        # disabled for another reason (e.g. GDPR anonymisation).
        self.vol_1.user.is_active = False
        self.vol_1.user.save()
        self.vol_1.notes = "touched"
        self.vol_1.save()
        self.vol_1.user.refresh_from_db()
        self.assertFalse(self.vol_1.user.is_active)

    def test_suspended_not_offered_to_non_superuser(self):
        from toolkit.members.forms import VolunteerForm
        form = VolunteerForm(instance=self.vol_1, is_superuser=False)
        values = [v for v, _ in form.fields["status"].choices]
        self.assertNotIn(Volunteer.STATUS_SUSPENDED, values)

    def test_suspended_offered_to_superuser(self):
        from toolkit.members.forms import VolunteerForm
        form = VolunteerForm(instance=self.vol_1, is_superuser=True)
        values = [v for v, _ in form.fields["status"].choices]
        self.assertIn(Volunteer.STATUS_SUSPENDED, values)


class TestVolunteerEdit(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )
        self.files_in_use = []

    def tearDown(self):
        for filename in self.files_in_use:
            try:
                if os.path.exists(filename):
                    os.unlink(filename)
            except OSError as ose:
                print("Couldn't delete file!", ose)

    @override_settings(MEDIA_URL="/")
    def test_get_form_edit(self):
        url = reverse("edit-volunteer", kwargs={"volunteer_id": self.vol_1.id})
        response = self.client.get(url)

        self.assertTemplateUsed(response, "form_volunteer.html")

        self.assertContains(response, "Volunteer One")
        self.assertContains(response, "volon@cube.test")
        self.assertContains(response, "0800 000 000")
        self.assertContains(response, "1 Road")
        self.assertContains(response, "Town of towns")
        self.assertContains(response, "BS6 123")
        self.assertContains(response, "UKountry")
        self.assertContains(response, "http://1.foo.test/")

        self.assertContains(
            response, "<title>Edit Volunteer Volunteer One</title>"
        )
        self.assertContains(
            response, '<a href="/tmp/path/to/portrait">', html=False
        )

    def test_get_form_add(self):
        url = reverse("add-volunteer")
        response = self.client.get(url)

        self.assertTemplateUsed(response, "form_volunteer.html")

        self.assertContains(
            response, "<title>Add Volunteer</title>", html=True
        )
        # Should have default mugshot:
        self.assertContains(
            response,
            f'<img id="photo" alt="No photo yet" src="{settings.DEFAULT_MUGSHOT}" width="75">',
            html=True,
        )

    def test_get_form_edit_invalid_vol(self):
        url = reverse("edit-volunteer", kwargs={"volunteer_id": 10001})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_post_new_vol_minimal_data(self):
        init_vol_count = Volunteer.objects.count()
        init_mem_count = Member.objects.count()

        url = reverse("add-volunteer")
        response = self.client.post(
            url,
            data={
                "mem-name": "New Volunteer, called \u0187hri\u01a8topher",
                "mem-email": "newvol@test.example",
                "vol-status": "active",
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("view-volunteer-summary"))

        self.assertContains(
            response,
            '<li class="success">Created volunteer &#x27;New Volunteer, '
            "called \u0187hri\u01a8topher&#x27;</li>",
            html=True,
        )

        # one more of each:
        self.assertEqual(Volunteer.objects.count(), init_vol_count + 1)
        self.assertEqual(Member.objects.count(), init_mem_count + 1)

        # New things:
        new_member = Member.objects.get(
            name="New Volunteer, called \u0187hri\u01a8topher"
        )
        # Implicitly check Volunteer record exists:
        self.assertTrue(new_member.volunteer.is_active)

    def test_post_new_vol_all_data(self):
        init_vol_count = Volunteer.objects.count()
        init_mem_count = Member.objects.count()

        url = reverse("add-volunteer")
        response = self.client.post(
            url,
            data={
                "mem-name": "Another New Volunteer",
                "mem-email": "snoo@whatver.com",
                "mem-address": "somewhere over the rainbow, I guess",
                "mem-posttown": "Town Town Town!",
                "mem-postcode": "< Sixteen chars?",
                "mem-country": "Suriname",
                "mem-website": "http://still_don't_care/",
                "mem-phone": "+44 1000000000000001",
                "mem-altphone": "-1 3202394 2352 23 234",
                "mem-mailout_failed": "t",
                "mem-notes": "member notes shouldn't be on this form!",
                "vol-notes": "plays the balalaika really badly",
                "vol-personal_pronouns": "xe/xem",
                "vol-roles": [2, 3],
                "vol-status": "active",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("view-volunteer-summary"))

        self.assertContains(
            response,
            '<li class="success">Created volunteer &#x27;Another New '
            "Volunteer&#x27;</li>",
            html=True,
        )

        # one more of each:
        self.assertEqual(Volunteer.objects.count(), init_vol_count + 1)
        self.assertEqual(Member.objects.count(), init_mem_count + 1)

        # New things:
        new_member = Member.objects.get(name="Another New Volunteer")
        self.assertEqual(new_member.email, "snoo@whatver.com")
        self.assertEqual(
            new_member.address, "somewhere over the rainbow, I guess"
        )
        self.assertEqual(new_member.posttown, "Town Town Town!")
        self.assertEqual(new_member.postcode, "< Sixteen chars?")
        self.assertEqual(new_member.country, "Suriname")
        self.assertEqual(new_member.website, "http://still_don't_care/")
        self.assertEqual(new_member.phone, "+44 1000000000000001")
        self.assertEqual(new_member.altphone, "-1 3202394 2352 23 234")
        self.assertFalse(new_member.mailout)
        # not in form, shouldn't have changed:
        self.assertFalse(new_member.mailout_failed)
        self.assertTrue(new_member.is_member)
        # Member notes aren't included on the form:
        self.assertEqual(new_member.notes, "")

        self.assertTrue(new_member.volunteer.is_active)
        self.assertEqual(
            new_member.volunteer.notes, "plays the balalaika really badly"
        )

        roles = new_member.volunteer.roles.all()

        self.assertEqual(len(roles), 2)
        self.assertEqual(roles[0].id, 2)
        self.assertEqual(roles[1].id, 3)

    def test_post_new_vol_invalid_missing_data(self):
        url = reverse("add-volunteer")
        response = self.client.post(url)

        self.assertTemplateUsed(response, "form_volunteer.html")

        # The only mandatory field (!)
        self.assertFormError(
            response.context["mem_form"], "name", "This field is required."
        )

    def test_post_edit_vol_minimal_data(self):
        init_vol_count = Volunteer.objects.count()
        init_mem_count = Member.objects.count()

        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        response = self.client.post(
            url,
            data={"mem-name": "Renam\u018fd Vol", "mem-email": "volon@cube.test", "vol-status": "active"},
            follow=True,
        )
        self.assertRedirects(response, reverse("view-volunteer-summary"))

        self.assertContains(
            response,
            '<li class="success">Updated volunteer &#x27;Renam\u018fd '
            "Vol&#x27;</li>",
            html=True,
        )

        # same number of each:
        self.assertEqual(Volunteer.objects.count(), init_vol_count)
        self.assertEqual(Member.objects.count(), init_mem_count)

        # extant member
        volunteer = Volunteer.objects.get(id=1)
        member = volunteer.member
        self.assertTrue(member.volunteer.is_active)
        # Changed things:
        self.assertEqual(member.name, "Renam\u018fd Vol")
        self.assertEqual(member.email, "volon@cube.test")
        self.assertEqual(member.address, "")
        self.assertEqual(member.posttown, "")
        self.assertEqual(member.postcode, "")
        self.assertEqual(member.country, "")
        self.assertEqual(member.website, "")
        self.assertEqual(member.phone, "")
        self.assertEqual(member.altphone, "")
        self.assertFalse(member.mailout)
        self.assertFalse(member.mailout_failed)
        self.assertTrue(member.is_member)
        # Member notes aren't included on the form:
        self.assertEqual(member.notes, "")

        self.assertTrue(member.volunteer.is_active)
        self.assertEqual(member.volunteer.notes, "")
        # Won't have changed without "clear" being checked:
        self.assertEqual(member.volunteer.portrait, "/tmp/path/to/portrait")

        self.assertEqual(member.volunteer.roles.count(), 0)

    def test_post_edit_vol_all_data(self):
        init_vol_count = Volunteer.objects.count()
        init_mem_count = Member.objects.count()

        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})

        response = self.client.post(
            url,
            data={
                "mem-name": "Renam\u018fd Vol",
                "mem-email": "snoo@whatver.com",
                "mem-address": "somewhere over the rainbow, I guess",
                "mem-posttown": "Town Town Town!",
                "mem-postcode": "< Sixteen chars?",
                "mem-country": "Suriname",
                "mem-website": "http://still_don't_care/",
                "mem-phone": "+44 1000000000000001",
                "mem-altphone": "-1 3202394 2352 23 234",
                "mem-mailout_failed": "t",
                "mem-notes": "member notes shouldn't be on this form!",
                "vol-notes": "plays the balalaika really badly",
                "vol-personal_pronouns": "xe/xem",
                "vol-roles": [2, 3],
                "vol-status": "active",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("view-volunteer-summary"))

        self.assertContains(
            response,
            '<li class="success">Updated volunteer &#x27;Renam\u018fd '
            "Vol&#x27;</li>",
            html=True,
        )

        # same number of each:
        self.assertEqual(Volunteer.objects.count(), init_vol_count)
        self.assertEqual(Member.objects.count(), init_mem_count)

        # extant member
        volunteer = Volunteer.objects.get(id=1)
        member = volunteer.member
        self.assertTrue(member.volunteer.is_active)
        self.assertEqual(member.name, "Renam\u018fd Vol")
        self.assertEqual(member.email, "snoo@whatver.com")
        self.assertEqual(member.address, "somewhere over the rainbow, I guess")
        self.assertEqual(member.posttown, "Town Town Town!")
        self.assertEqual(member.postcode, "< Sixteen chars?")
        self.assertEqual(member.country, "Suriname")
        self.assertEqual(member.website, "http://still_don't_care/")
        self.assertEqual(member.phone, "+44 1000000000000001")
        self.assertEqual(member.altphone, "-1 3202394 2352 23 234")
        self.assertFalse(member.mailout)
        # not in form, shouldn't have changed:
        self.assertFalse(member.mailout_failed)
        self.assertTrue(member.is_member)
        # Member notes aren't included on the form:
        self.assertEqual(member.notes, "")

        self.assertTrue(member.volunteer.is_active)
        self.assertEqual(
            member.volunteer.notes, "plays the balalaika really badly"
        )

        roles = member.volunteer.roles.all()

        self.assertEqual(len(roles), 2)
        self.assertEqual(roles[0].id, 2)
        self.assertEqual(roles[1].id, 3)

    def test_post_update_vol_invalid_missing_data(self):
        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        response = self.client.post(url)

        self.assertTemplateUsed(response, "form_volunteer.html")

        # The only mandatory field (!)
        self.assertFormError(
            response.context["mem_form"], "name", "This field is required."
        )

    def test_post_update_vol_invalid_vol_id(self):
        url = reverse("edit-volunteer", kwargs={"volunteer_id": 10001})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_update_vol_clear_portrait(self):

        temp_jpg = tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg", delete=False
        )

        # Ensure files get cleaned up:
        self.files_in_use.append(temp_jpg.name)

        temp_jpg.close()

        # Add to vol 1:
        vol = Volunteer.objects.get(id=1)
        vol.portrait = temp_jpg.name
        vol.save()

        # No errant code should have deleted the files:
        self.assertTrue(os.path.isfile(temp_jpg.name))

        # Post an edit to clear the image:
        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        response = self.client.post(
            url,
            data={
                "mem-name": "Pictureless Person",
                "mem-email": "volon@cube.test",
                "vol-portrait-clear": "t",
                "vol-status": "active",
            },
        )
        self.assertRedirects(response, reverse("view-volunteer-summary"))

        vol = Volunteer.objects.get(id=1)
        self.assertEqual(vol.member.name, "Pictureless Person")
        self.assertEqual(vol.portrait, "")

        # Should have deleted the old images:
        self.assertFalse(os.path.isfile(temp_jpg.name))

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_update_vol_change_portrait_success(self):
        temp_old_jpg = tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="toolkit-test-", suffix=".jpg", delete=False
        )

        expected_upload_path = os.path.join(
            "/tmp", settings.VOLUNTEER_PORTRAIT_DIR, "image_bluesq.jpg"
        )

        # Ensure files get cleaned up:
        self.files_in_use.append(temp_old_jpg.name)
        self.files_in_use.append(expected_upload_path)
        temp_old_jpg.close()

        # Add to vol 1:
        vol = Volunteer.objects.get(id=1)
        vol.portrait = temp_old_jpg.name
        vol.save()

        # No errant code should have deleted the files:
        self.assertTrue(os.path.isfile(temp_old_jpg.name))

        # Get new image to send:
        new_jpg_filename = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "test_data",
            "image_bluesq.jpg",
        )

        with open(new_jpg_filename, "rb") as new_jpg_file:
            # Post an edit to update the image:
            url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
            response = self.client.post(
                url,
                data={
                    "mem-name": "Pictureless Person",
                    "mem-email": "volon@cube.test",
                    "vol-portrait": new_jpg_file,
                    "vol-status": "active",
                },
            )

        self.assertRedirects(response, reverse("view-volunteer-summary"))

        vol = Volunteer.objects.get(id=1)
        self.assertEqual(vol.member.name, "Pictureless Person")

        # Portrait path should be:
        self.assertEqual(
            vol.portrait.name,
            os.path.join(settings.VOLUNTEER_PORTRAIT_DIR, "image_bluesq.jpg"),
        )
        # And should have 'uploaded' file to:
        self.assertTrue(os.path.isfile(expected_upload_path))

        # Should have deleted the old images:
        self.assertFalse(os.path.isfile(temp_old_jpg.name))

        # TODO do this properly:
        shutil.rmtree(os.path.join("/tmp", settings.VOLUNTEER_PORTRAIT_DIR))

    @override_settings(MEDIA_ROOT="/tmp")
    def test_post_update_vol_set_portrait_data_uri(self):
        expected_upload_path = os.path.join(
            settings.VOLUNTEER_PORTRAIT_DIR, "webcam_photo.png"
        )
        expected_upload_location = os.path.join("/tmp", expected_upload_path)

        # Ensure files get cleaned up:
        self.files_in_use.append(expected_upload_location)

        # Add to vol 1:
        vol = Volunteer.objects.get(id=1)
        self.assertNotEqual(vol.portrait, expected_upload_path)

        # Post an edit to update the image:
        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        response = self.client.post(
            url,
            data={
                "mem-name": "Pictureless Person",
                "mem-email": "volon@cube.test",
                "vol-image_data": (
                    f"data:image/png;base64,{TINY_VALID_BASE64_PNG}"
                ),
                "vol-status": "active",
            },
        )

        self.assertRedirects(response, reverse("view-volunteer-summary"))

        vol = Volunteer.objects.get(id=1)
        self.assertEqual(vol.member.name, "Pictureless Person")

        # Portrait path should be:
        self.assertEqual(vol.portrait.name, expected_upload_path)
        # And should have 'uploaded' file to:
        self.assertTrue(os.path.isfile(expected_upload_location))
        # And contents:
        with open(expected_upload_location, "rb") as imgf:
            self.assertEqual(
                imgf.read(), binascii.a2b_base64(TINY_VALID_BASE64_PNG)
            )

        # TODO do this properly!
        shutil.rmtree(os.path.join("/tmp", settings.VOLUNTEER_PORTRAIT_DIR))

    def test_post_update_vol_set_portrait_data_uri_bad_mimetype(self):
        vol = Volunteer.objects.get(id=1)
        initial_portrait = vol.portrait.name
        self.assertNotEqual(initial_portrait, None)

        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        response = self.client.post(
            url,
            data={
                "mem-name": "Pictureless Person",
                "vol-image_data": (
                    f"data:image/jpeg;base64,{TINY_VALID_BASE64_PNG}"
                ),
            },
        )

        self.assertTemplateUsed(response, "form_volunteer.html")
        # * No form error, as it's a form-wide validation fail, not per-field.
        #   Settle for just being happy that the file hasn't been saved
        # self.assertFormError(response, 'vol_form', 'image_data',
        #                      u'Image data format not recognised')

        vol = Volunteer.objects.get(id=1)
        self.assertNotEqual(vol.member.name, "Pictureless Person")
        self.assertEqual(vol.portrait.name, initial_portrait)

    def test_post_update_vol_set_portrait_data_bad_bytes(self):
        vol = Volunteer.objects.get(id=1)
        initial_portrait = vol.portrait.name
        self.assertNotEqual(initial_portrait, None)

        url = reverse("edit-volunteer", kwargs={"volunteer_id": 1})
        INVALID_PNG = f"Spinach{TINY_VALID_BASE64_PNG}"
        response = self.client.post(
            url,
            data={
                "mem-name": "Pictureless Person",
                "vol-image_data": f"data:image/png;base64,{INVALID_PNG}",
            },
        )

        self.assertTemplateUsed(response, "form_volunteer.html")
        # * No form error, as it's a form-wide validation fail, not per-field.
        #   Settle for just being happy that the file hasn't been saved
        # self.assertFormError(response, 'vol_form', 'image_data',
        #                      u'Image data format not recognised')

        vol = Volunteer.objects.get(id=1)
        self.assertNotEqual(vol.member.name, "Pictureless Person")
        self.assertEqual(vol.portrait.name, initial_portrait)


class TestAddTraining(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def _test_add_training_common(self, is_general):
        url = reverse(
            "add-volunteer-training-record", kwargs={"volunteer_id": 1}
        )
        role = Role.objects.get(id=2)
        vol = Volunteer.objects.get(id=1)

        self.assertFalse(role in vol.roles.all())

        trainer = "Friendly Trainer \u0187hri\u01a8topher"
        notes = " No notes\nare noted... here. "

        post_data = {
            "training-training_type": TrainingRecord.ROLE_TRAINING,
            "training-trainer": trainer,
            "training-training_date": "1/2/2015",
            "training-notes": notes,
        }
        if is_general:
            post_data["training-training_type"] = (
                TrainingRecord.GENERAL_TRAINING
            )
            post_data["training-role"] = ""
        else:
            post_data["training-training_type"] = TrainingRecord.ROLE_TRAINING
            post_data["training-role"] = role.id

        response = self.client.post(url, data=post_data)
        expected = {
            "succeeded": True,
            "id": 1,
            "training_description": str(role),
            "training_date": "01/02/2015",
            "trainer": trainer,
            "notes": notes.strip(),
        }
        if is_general:
            expected["training_description"] = (
                TrainingRecord.GENERAL_TRAINING_DESC
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

        vol = Volunteer.objects.get(id=1)
        self.assertEqual(len(vol.training_records.all()), 1)
        record = vol.training_records.all()[0]
        self.assertEqual(record.role, None if is_general else role)
        self.assertEqual(record.trainer, trainer)
        self.assertEqual(record.notes, notes.strip())
        self.assertEqual(
            record.training_date, datetime.date(day=1, month=2, year=2015)
        )
        if is_general:
            self.assertFalse(role in vol.roles.all())
        else:
            self.assertTrue(role in vol.roles.all())

    def test_add_role_training(self):
        self._test_add_training_common(is_general=False)

    def test_add_general_training(self):
        self._test_add_training_common(is_general=True)

    def test_add_training_missing_training_type_data(self):
        url = reverse(
            "add-volunteer-training-record", kwargs={"volunteer_id": 1}
        )
        response = self.client.post(url, data={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "succeeded": False,
                "errors": {
                    "training_type": ["This field is required."],
                    "trainer": ["This field is required."],
                    "training_date": ["This field is required."],
                },
            },
        )
        vol = Volunteer.objects.get(id=1)
        self.assertEqual(len(vol.training_records.all()), 0)

    def test_add_training_missing_role(self):
        url = reverse(
            "add-volunteer-training-record", kwargs={"volunteer_id": 1}
        )
        response = self.client.post(
            url,
            data={
                "training-training_type": TrainingRecord.ROLE_TRAINING,
                "training-trainer": "trainer",
                "training-training_date": "1/2/2015",
                "training-notes": "notes",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                "succeeded": False,
                "errors": {
                    "role": ["This field is required."],
                },
            },
            response.json(),
        )
        vol = Volunteer.objects.get(id=1)
        self.assertEqual(len(vol.training_records.all()), 0)

    def test_add_training_inactive_volunteer(self):
        vol = Volunteer.objects.inactive()[0]
        url = reverse(
            "add-volunteer-training-record", kwargs={"volunteer_id": vol.id}
        )
        response = self.client.post(
            url,
            data={
                "training-role": 1,
                "training-trainer": "Trainer",
                "training-training_date": "1/2/2015",
                "training-notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"succeeded": False, "errors": "volunteer is not active"},
        )
        self.assertEqual(len(vol.training_records.all()), 0)


class TestDeleteTraining(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def test_delete_training_record(self):
        vol = Volunteer.objects.get(id=1)
        role = Role.objects.get(id=1)

        record = TrainingRecord(
            volunteer=vol,
            training_type=TrainingRecord.ROLE_TRAINING,
            role=role,
            trainer="Trainer",
            training_date=datetime.date(day=29, month=2, year=2012),
        )
        record.save()

        url = reverse(
            "delete-volunteer-training-record",
            kwargs={"training_record_id": record.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertEqual(response.content, b"OK")

        self.assertEqual(len(TrainingRecord.objects.all()), 0)

    def test_delete_training_record_inactive_vol(self):
        vol = Volunteer.objects.get(id=1)
        role = Role.objects.get(id=1)

        record = TrainingRecord(
            volunteer=vol,
            training_type=TrainingRecord.ROLE_TRAINING,
            role=role,
            trainer="Trainer",
            training_date=datetime.date(day=29, month=2, year=2012),
        )
        record.save()

        vol.status = Volunteer.STATUS_RETIRED
        vol.save()

        url = reverse(
            "delete-volunteer-training-record",
            kwargs={"training_record_id": record.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        self.assertEqual(len(TrainingRecord.objects.all()), 1)


class TestAddGroupTraining(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def test_get_form(self):
        url = reverse("add-volunteer-training-group-record")
        response = self.client.get(url)
        self.assertTemplateUsed(response, "form_group_training.html")

    def _shared_test_add_group_role_record(self, test_general):
        url = reverse("add-volunteer-training-group-record")

        role = Role.objects.get(id=1)
        trainer = "Trainer \u0187hri\u01a8topher"
        notes = " Some not\u018fs\nwere noted here. "
        training_date = datetime.date(day=4, month=5, year=2016)

        volunteers = Volunteer.objects.active()[:3]
        self.assertEqual(len(volunteers), 3)
        post_data = {
            "role": "",
            "trainer": trainer,
            "training_date": "4/5/2016",
            "notes": notes,
            "volunteers": [v.member.id for v in volunteers],
        }

        if test_general:
            post_data["type"] = TrainingRecord.GENERAL_TRAINING
        else:
            post_data["type"] = TrainingRecord.ROLE_TRAINING
            post_data["role"] = role.id

        response = self.client.post(url, data=post_data)
        self.assertRedirects(response, url)

        volunteers = Volunteer.objects.active()[:3]
        for vol in volunteers:
            recs = vol.training_records.all()
            self.assertEqual(len(recs), 1)
            if test_general:
                self.assertEqual(
                    recs[0].training_type, TrainingRecord.GENERAL_TRAINING
                )
                self.assertEqual(recs[0].role, None)
            else:
                self.assertTrue(role in vol.roles.all())
                self.assertEqual(
                    recs[0].training_type, TrainingRecord.ROLE_TRAINING
                )
                self.assertEqual(recs[0].role, role)
            self.assertEqual(recs[0].notes, notes.strip())
            self.assertEqual(recs[0].trainer, trainer)
            self.assertEqual(recs[0].training_date, training_date)

    def test_add_group_role_record(self):
        self._shared_test_add_group_role_record(test_general=False)

    def test_add_group_general_record(self):
        self._shared_test_add_group_role_record(test_general=True)

    def test_add_group_inactive_volunteer(self):
        url = reverse("add-volunteer-training-group-record")

        role = Role.objects.get(id=1)

        volunteers = Volunteer.objects.active()[:3]
        self.assertEqual(len(volunteers), 3)
        volunteers[1].status = Volunteer.STATUS_RETIRED
        volunteers[1].save()

        response = self.client.post(
            url,
            data={
                "type": TrainingRecord.ROLE_TRAINING,
                "role": role.id,
                "trainer": "trainer",
                "training_date": "4/5/2016",
                "notes": "",
                "volunteers": [v.member.id for v in volunteers],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_group_training.html")

        # It's not the ideal error message, I grant you:
        self.assertFormError(
            response.context["form"],
            "volunteers",
            "Select a valid choice. %d is not one of the available choices."
            % (volunteers[1].member.id),
        )

    def test_add_group_record_missing_data(self):
        url = reverse("add-volunteer-training-group-record")

        self.assertEqual(len(TrainingRecord.objects.all()), 0)

        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_group_training.html")

        self.assertFormError(
            response.context["form"], "type", "This field is required."
        )
        # 'role' isn't requireed unless 'type' is selected
        # self.assertFormError(response, 'form', 'role',
        #                     u'This field is required.')
        self.assertFormError(
            response.context["form"],
            "training_date",
            "This field is required.",
        )
        self.assertFormError(
            response.context["form"], "trainer", "This field is required."
        )
        self.assertFormError(
            response.context["form"], "volunteers", "This field is required."
        )

    def test_add_group_record_missing_role(self):
        url = reverse("add-volunteer-training-group-record")

        self.assertEqual(len(TrainingRecord.objects.all()), 0)

        response = self.client.post(
            url,
            data={
                "type": TrainingRecord.ROLE_TRAINING,
                "trainer": "trainer",
                "training_date": "4/5/2016",
                "notes": "",
                "volunteers": 1,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "form_group_training.html")

        self.assertFormError(
            response.context["form"], "role", "This field is required."
        )


class TestViewVolunteerTraining(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def test_content(self):
        url = reverse("view-volunteer-training-report")

        volunteers = Volunteer.objects.active()[:3]
        self.assertEqual(len(volunteers), 3)

        role = Role.objects.get(id=1)
        training_date = datetime.date(day=4, month=5, year=2016)

        for vol in volunteers:
            self.assertTrue(vol.is_active)
            vol.roles.add(role)
            record = TrainingRecord(
                volunteer=vol,
                training_type=TrainingRecord.ROLE_TRAINING,
                role=role,
                trainer="trainer",
                training_date=training_date,
            )
            record.save()

        # Add a second, older record, that should not take precedence, for
        # vol[0]
        newer_date = training_date - datetime.timedelta(days=1)
        new_record = TrainingRecord(
            volunteer=volunteers[0],
            training_type=TrainingRecord.ROLE_TRAINING,
            role=role,
            trainer="trainer",
            training_date=newer_date,
        )
        new_record.save()

        # Add a third old record, that should also not take
        # precedence, for vol[0] (to force coverage of one of the
        # conditionals in the view...)
        newer_date = training_date - datetime.timedelta(days=1)
        new_record = TrainingRecord(
            volunteer=volunteers[0],
            training_type=TrainingRecord.ROLE_TRAINING,
            role=role,
            trainer="trainer",
            training_date=newer_date,
        )
        new_record.save()

        # Similarly, add an older and a newer general training record for vol
        # 3:
        older_date = training_date - datetime.timedelta(days=2)
        new_record = TrainingRecord(
            volunteer=volunteers[2],
            training_type=TrainingRecord.GENERAL_TRAINING,
            trainer="old trainer",
            training_date=older_date,
        )
        new_record.save()

        newer_date = training_date - datetime.timedelta(days=1)
        new_record = TrainingRecord(
            volunteer=volunteers[2],
            training_type=TrainingRecord.GENERAL_TRAINING,
            trainer="new trainer",
            training_date=newer_date,
        )
        new_record.save()

        # Make vol[1] inactive
        volunteers[1].status = Volunteer.STATUS_RETIRED
        volunteers[1].save()

        # Make vol[2] not have the role:
        volunteers[2].roles.remove(role)

        # ...so should just have one training record:
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "volunteer_training_report.html")
        self.assertContains(
            response,
            """
            <div class="role_info" id="id_role_info_1">
              <h2>Role 1 (standard)</h2>
              <ul>

                  <li class="training_record" data-training-time="1462316400">
                    <a href="/volunteers/1/edit#training-record">
                      Volunteer One
                    </a>
                    &mdash; last trained 04/05/2016
                  </li>

              </ul>
            </div>""",
            html=True,
        )
        self.assertNotContains(response, "Role 2")
        self.assertContains(
            response,
            """
            <div>
              <h2>General Safety Training</h2>
              <ul>
                  <li class="training_record" data-training-time="0">
                    <a href="/volunteers/1/edit">
                      Volunteer One
                    </a>
                    &mdash; never trained
                  </li>
                  <li class="training_record" data-training-time="1462230000">
                    <a href="/volunteers/3/edit">
                      Volunteer Three
                    </a>
                    &mdash;
                        last trained 03/05/2016
                  </li>
              </ul>
            </div>""",
            html=True,
        )

        self.assertNotContains(response, "Volunteer Two")
        self.assertNotContains(response, "Volunteer Four")

    def test_no_post(self):
        url = reverse("view-volunteer-training-report")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 405)


class TestAnonymiseVolunteer(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Grant superuser status to the shared admin test account
        from django.contrib.auth.models import User as AuthUser
        AuthUser.objects.filter(username="admin").update(is_superuser=True)
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )
        self.url = reverse("anonymise-volunteer", kwargs={"volunteer_id": self.vol_1.pk})

    def tearDown(self):
        self.client.logout()

    def _post_confirm(self, volunteer=None, name=None):
        vol = volunteer or self.vol_1
        url = reverse("anonymise-volunteer", kwargs={"volunteer_id": vol.pk})
        confirm_name = name if name is not None else vol.member.name
        return self.client.post(url, {"confirm_name": confirm_name})

    def test_get_requires_superuser(self):
        self.client.logout()
        self.client.login(username="no_perm", password="T3stPassword!2")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_post_requires_superuser(self):
        self.client.logout()
        self.client.login(username="no_perm", password="T3stPassword!2")
        response = self._post_confirm()
        self.assertEqual(response.status_code, 403)

    def test_get_shows_preview(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Volunteer One")
        self.assertTemplateUsed(response, "anonymise_volunteer.html")

    def test_wrong_name_aborts(self):
        response = self._post_confirm(name="Wrong Name")
        self.assertEqual(response.status_code, 302)
        self.vol_1.member.refresh_from_db()
        self.assertEqual(self.vol_1.member.name, "Volunteer One")

    def test_anonymise_clears_member_pii(self):
        self._post_confirm()
        self.vol_1.member.refresh_from_db()
        member = self.vol_1.member
        self.assertIn("Anonymised", member.name)
        self.assertIn("deleted.invalid", member.email)
        self.assertEqual(member.address, "")
        self.assertEqual(member.phone, "")
        self.assertEqual(member.notes, "")

    def test_anonymise_deactivates_user(self):
        self._post_confirm()
        self.vol_1.user.refresh_from_db()
        self.assertFalse(self.vol_1.user.is_active)
        self.assertFalse(self.vol_1.user.is_superuser)
        self.assertIn("anon-", self.vol_1.user.username)

    def test_anonymise_deactivates_volunteer(self):
        self._post_confirm()
        self.vol_1.refresh_from_db()
        self.assertFalse(self.vol_1.is_active)
        self.assertEqual(self.vol_1.notes, "")

    def test_anonymise_clears_roles(self):
        self._post_confirm()
        self.vol_1.refresh_from_db()
        self.assertEqual(self.vol_1.roles.count(), 0)

    def test_anonymise_deletes_training_records(self):
        role = Role.objects.first()
        TrainingRecord.objects.create(
            volunteer=self.vol_1,
            role=role,
            training_type=TrainingRecord.ROLE_TRAINING,
            training_date=datetime.date(2024, 1, 1),
        )
        self.assertEqual(TrainingRecord.objects.filter(volunteer=self.vol_1).count(), 1)
        self._post_confirm()
        self.assertEqual(TrainingRecord.objects.filter(volunteer=self.vol_1).count(), 0)

    def _make_rota_entry(self, name, event_name="Test Event"):
        event = Event(
            name=event_name,
            copy="copy",
            copy_summary="summary",
            duration=None,
            outside_hire=False,
            private=False,
        )
        event.save()
        showing = Showing(
            event=event,
            start=datetime.datetime(2030, 6, 1, 19, 0, tzinfo=zoneinfo.ZoneInfo("UTC")),
            confirmed=True,
        )
        showing.save()
        role = Role.objects.first()
        return RotaEntry.objects.create(
            showing=showing,
            role=role,
            name=name,
            rank=1,
        )

    def test_anonymise_blanks_rota_entries_by_name(self):
        entry = self._make_rota_entry("Volunteer One")
        self._post_confirm()
        entry.refresh_from_db()
        self.assertEqual(entry.name, "")

    def test_rota_entries_with_different_name_preserved(self):
        entry = self._make_rota_entry("Someone Else", event_name="Other Event")
        self._post_confirm()
        entry.refresh_from_db()
        self.assertEqual(entry.name, "Someone Else")

    def test_anonymise_creates_audit_log(self):
        self.assertEqual(AnonymisationLog.objects.count(), 0)
        self._post_confirm()
        self.assertEqual(AnonymisationLog.objects.count(), 1)
        log = AnonymisationLog.objects.first()
        self.assertEqual(log.volunteer_pk, self.vol_1.pk)
        self.assertIsNotNone(log.performed_by)


from toolkit.labs.models import Collective


class TestVolunteerDirectory(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.dir_url = reverse("volunteer-directory")

    def test_requires_login(self):
        response = self.client.get(self.dir_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_loads_for_any_logged_in_user(self):
        self.client.login(username="no_perm", password="T3stPassword!2")
        response = self.client.get(self.dir_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "volunteer_directory.html")

    def test_opted_out_volunteer_not_listed(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertNotContains(response, "Volunteer One")

    def test_opted_in_full_name_shown(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertContains(response, "Volunteer One")

    def test_opted_in_initial_only(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_INITIAL
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertContains(response, "Volunteer O.")
        self.assertNotContains(response, "Volunteer One")

    def test_search_filters_by_name(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.save()
        self.vol_2.dir_share_listed = True
        self.vol_2.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_2.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url + "?q=One")
        self.assertContains(response, "Volunteer One")
        self.assertNotContains(response, "Volunteer Two")

    def test_pronouns_shown_when_opted_in(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.dir_share_pronouns = True
        self.vol_1.save()
        self.mem_4.personal_pronouns = "they/them"
        self.mem_4.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertContains(response, "they/them")

    def test_access_rider_shown_when_opted_in(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.dir_share_access_rider = True
        self.vol_1.access_needs = "Please provide a chair."
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertContains(response, "Please provide a chair.")

    def test_access_rider_hidden_when_not_opted_in(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.dir_share_access_rider = False
        self.vol_1.access_needs = "Please provide a chair."
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertNotContains(response, "Please provide a chair.")

    def test_collectives_shown_when_opted_in(self):
        collective = Collective.objects.create(name="Film Collective", slug="film", colour="#000000")
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.dir_share_collectives = True
        self.vol_1.collectives.add(collective)
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertContains(response, "Film Collective")

    def test_email_not_shown_when_not_opted_in(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.vol_1.dir_share_email = False
        self.vol_1.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.dir_url)
        self.assertNotContains(response, "volon@cube.test")


class TestVolunteerDirectoryDisplayName(MembersTestsMixin, TestCase):
    def test_full_name(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_FULL
        self.assertEqual(self.vol_1.directory_display_name(), "Volunteer One")

    def test_initial_multi_word(self):
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_INITIAL
        self.assertEqual(self.vol_1.directory_display_name(), "Volunteer O.")

    def test_initial_single_word(self):
        self.mem_4.name = "Mononym"
        self.mem_4.save()
        self.vol_1.dir_share_listed = True
        self.vol_1.dir_share_name_style = Volunteer.NAME_STYLE_INITIAL
        self.assertEqual(self.vol_1.directory_display_name(), "Mononym")

    def test_none_returns_empty(self):
        self.vol_1.dir_share_listed = False
        self.assertEqual(self.vol_1.directory_display_name(), "")


class TestVolunteerPIIPermissionBoundary(MembersTestsMixin, TestCase):
    """9.74: Programmer (toolkit.write only) must not access volunteer PII views."""

    PII_URLS = [
        "view-volunteer-list",
        "view-volunteer-summary",
        "view-volunteer-role-report",
        "view-volunteer-training-report",
        "view-volunteer-export",
    ]

    def setUp(self):
        super().setUp()
        self.client.login(username="read_only", password="T3stPassword!1")

    def _get(self, url_name, **kwargs):
        return self.client.get(reverse(url_name, kwargs=kwargs))

    def test_read_only_denied_volunteer_list(self):
        resp = self._get("view-volunteer-list")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_read_only_denied_volunteer_summary(self):
        resp = self._get("view-volunteer-summary")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_read_only_denied_volunteer_role_report(self):
        resp = self._get("view-volunteer-role-report")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_read_only_denied_volunteer_export(self):
        resp = self._get("view-volunteer-export")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_read_only_denied_volunteer_training_report(self):
        resp = self._get("view-volunteer-training-report")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp["Location"])

    def test_read_only_denied_edit_other_volunteer(self):
        resp = self._get("edit-volunteer", volunteer_id=self.vol_1.pk)
        # read_only has no volunteer record, so editing another's profile → denied
        self.assertEqual(resp.status_code, 403)

    def test_panopticon_can_access_volunteer_list(self):
        self.client.login(username="admin", password="T3stPassword!")
        resp = self._get("view-volunteer-list")
        self.assertEqual(resp.status_code, 200)
