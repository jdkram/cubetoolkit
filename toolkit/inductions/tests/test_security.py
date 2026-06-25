# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
"""Auth boundaries for every inductions endpoint.

Management views are Panopticon-only: anonymous users are redirected to login,
authenticated non-superusers get 403. Public views are reachable by anyone when
the feature is enabled, and 404 when it is switched off.
"""
from django.test import TestCase
from django.urls import reverse

from toolkit.inductions.models import InductionRequest, InductionsSettings
from toolkit.inductions.tests.common import InductionsTestsMixin


class ManageEndpointSecurity(InductionsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.req = InductionRequest.objects.create(
            name="Carol", email="carol@test.example", access_needs="Step-free access",
        )

    def _get_urls(self):
        s = self.session.slug
        return [
            reverse("inductions:manage_session_list"),
            reverse("inductions:manage_settings"),
            reverse("inductions:manage_session_new"),
            reverse("inductions:manage_access_needs_list"),
            reverse("inductions:manage_session_detail", args=[s]),
            reverse("inductions:manage_session_edit", args=[s]),
            reverse("inductions:manage_export_csv", args=[s]),
            reverse("inductions:manage_access_needs_detail", args=[self.req.pk]),
        ]

    def _post_urls(self):
        s = self.session.slug
        sid = self.signup.pk
        return [
            reverse("inductions:manage_session_close", args=[s]),
            reverse("inductions:manage_session_purge", args=[s]),
            reverse("inductions:manage_check_in", args=[s, sid]),
            reverse("inductions:manage_mark_attendance", args=[s, sid]),
            reverse("inductions:manage_create_accounts", args=[s]),
            reverse("inductions:manage_edit_signup", args=[s, sid]),
            reverse("inductions:manage_no_show", args=[s, sid]),
            reverse("inductions:manage_add_walkin", args=[s]),
            reverse("inductions:manage_link_existing", args=[s, sid]),
            reverse("inductions:manage_remove_signup", args=[s, sid]),
            reverse("inductions:manage_send_test_email"),
        ]

    def test_anonymous_redirected_to_login(self):
        for url in self._get_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        for url in self._post_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 302)

    def test_non_superuser_forbidden(self):
        self.login_nobody()
        for url in self._get_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in self._post_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_superuser_can_reach_get_pages(self):
        self.login_admin()
        for url in self._get_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class PublicEndpointGating(InductionsTestsMixin, TestCase):
    def test_public_pages_reachable_when_enabled(self):
        self.assertEqual(
            self.client.get(reverse("inductions:session_list_public")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("inductions:signup", args=[self.session.slug])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("inductions:access_needs_signup")).status_code, 200
        )

    def test_public_pages_404_when_disabled(self):
        cfg = InductionsSettings.load()
        cfg.inductions_enabled = False
        cfg.save()
        self.assertEqual(
            self.client.get(reverse("inductions:session_list_public")).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("inductions:signup", args=[self.session.slug])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("inductions:access_needs_signup")).status_code, 404
        )

    def test_manage_still_works_when_feature_disabled(self):
        """Panopticon management is deliberately not gated by inductions_enabled."""
        cfg = InductionsSettings.load()
        cfg.inductions_enabled = False
        cfg.save()
        self.login_admin()
        self.assertEqual(
            self.client.get(reverse("inductions:manage_session_list")).status_code, 200
        )

    def test_access_needs_404_when_access_needs_disabled(self):
        cfg = InductionsSettings.load()
        cfg.access_needs_enabled = False
        cfg.save()
        self.assertEqual(
            self.client.get(reverse("inductions:access_needs_signup")).status_code, 404
        )
