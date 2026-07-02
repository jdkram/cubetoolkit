# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
"""Core induction flows: sign-up, capacity, attendance, account creation, export.

These cover the mechanical behaviour that previously had to be checked by hand,
including the specific points raised during manual testing (slug not doubling the
year, username format, capacity enforcement).
"""
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from toolkit.inductions.models import (
    InductionSession,
    InductionSignup,
    InductionsSettings,
)
from toolkit.inductions.tests.common import InductionsTestsMixin
from toolkit.inductions.views import _create_volunteer_from_signup
from toolkit.members.models import Member, Volunteer


def _mk_signup(session, name, email=""):
    return InductionSignup.objects.create(session=session, name=name, email=email)


class SlugGeneration(InductionsTestsMixin, TestCase):
    def test_year_not_doubled_when_title_contains_year(self):
        """Regression: title with a year + a %Y date format produced '...2026-2026-08-02'."""
        s = InductionSession.objects.create(
            title="Volunteer Induction August 2026",
            date=timezone.make_aware(timezone.datetime(2026, 8, 2, 18, 0)),
        )
        self.assertEqual(s.slug.count("2026"), 1)
        self.assertEqual(s.slug, "volunteer-induction-august-2026-08-02")

    def test_slugs_are_unique(self):
        a = InductionSession.objects.create(title="Same", date=timezone.now())
        b = InductionSession.objects.create(title="Same", date=timezone.now())
        self.assertNotEqual(a.slug, b.slug)


class PublicSignup(InductionsTestsMixin, TestCase):
    def test_valid_signup_creates_record(self):
        url = self.session.get_signup_url() if hasattr(self.session, "get_signup_url") else None
        from django.urls import reverse
        url = reverse("inductions:signup", args=[self.session.slug])
        resp = self.client.post(url, self.valid_signup_post())
        self.assertEqual(resp.status_code, 302)
        signup = self.session.signups.get(email="bob@test.example")
        self.assertEqual(signup.name, "Bob Jones")
        self.assertEqual(signup.status, InductionSignup.STATUS_PENDING)

    def test_consent_required(self):
        from django.urls import reverse
        url = reverse("inductions:signup", args=[self.session.slug])
        resp = self.client.post(url, self.valid_signup_post(consent=""))
        self.assertEqual(resp.status_code, 200)  # re-rendered with errors
        self.assertFalse(self.session.signups.filter(email="bob@test.example").exists())

    def test_age_confirm_required(self):
        from django.urls import reverse
        url = reverse("inductions:signup", args=[self.session.slug])
        resp = self.client.post(url, self.valid_signup_post(age_confirm=""))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(self.session.signups.filter(email="bob@test.example").exists())

    def test_closed_session_not_signable(self):
        from django.urls import reverse
        self.session.status = InductionSession.STATUS_CLOSED
        self.session.save()
        url = reverse("inductions:signup", args=[self.session.slug])
        self.assertEqual(self.client.get(url).status_code, 404)


class Capacity(InductionsTestsMixin, TestCase):
    def test_effective_capacity_reflects_session_value(self):
        self.session.max_signups = 2
        self.session.save()
        self.assertEqual(self.session.effective_capacity(), 2)

    def test_effective_capacity_unlimited_when_blank(self):
        # default_max_signups is only used to pre-fill the edit form's initial
        # value — a session with max_signups explicitly None is unlimited,
        # regardless of the site-wide default.
        cfg = InductionsSettings.load()
        cfg.default_max_signups = 3
        cfg.save()
        self.session.max_signups = None
        self.session.save()
        self.assertIsNone(self.session.effective_capacity())

    def test_full_session_shows_full_page(self):
        from django.urls import reverse
        self.session.max_signups = 1  # already has one signup from the mixin
        self.session.save()
        self.assertTrue(self.session.is_full)
        resp = self.client.get(reverse("inductions:signup", args=[self.session.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "inductions/signup_full.html")

    def test_full_session_rejects_signup_post(self):
        from django.urls import reverse
        self.session.max_signups = 1
        self.session.save()
        url = reverse("inductions:signup", args=[self.session.slug])
        self.client.post(url, self.valid_signup_post())
        self.assertFalse(self.session.signups.filter(email="bob@test.example").exists())

    def test_over_cap_banner_hidden_within_cap(self):
        from django.urls import reverse
        self.session.max_signups = 5  # only 1 signup (from the mixin) exists
        self.session.save()
        self.login_admin()
        resp = self.client.get(reverse("inductions:manage_session_detail", args=[self.session.slug]))
        self.assertNotContains(resp, "over the cap")

    def test_over_cap_banner_shown_and_last_signups_flagged(self):
        from django.urls import reverse
        self.session.max_signups = 1  # lowered after signups already exist
        self.session.save()
        InductionSignup.objects.create(session=self.session, name="Late One", email="late1@test.example")
        InductionSignup.objects.create(session=self.session, name="Late Two", email="late2@test.example")
        self.login_admin()
        resp = self.client.get(reverse("inductions:manage_session_detail", args=[self.session.slug]))
        self.assertContains(resp, "2 over the cap")
        # The two most recent sign-ups are flagged over-cap; the original mixin signup is not.
        over_cap_ids = {s.pk for s in resp.context["signups"] if s.is_over_cap}
        self.assertEqual(
            over_cap_ids,
            set(self.session.signups.exclude(pk=self.signup.pk).values_list("pk", flat=True)),
        )

    def test_set_cap_updates_session(self):
        from django.urls import reverse
        self.login_admin()
        url = reverse("inductions:manage_session_set_cap", args=[self.session.slug])
        resp = self.client.post(url, {"max_signups": "4"})
        self.assertEqual(resp.json(), {"ok": True, "max_signups": 4})
        self.session.refresh_from_db()
        self.assertEqual(self.session.max_signups, 4)

    def test_set_cap_blank_clears_to_unlimited(self):
        from django.urls import reverse
        self.session.max_signups = 4
        self.session.save()
        self.login_admin()
        url = reverse("inductions:manage_session_set_cap", args=[self.session.slug])
        resp = self.client.post(url, {"max_signups": ""})
        self.assertEqual(resp.json(), {"ok": True, "max_signups": None})
        self.session.refresh_from_db()
        self.assertIsNone(self.session.max_signups)

    def test_set_cap_rejects_negative(self):
        from django.urls import reverse
        self.login_admin()
        url = reverse("inductions:manage_session_set_cap", args=[self.session.slug])
        resp = self.client.post(url, {"max_signups": "-1"})
        self.assertFalse(resp.json()["ok"])
        self.session.refresh_from_db()
        self.assertIsNone(self.session.max_signups)


class SessionFormCapacityPrefill(InductionsTestsMixin, TestCase):
    def test_new_session_form_prefills_max_signups_with_site_default(self):
        from toolkit.inductions.forms import InductionSessionForm
        cfg = InductionsSettings.load()
        cfg.default_max_signups = 6
        cfg.save()
        form = InductionSessionForm()
        self.assertEqual(form.fields["max_signups"].initial, 6)

    def test_edit_form_prefills_max_signups_when_blank_on_session(self):
        from toolkit.inductions.forms import InductionSessionForm
        cfg = InductionsSettings.load()
        cfg.default_max_signups = 8
        cfg.save()
        self.session.max_signups = None
        self.session.save()
        form = InductionSessionForm(instance=self.session)
        self.assertEqual(form.fields["max_signups"].initial, 8)

    def test_edit_form_does_not_override_existing_session_value(self):
        from toolkit.inductions.forms import InductionSessionForm
        cfg = InductionsSettings.load()
        cfg.default_max_signups = 8
        cfg.save()
        self.session.max_signups = 2
        self.session.save()
        form = InductionSessionForm(instance=self.session)
        self.assertIsNone(form.fields["max_signups"].initial)


class UsernameGeneration(InductionsTestsMixin, TestCase):
    def test_two_part_name(self):
        v = _create_volunteer_from_signup(_mk_signup(self.session, "John Doe", "jd@test.example"))
        self.assertEqual(v.user.username, "JohnDoe")

    def test_middle_name_dropped(self):
        v = _create_volunteer_from_signup(_mk_signup(self.session, "Mary Anne Smith", "ms@test.example"))
        self.assertEqual(v.user.username, "MarySmith")

    def test_single_name(self):
        v = _create_volunteer_from_signup(_mk_signup(self.session, "Cher", "cher@test.example"))
        self.assertEqual(v.user.username, "Cher")

    def test_collision_suffixed(self):
        a = _create_volunteer_from_signup(_mk_signup(self.session, "John Doe", "jd1@test.example"))
        b = _create_volunteer_from_signup(_mk_signup(self.session, "John Doe", "jd2@test.example"))
        self.assertEqual(a.user.username, "JohnDoe")
        self.assertEqual(b.user.username, "JohnDoe-1")

    def test_desired_username_respected(self):
        s = _mk_signup(self.session, "John Doe", "jd@test.example")
        s.desired_username = "johnny"
        s.save()
        v = _create_volunteer_from_signup(s)
        self.assertEqual(v.user.username, "johnny")


class Attendance(InductionsTestsMixin, TestCase):
    def test_mark_attendance_toggles(self):
        from django.urls import reverse
        self.login_admin()
        url = reverse("inductions:manage_mark_attendance", args=[self.session.slug, self.signup.pk])
        self.client.post(url)
        self.signup.refresh_from_db()
        self.assertEqual(self.signup.status, InductionSignup.STATUS_CHECKED_IN)
        self.client.post(url)
        self.signup.refresh_from_db()
        self.assertEqual(self.signup.status, InductionSignup.STATUS_PENDING)


class CreateAccounts(InductionsTestsMixin, TestCase):
    def _check_in(self, signup):
        signup.status = InductionSignup.STATUS_CHECKED_IN
        signup.save()

    def test_creates_volunteer_for_checked_in(self):
        from django.urls import reverse
        self._check_in(self.signup)
        self.login_admin()
        url = reverse("inductions:manage_create_accounts", args=[self.session.slug])
        self.client.post(url)
        self.signup.refresh_from_db()
        self.assertIsNotNone(self.signup.volunteer_id)
        self.assertTrue(Volunteer.objects.filter(pk=self.signup.volunteer_id).exists())

    def test_pending_signup_not_processed(self):
        from django.urls import reverse
        self.login_admin()  # self.signup is still PENDING
        url = reverse("inductions:manage_create_accounts", args=[self.session.slug])
        self.client.post(url)
        self.signup.refresh_from_db()
        self.assertIsNone(self.signup.volunteer_id)

    def test_duplicate_email_surfaced_not_created(self):
        from django.urls import reverse
        # Existing volunteer with the same email as the signup
        mem = Member.objects.create(name="Existing Person", email="dup@test.example")
        user = User.objects.create_user("existing", "dup@test.example", "x")
        Volunteer.objects.create(member=mem, user=user)

        dup = _mk_signup(self.session, "New Person", "dup@test.example")
        self._check_in(dup)
        self.login_admin()
        url = reverse("inductions:manage_create_accounts", args=[self.session.slug])
        resp = self.client.post(url)
        dup.refresh_from_db()
        self.assertIsNone(dup.volunteer_id)  # not created — flagged as duplicate
        self.assertContains(resp, "dup@test.example")

    def test_force_creates_despite_duplicate(self):
        from django.urls import reverse
        mem = Member.objects.create(name="Existing Person", email="dup2@test.example")
        user = User.objects.create_user("existing2", "dup2@test.example", "x")
        Volunteer.objects.create(member=mem, user=user)

        dup = _mk_signup(self.session, "New Person", "dup2@test.example")
        self._check_in(dup)
        self.login_admin()
        url = reverse("inductions:manage_create_accounts", args=[self.session.slug])
        self.client.post(url, {"force_signup_ids": str(dup.pk)})
        dup.refresh_from_db()
        self.assertIsNotNone(dup.volunteer_id)


class Walkin(InductionsTestsMixin, TestCase):
    def test_walkin_requires_first_name(self):
        from django.urls import reverse
        self.login_admin()
        url = reverse("inductions:manage_add_walkin", args=[self.session.slug])
        resp = self.client.post(url, {"first_name": "", "email": "x@test.example"})
        self.assertFalse(resp.json()["ok"])

    def test_walkin_creates_pending_signup(self):
        from django.urls import reverse
        self.login_admin()
        url = reverse("inductions:manage_add_walkin", args=[self.session.slug])
        resp = self.client.post(url, {"first_name": "Eve", "last_name": "Taylor", "email": "eve@test.example"})
        self.assertTrue(resp.json()["ok"])
        s = self.session.signups.get(email="eve@test.example")
        self.assertEqual(s.name, "Eve Taylor")
        self.assertEqual(s.status, InductionSignup.STATUS_PENDING)


class CsvExport(InductionsTestsMixin, TestCase):
    def test_export_is_headerless_first_last_email_for_checked_in(self):
        from django.urls import reverse
        # one checked-in, one pending — only the checked-in should appear
        ci = _mk_signup(self.session, "Dana Lee", "dana@test.example")
        ci.status = InductionSignup.STATUS_CHECKED_IN
        ci.save()
        self.login_admin()
        url = reverse("inductions:manage_export_csv", args=[self.session.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode().strip().splitlines()
        self.assertEqual(body, ["Dana,Lee,dana@test.example"])
