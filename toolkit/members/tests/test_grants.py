"""Tests for PanopticonGrant, ProgrammerGrant models and the access transparency page."""
import datetime

from django.contrib.auth.models import User, Group
from django.test import TestCase
from django.urls import reverse

from toolkit.members.models import PanopticonGrant, ProgrammerGrant
from .common import MembersTestsMixin


class PanopticonGrantModelTests(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.panopticon_user = User.objects.get(username="admin")

    def test_grant_created_manually(self):
        grant = PanopticonGrant.objects.create(
            user=self.panopticon_user,
            reason="Testing",
            granted_by=self.panopticon_user,
        )
        self.assertEqual(grant.user, self.panopticon_user)
        self.assertEqual(grant.reason, "Testing")
        self.assertIsNone(grant.last_reviewed_at)

    def test_review_overdue_when_no_review(self):
        grant = PanopticonGrant.objects.create(
            user=self.panopticon_user,
            reason="Test",
        )
        self.assertTrue(grant.review_overdue())

    def test_review_not_overdue_when_recent(self):
        grant = PanopticonGrant.objects.create(
            user=self.panopticon_user,
            reason="Test",
            last_reviewed_at=datetime.date.today(),
        )
        self.assertFalse(grant.review_overdue())

    def test_review_overdue_when_over_365_days(self):
        old_date = datetime.date.today() - datetime.timedelta(days=366)
        grant = PanopticonGrant.objects.create(
            user=self.panopticon_user,
            reason="Test",
            last_reviewed_at=old_date,
        )
        self.assertTrue(grant.review_overdue())


class UserFormGrantIntegrationTests(MembersTestsMixin, TestCase):
    """Test that UserForm.save() creates/deletes grant records."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.get(username="admin")
        self.target_user = User.objects.create_user(
            "target_vol", "target@example.com", "pass"
        )

    def _make_form(self, **post_data):
        from toolkit.members.forms import UserForm
        defaults = {
            "user-username": self.target_user.username,
        }
        defaults.update(post_data)
        return UserForm(defaults, instance=self.target_user)

    def test_granting_panopticon_creates_grant(self):
        form = self._make_form(**{
            "user-is_superuser": "on",
            "user-panopticon_reason": "Organising committee",
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save(granted_by=self.admin)
        grant = PanopticonGrant.objects.get(user=self.target_user)
        self.assertEqual(grant.reason, "Organising committee")
        self.assertEqual(grant.granted_by, self.admin)

    def test_granting_panopticon_without_reason_fails(self):
        form = self._make_form(**{"user-is_superuser": "on", "user-panopticon_reason": ""})
        self.assertFalse(form.is_valid())
        self.assertFalse(PanopticonGrant.objects.filter(user=self.target_user).exists())

    def test_revoking_panopticon_deletes_grant(self):
        self.target_user.is_superuser = True
        self.target_user.save()
        PanopticonGrant.objects.create(user=self.target_user, reason="Old reason")
        form = self._make_form(**{"user-is_superuser": False})
        self.assertTrue(form.is_valid(), form.errors)
        form.save(granted_by=self.admin)
        self.assertFalse(PanopticonGrant.objects.filter(user=self.target_user).exists())

    def test_granting_programmer_creates_grant(self):
        form = self._make_form(**{"user-programmer": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save(granted_by=self.admin)
        self.assertTrue(ProgrammerGrant.objects.filter(user=self.target_user).exists())
        grant = ProgrammerGrant.objects.get(user=self.target_user)
        self.assertEqual(grant.granted_by, self.admin)

    def test_revoking_programmer_deletes_grant(self):
        programmers, _ = Group.objects.get_or_create(name="Programmers")
        self.target_user.groups.add(programmers)
        ProgrammerGrant.objects.create(user=self.target_user)
        form = self._make_form(**{"user-programmer": False})
        self.assertTrue(form.is_valid(), form.errors)
        form.save(granted_by=self.admin)
        self.assertFalse(ProgrammerGrant.objects.filter(user=self.target_user).exists())


class ToolkitAccessViewTests(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("toolkit-access")

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_volunteer_can_access(self):
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_panopticon_can_access(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_page_lists_panopticon_users(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url)
        # admin is a superuser; should appear
        self.assertContains(response, "admin")

    def test_page_shows_rights_table(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url)
        self.assertContains(response, "Programmer")
        self.assertContains(response, "Panopticon")
        self.assertContains(response, "Volunteer")


class MarkPanopticonReviewedTests(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.get(username="admin")
        self.grant = PanopticonGrant.objects.create(
            user=self.admin, reason="Original reason"
        )
        self.url = reverse("toolkit-access-review", kwargs={"grant_id": self.grant.pk})

    def test_mark_reviewed_sets_date(self):
        self.client.login(username="admin", password="T3stPassword!")
        self.client.post(self.url)
        self.grant.refresh_from_db()
        self.assertEqual(self.grant.last_reviewed_at, datetime.date.today())
        self.assertEqual(self.grant.reviewed_by, self.admin)

    def test_requires_panopticon(self):
        self.client.login(username="vol1", password="testpass")
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)
        self.grant.refresh_from_db()
        self.assertIsNone(self.grant.last_reviewed_at)
