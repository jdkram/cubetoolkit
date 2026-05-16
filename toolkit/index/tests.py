import zoneinfo
from datetime import datetime, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

import django.contrib.auth.models as auth_models
import django.contrib.contenttypes as contenttypes

from toolkit.diary.models import Event, Role, RotaEntry, Showing, VolunteerEventMark
from toolkit.index.models import IndexLink, IndexCategory
from toolkit.members.models import Member, Volunteer

UKTZ = zoneinfo.ZoneInfo("Europe/London")


class SecurityTests(TestCase):
    """Test that write permission is required"""

    def test_private_urls(self):
        """All URLs which should 302 redirect to the login page"""
        views_to_test = {
            "toolkit-index": {},
            "create-index-link": {},
            "update-index-link": {"pk": "1"},
            "delete-index-link": {"pk": "1"},
            "create-index-category": {},
            "update-index-category": {"pk": "1"},
        }
        for view_name, kwargs in views_to_test.items():
            url = reverse(view_name, kwargs=kwargs)
            expected_redirect = reverse("login", query={"next": url})

            # Test GET:
            response = self.client.get(url)
            self.assertRedirects(response, expected_redirect)

            # Test POST:
            response = self.client.post(url)
            self.assertRedirects(response, expected_redirect)


class TestViews(TestCase):
    # Fairly incomplete set of tests, but good enough

    def setUp(self):
        self.cat1 = IndexCategory(name="Category 1 Links!")
        self.cat1.save()

        cat2 = IndexCategory(name="Category 2 Links!")
        cat2.save()

        cat3 = IndexCategory(name="Sad, empty category")
        cat3.save()

        l1 = IndexLink(text="Link one", link="http://link1.test.com/")
        l1.category = self.cat1
        l1.save()

        l2 = IndexLink(text="Two Link", link="http://cubecinema.com/")
        l2.category = cat2
        l2.save()

        l3 = IndexLink(
            text="THIRD LINK", link="http://cubecinema.com/blah-de-blah"
        )
        l3.category = cat2
        l3.save()

        # System user:
        user_rw = auth_models.User.objects.create_user(
            "admin", "toolkit_admin@localhost", "T3stPassword!"
        )
        # Create dummy ContentType:
        ct = contenttypes.models.ContentType.objects.get_or_create(
            model="", app_label="toolkit"
        )[0]
        # Create 'write' permission:
        write_permission = auth_models.Permission.objects.get_or_create(
            name="Write access to all toolkit content",
            content_type=ct,
            codename="write",
        )[0]
        # Give "admin" user the write permission:
        user_rw.user_permissions.add(write_permission)

        # And login:
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def tearDown(self):
        self.client.logout()

    def test_get_index(self):
        url = reverse("toolkit-index")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed("toolkit_index.html")

    def test_create_link(self):
        link_name = "Superior quality link"
        link_url = "http://i.like.an.example.com"
        url = reverse("create-index-link")
        response = self.client.get(url)
        # check form loads
        self.assertEqual(response.status_code, 200)

        # check create works:
        response = self.client.post(
            url,
            data={
                "text": link_name,
                "link": link_url,
                "category": 1,
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        link = IndexLink.objects.get(id=4)
        self.assertEqual(link.text, link_name)
        self.assertEqual(link.link, link_url)
        self.assertEqual(link.category, self.cat1)

    def test_create_link_with_description(self):
        url = reverse("create-index-link")
        description_text = "Login with your member credentials"
        response = self.client.post(
            url,
            data={
                "text": "Members login",
                "link": "http://members.example.com/login",
                "category": 1,
                "description": description_text,
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        link = IndexLink.objects.get(id=4)
        self.assertEqual(link.description, description_text)

    def test_edit_link(self):
        url = reverse("update-index-link", kwargs={"pk": "1"})
        response = self.client.post(
            url,
            data={
                "text": "All new link text!",
                "link": "http://boring.com/",
                "category": "2",
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        link = IndexLink.objects.get(id=1)
        self.assertEqual(link.text, "All new link text!")
        self.assertEqual(link.link, "http://boring.com/")
        self.assertEqual(link.category_id, 2)

    def test_edit_link_with_description(self):
        url = reverse("update-index-link", kwargs={"pk": "1"})
        description_text = "Use the emergency password if normal login fails"
        response = self.client.post(
            url,
            data={
                "text": "Link one updated",
                "link": "http://link1.test.com/",
                "category": "1",
                "description": description_text,
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        link = IndexLink.objects.get(id=1)
        self.assertEqual(link.description, description_text)

    def test_description_rendered_on_index(self):
        link = IndexLink.objects.get(id=1)
        link.description = "Helpful instructions here"
        link.save()

        url = reverse("toolkit-index")
        response = self.client.get(url)
        self.assertContains(response, "Helpful instructions here")

    def test_create_category(self):
        category_name = "My new category of fish"
        # url = reverse("create-index-link", kwargs={"pk": "1"})
        url = reverse("create-index-category")
        response = self.client.get(url)
        # check form loads
        self.assertEqual(response.status_code, 200)

        # check create works:
        response = self.client.post(
            url,
            data={
                "name": category_name,
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        category = IndexCategory.objects.get(id=4)
        self.assertEqual(category.name, category_name)

    def test_edit_category(self):
        url = reverse("update-index-category", kwargs={"pk": "1"})
        response = self.client.post(
            url,
            data={
                "name": "Category is called what, now?",
            },
        )
        self.assertRedirects(response, reverse("toolkit-index"))

        cat = IndexCategory.objects.get(id=1)
        self.assertEqual(cat.name, "Category is called what, now?")

    def test_edit_category_invalid_name_blank(self):
        url = reverse("update-index-category", kwargs={"pk": "1"})
        response = self.client.post(
            url,
            data={
                "name": "   ",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "name", "This field is required."
        )

        cat = IndexCategory.objects.get(id=1)
        self.assertEqual(cat.name, "Category 1 Links!")

    def test_edit_category_invalid_name_missing(self):
        url = reverse("update-index-category", kwargs={"pk": "1"})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "name", "This field is required."
        )


def _make_volunteer_user(username: str, password: str = "T3stPassword!") -> tuple[auth_models.User, Volunteer]:
    member = Member.objects.create(name=f"{username} Test", email=f"{username}@example.com")
    user = auth_models.User.objects.create_user(username, email=f"{username}@example.com", password=password)
    volunteer = Volunteer.objects.create(member=member, user=user)
    return user, volunteer


def _make_showing(days_ahead: int = 7, confirmed: bool = True) -> Showing:
    now = timezone.now()
    event = Event.objects.create(name=f"Test Event {days_ahead}d")
    showing = Showing.objects.create(
        event=event,
        start=now + timedelta(days=days_ahead),
        confirmed=confirmed,
    )
    return showing


class TestDashboardWidgets(TestCase):
    def setUp(self):
        # Write permission setup (mirrors TestViews.setUp)
        ct = contenttypes.models.ContentType.objects.get_or_create(
            model="", app_label="toolkit"
        )[0]
        self.write_perm = auth_models.Permission.objects.get_or_create(
            name="Write access to all toolkit content",
            content_type=ct,
            codename="write",
        )[0]
        self.url = reverse("toolkit-index")

    def _login(self, user: auth_models.User) -> None:
        self.client.login(username=user.username, password="T3stPassword!")

    def test_no_volunteer_record_no_shift_widgets(self):
        # A user without a Volunteer record should not see shift/starred widgets
        user = auth_models.User.objects.create_user("plain", password="T3stPassword!")
        self._login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("has_volunteer", response.context)
        self.assertNotIn("upcoming_shifts", response.context)
        self.assertNotIn("starred_events", response.context)

    def test_upcoming_shifts_empty_when_no_rota_entries(self):
        user, _volunteer = _make_volunteer_user("vol1")
        self._login(user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("upcoming_shifts", response.context)
        self.assertEqual(list(response.context["upcoming_shifts"]), [])

    def test_upcoming_shifts_shows_confirmed_future_entry(self):
        user, volunteer = _make_volunteer_user("vol2")
        role = Role.objects.create(name="Test Role", read_only=False, standard=True)
        showing = _make_showing(days_ahead=3, confirmed=True)
        RotaEntry.objects.create(showing=showing, role=role, volunteer=volunteer, name=volunteer.member.name)
        self._login(user)
        response = self.client.get(self.url)
        shifts = response.context["upcoming_shifts"]
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].showing, showing)

    def test_upcoming_shifts_excludes_unconfirmed(self):
        user, volunteer = _make_volunteer_user("vol3")
        role = Role.objects.create(name="Test Role 2", read_only=False, standard=True)
        showing = _make_showing(days_ahead=3, confirmed=False)
        RotaEntry.objects.create(showing=showing, role=role, volunteer=volunteer, name=volunteer.member.name)
        self._login(user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["upcoming_shifts"]), [])

    def test_starred_events_shows_events_with_future_showings(self):
        user, volunteer = _make_volunteer_user("vol4")
        showing = _make_showing(days_ahead=10)
        VolunteerEventMark.objects.create(
            volunteer=volunteer, event=showing.event, mark_type=VolunteerEventMark.MARK_STAR
        )
        self._login(user)
        response = self.client.get(self.url)
        starred = response.context["starred_events"]
        self.assertEqual(len(starred), 1)
        self.assertEqual(starred[0].event, showing.event)

    def test_starred_events_card_shown_with_empty_state_when_no_stars(self):
        user, _volunteer = _make_volunteer_user("vol4b")
        self._login(user)
        response = self.client.get(self.url)
        self.assertIn("starred_events", response.context)
        self.assertEqual(list(response.context["starred_events"]), [])
        self.assertContains(response, "Star events on the")
        self.assertContains(response, "rota")

    def test_starred_events_excludes_past_showings(self):
        user, volunteer = _make_volunteer_user("vol5")
        # FutureDateTimeField blocks saving in the past; create future then move back.
        showing = _make_showing(days_ahead=1)
        Showing.objects.filter(pk=showing.pk).update(
            start=timezone.now() - timedelta(days=2)
        )
        VolunteerEventMark.objects.create(
            volunteer=volunteer, event=showing.event, mark_type=VolunteerEventMark.MARK_STAR
        )
        self._login(user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["starred_events"]), [])

    def test_starred_events_excludes_shadow_marks(self):
        user, volunteer = _make_volunteer_user("vol6")
        showing = _make_showing(days_ahead=5)
        VolunteerEventMark.objects.create(
            volunteer=volunteer, event=showing.event, mark_type=VolunteerEventMark.MARK_SHADOW
        )
        self._login(user)
        response = self.client.get(self.url)
        self.assertEqual(list(response.context["starred_events"]), [])

    def test_new_showings_visible_to_programmer(self):
        user = auth_models.User.objects.create_user("prog1", password="T3stPassword!")
        user.user_permissions.add(self.write_perm)
        user.save()
        showing = _make_showing(days_ahead=7)
        self._login(user)
        # client.login() sets last_login to now (after creation); push it back
        # so the showing's created_at falls within the lookback window.
        auth_models.User.objects.filter(pk=user.pk).update(
            last_login=timezone.now() - timedelta(hours=1)
        )
        response = self.client.get(self.url)
        self.assertIn("new_showings", response.context)
        pks = [s.pk for s in response.context["new_showings"]]
        self.assertIn(showing.pk, pks)

    def test_new_showings_not_in_context_for_volunteer(self):
        user, _vol = _make_volunteer_user("vol7")
        _make_showing(days_ahead=7)
        self._login(user)
        response = self.client.get(self.url)
        self.assertNotIn("new_showings", response.context)

    def test_new_showings_uses_30day_fallback_when_no_last_login(self):
        # When last_login is None, fall back to 30-day lookback rather than skipping.
        user = auth_models.User.objects.create_user("prog2", password="T3stPassword!")
        user.user_permissions.add(self.write_perm)
        user.save()
        showing = _make_showing(days_ahead=7)
        self._login(user)
        # Force last_login back to None to exercise the fallback path.
        auth_models.User.objects.filter(pk=user.pk).update(last_login=None)
        response = self.client.get(self.url)
        # Showing created during this test is within the 30-day window.
        self.assertIn("new_showings", response.context)
        pks = [s.pk for s in response.context["new_showings"]]
        self.assertIn(showing.pk, pks)
