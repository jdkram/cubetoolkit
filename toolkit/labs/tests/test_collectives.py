# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import copy
import os

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from toolkit.labs.models import Collective

from .common import LabsTestsMixin

# Add star_and_shadow_templates to TEMPLATES so the public collectives view
# can find its template (which lives there, not in the base templates/ dir).
_SS_TEMPLATES = copy.deepcopy(settings.TEMPLATES)
_SS_TEMPLATES[0]["DIRS"] = (
    os.path.join(settings.BASE_DIR, "star_and_shadow_templates"),
) + tuple(_SS_TEMPLATES[0]["DIRS"])


class CollectivesPublicTests(LabsTestsMixin, TestCase):
    """Public collectives directory — no login required."""

    def _get_public(self):
        with self.settings(TEMPLATES=_SS_TEMPLATES):
            return self.client.get(reverse("labs-collectives-public"))

    def test_shows_listed_collective_with_public_copy(self):
        response = self._get_public()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.col_public.name)
        self.assertContains(response, self.col_public.public_copy)

    def test_hides_unlisted_collective(self):
        response = self._get_public()
        self.assertNotContains(response, self.col_open.name)

    def test_hides_inactive_collective_even_if_listed(self):
        self.col_inactive.listed_publicly = True
        self.col_inactive.public_copy = "We used to exist."
        self.col_inactive.save()
        response = self._get_public()
        self.assertNotContains(response, self.col_inactive.name)

    def test_hides_collective_with_empty_public_copy(self):
        # listed_publicly=True but public_copy="" → excluded by view's .exclude(public_copy="")
        self.col_open.listed_publicly = True
        self.col_open.public_copy = ""
        self.col_open.save()
        response = self._get_public()
        self.assertNotContains(response, self.col_open.name)


class CollectivesInternalTests(LabsTestsMixin, TestCase):
    """Internal collectives view — login required."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_lists_all_active_collectives(self):
        response = self.client.get(reverse("labs-collectives"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.col_open.name)
        self.assertContains(response, self.col_invite.name)

    def test_does_not_show_inactive_collective(self):
        response = self.client.get(reverse("labs-collectives"))
        self.assertNotContains(response, self.col_inactive.name)

    def test_print_view_loads(self):
        response = self.client.get(reverse("labs-collectives-print"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.col_open.name)


class CollectiveJoinTests(LabsTestsMixin, TestCase):
    """Volunteer can join open collectives."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_volunteer_can_join_open_collective(self):
        url = reverse("labs-collective-join", kwargs={"slug": self.col_open.slug})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-collectives"))
        self.assertIn(self.col_open, self.user_vol.volunteer.collectives.all())

    def test_joining_again_is_harmless(self):
        self.user_vol.volunteer.collectives.add(self.col_open)
        url = reverse("labs-collective-join", kwargs={"slug": self.col_open.slug})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-collectives"))
        # Still in the collective, no duplicate
        self.assertEqual(
            self.user_vol.volunteer.collectives.filter(slug="film").count(), 1
        )

    def test_cannot_join_invite_only_collective(self):
        url = reverse("labs-collective-join", kwargs={"slug": self.col_invite.slug})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-collectives"))
        self.assertNotIn(self.col_invite, self.user_vol.volunteer.collectives.all())

    def test_user_without_volunteer_profile_gets_error_message(self):
        self.client.logout()
        self.client.login(username="no_perm", password="T3stPassword!2")
        url = reverse("labs-collective-join", kwargs={"slug": self.col_open.slug})
        response = self.client.post(url, follow=True)
        self.assertContains(response, "volunteer profile")

    def test_join_inactive_collective_returns_404(self):
        url = reverse("labs-collective-join", kwargs={"slug": self.col_inactive.slug})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class CollectiveLeaveTests(LabsTestsMixin, TestCase):
    """Volunteer can leave collectives they're in."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")
        self.user_vol.volunteer.collectives.add(self.col_open)

    def test_volunteer_can_leave_collective(self):
        url = reverse("labs-collective-leave", kwargs={"slug": self.col_open.slug})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-collectives"))
        self.assertNotIn(self.col_open, self.user_vol.volunteer.collectives.all())

    def test_leaving_collective_not_in_is_harmless(self):
        # leave an unjoined collective — should not error
        url = reverse("labs-collective-leave", kwargs={"slug": self.col_invite.slug})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-collectives"))


class CollectiveEditTests(LabsTestsMixin, TestCase):
    """Collective edit form — any logged-in user can edit collective info."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")
        self.url = reverse("labs-collective-edit", kwargs={"slug": self.col_open.slug})

    def test_get_edit_form_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.col_open.name)

    def test_edit_inactive_collective_returns_404(self):
        url = reverse("labs-collective-edit", kwargs={"slug": self.col_inactive.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_post_updates_collective_and_sets_updated_by(self):
        # CollectiveForm fields (name/slug are excluded from the form — they're set by admins)
        # Include the CollectiveLinkFormSet management form to keep the formset valid
        data = {
            "colour": "#0d2b45",
            "volunteer_count": "About 10",
            "about": "We screen films.",
            "roles": "Screening, projection",
            "organising": "Monthly meetings",
            "proud_of": "Great taste",
            "get_involved": "Come to a screening",
            "contact": "film@test.example",
            "listed_publicly": "",
            "public_copy": "",
            # CollectiveLinkFormSet management form (prefix comes from related_name="links")
            "links-TOTAL_FORMS": "3",
            "links-INITIAL_FORMS": "0",
            "links-MIN_NUM_FORMS": "0",
            "links-MAX_NUM_FORMS": "3",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("labs-collectives"))
        self.col_open.refresh_from_db()
        self.assertEqual(self.col_open.volunteer_count, "About 10")
        self.assertEqual(self.col_open.updated_by, self.user_vol)
