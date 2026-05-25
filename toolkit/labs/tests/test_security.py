# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import copy
import os

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .common import LabsTestsMixin

_SS_TEMPLATES = copy.deepcopy(settings.TEMPLATES)
_SS_TEMPLATES[0]["DIRS"] = (
    os.path.join(settings.BASE_DIR, "star_and_shadow_templates"),
) + tuple(_SS_TEMPLATES[0]["DIRS"])


class LabsSecurityTests(LabsTestsMixin, TestCase):
    """Auth and permission enforcement for all labs endpoints."""

    def _login_url(self, url):
        return reverse("login", query={"next": url})

    def _assert_anon_redirects(self, view_name, kwargs=None, method="get"):
        url = reverse(view_name, kwargs=kwargs or {})
        response = getattr(self.client, method)(url)
        self.assertRedirects(
            response,
            self._login_url(url),
            msg_prefix=f"anon {method.upper()} {view_name}",
        )

    # ── Anonymous users → redirect to login ───────────────────────────────

    def test_anon_cannot_access_collectives(self):
        self._assert_anon_redirects("labs-collectives")
        self._assert_anon_redirects("labs-collectives", method="post")

    def test_anon_cannot_access_collectives_print(self):
        self._assert_anon_redirects("labs-collectives-print")

    def test_anon_cannot_access_collective_edit(self):
        self._assert_anon_redirects("labs-collective-edit", {"slug": self.col_open.slug})

    def test_anon_cannot_join_collective(self):
        self._assert_anon_redirects(
            "labs-collective-join", {"slug": self.col_open.slug}, method="post"
        )

    def test_anon_cannot_leave_collective(self):
        self._assert_anon_redirects(
            "labs-collective-leave", {"slug": self.col_open.slug}, method="post"
        )

    def test_anon_cannot_access_floorplan(self):
        self._assert_anon_redirects("labs-floorplan")

    def test_anon_cannot_access_room_note(self):
        self._assert_anon_redirects("labs-room-note", {"room_id": "room-cinema"})

    def test_anon_cannot_access_donation_manage(self):
        self._assert_anon_redirects("labs-donations-manage")
        self._assert_anon_redirects("labs-donations-manage", method="post")

    def test_anon_cannot_access_job_list(self):
        self._assert_anon_redirects("labs-jobs")

    def test_anon_cannot_access_job_add(self):
        self._assert_anon_redirects("labs-job-add")

    def test_anon_cannot_access_job_edit(self):
        self._assert_anon_redirects("labs-job-edit", {"job_id": self.job_open.pk})

    def test_anon_cannot_claim_job(self):
        self._assert_anon_redirects(
            "labs-job-claim", {"job_id": self.job_open.pk}, method="post"
        )

    def test_anon_cannot_unclaim_job(self):
        self._assert_anon_redirects(
            "labs-job-unclaim", {"job_id": self.job_claimed.pk}, method="post"
        )

    def test_anon_cannot_resolve_job(self):
        self._assert_anon_redirects(
            "labs-job-resolve", {"job_id": self.job_open.pk}, method="post"
        )

    def test_anon_cannot_access_bulletins(self):
        self._assert_anon_redirects("labs-bulletins")

    def test_anon_cannot_access_bulletin_archive(self):
        self._assert_anon_redirects("labs-bulletins-archive")

    def test_anon_cannot_access_bulletin_add(self):
        self._assert_anon_redirects("labs-bulletin-add")

    # ── POST-only views: GET returns 405 for logged-in users ──────────────

    def test_collective_join_get_returns_405(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-collective-join", kwargs={"slug": self.col_open.slug})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_collective_leave_get_returns_405(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-collective-leave", kwargs={"slug": self.col_open.slug})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_job_claim_get_returns_405(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-job-claim", kwargs={"job_id": self.job_open.pk})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_job_unclaim_get_returns_405(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-job-unclaim", kwargs={"job_id": self.job_claimed.pk})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_job_resolve_get_returns_405(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-job-resolve", kwargs={"job_id": self.job_open.pk})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_bulletin_pin_get_returns_405(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-bulletin-pin", kwargs={"bulletin_id": self.bulletin.pk})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_bulletin_delete_get_returns_405(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-bulletin-delete", kwargs={"bulletin_id": self.bulletin.pk})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_bulletin_read_all_get_returns_405(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-bulletins-read-all")
        self.assertEqual(self.client.get(url).status_code, 405)

    # ── toolkit.write required (403 for logged-in without write perm) ─────

    def test_no_write_cannot_access_donation_manage(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("labs-donations-manage")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_no_write_cannot_add_job(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("labs-job-add")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_no_write_cannot_edit_job(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("labs-job-edit", kwargs={"job_id": self.job_open.pk})
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_no_write_cannot_pin_bulletin(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("labs-bulletin-pin", kwargs={"bulletin_id": self.bulletin.pk})
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_no_write_cannot_expire_bulletin(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("labs-bulletin-expire", kwargs={"bulletin_id": self.bulletin.pk})
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_non_superuser_cannot_delete_bulletin(self):
        # bulletin_delete checks is_superuser manually inside the view
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-bulletin-delete", kwargs={"bulletin_id": self.bulletin.pk})
        self.assertEqual(self.client.post(url).status_code, 403)

    # ── Public endpoints: no auth required ───────────────────────────────

    def test_public_collectives_page_accessible_without_login(self):
        url = reverse("labs-collectives-public")
        with self.settings(TEMPLATES=_SS_TEMPLATES):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_donations_list_accessible_without_login(self):
        url = reverse("labs-donations")
        self.assertEqual(self.client.get(url).status_code, 200)
