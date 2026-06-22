from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import Event, Role, RotaEntry, Showing, SiteConfiguration, get_site_config
from toolkit.members.models import Member, Volunteer
from toolkit.members.tests.common import MembersTestsMixin


def _make_confirmed_showing(event, start, role, volunteer):
    showing = Showing.objects.create(
        event=event,
        start=start,
        confirmed=True,
        booked_by="Test",
    )
    RotaEntry.objects.create(
        showing=showing,
        role=role,
        volunteer=volunteer,
        required=True,
        rank=0,
    )
    return showing


class VolunteerStatsViewTests(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.delete(SiteConfiguration._CACHE_KEY)
        self.url_own = reverse("volunteer-stats")
        self.url_as = reverse("volunteer-stats-as", kwargs={"volunteer_id": self.vol_1.pk})
        self.role = Role.objects.create(name="Test Role", standard=True)
        self.event = Event.objects.create(name="Test Event")

    def _add_past_shifts(self, volunteer, n, role=None, event=None):
        role = role or self.role
        event = event or self.event
        base = timezone.now() - timedelta(days=400)
        for i in range(n):
            _make_confirmed_showing(event, base + timedelta(days=i * 7), role, volunteer)

    # ── Access ────────────────────────────────────────────────────────────────

    def test_own_stats_requires_login(self):
        response = self.client.get(self.url_own)
        self.assertNotEqual(response.status_code, 200)

    def test_own_stats_loads_for_volunteer(self):
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "history")

    def test_panopticon_can_view_other_volunteer(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(self.url_as)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panopticon view")

    def test_non_panopticon_cannot_view_other_volunteer(self):
        self.client.login(username="vol2", password="testpass")
        response = self.client.get(self.url_as)
        self.assertEqual(response.status_code, 403)

    # ── Zero shifts ───────────────────────────────────────────────────────────

    def test_zero_shifts_renders_gracefully(self):
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_shifts"], 0)
        self.assertContains(response, "No confirmed shifts")

    # ── Totals ────────────────────────────────────────────────────────────────

    def test_total_shifts_correct(self):
        self._add_past_shifts(self.vol_1, 7)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_shifts"], 7)

    def test_milestones_populated(self):
        self._add_past_shifts(self.vol_1, 25)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        ns = [m["n"] for m in response.context["milestones"]]
        self.assertIn(1, ns)
        self.assertIn(5, ns)
        self.assertIn(10, ns)
        self.assertIn(25, ns)
        self.assertNotIn(50, ns)

    def test_milestones_hidden_below_five_shifts(self):
        self._add_past_shifts(self.vol_1, 3)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertNotContains(response, "Moments in your history")

    # ── Role breakdown + stats_label ──────────────────────────────────────────

    def test_role_breakdown_groups_by_stats_label(self):
        role_a = Role.objects.create(name="Bar Shift 1", stats_label="Bar")
        role_b = Role.objects.create(name="Bar Shift 2", stats_label="Bar")
        self._add_past_shifts(self.vol_1, 3, role=role_a)
        self._add_past_shifts(self.vol_1, 2, role=role_b)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        labels = [r["label"] for r in response.context["role_breakdown"]]
        self.assertIn("Bar", labels)
        bar_row = next(r for r in response.context["role_breakdown"] if r["label"] == "Bar")
        self.assertEqual(bar_row["count"], 5)

    def test_role_breakdown_uses_name_when_no_label(self):
        self._add_past_shifts(self.vol_1, 4, role=self.role)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        labels = [r["label"] for r in response.context["role_breakdown"]]
        self.assertIn("Test Role", labels)

    # ── Programming gate ──────────────────────────────────────────────────────

    def test_programming_gate_met(self):
        self._add_past_shifts(self.vol_1, 10)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertTrue(response.context["programming_gate_met"])

    def test_programming_gate_not_met(self):
        self._add_past_shifts(self.vol_1, 9)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertFalse(response.context["programming_gate_met"])

    def test_programming_gate_excludes_training_tagged_events(self):
        from toolkit.diary.models import EventTag
        tag = EventTag.objects.create(name="induction", slug="induction")
        training_event = Event.objects.create(name="Induction Session")
        training_event.tags.add(tag)

        cfg = get_site_config()
        cfg.stats_training_tag_slugs = ["induction"]
        cfg.programming_min_event_shifts = 5
        cfg.save(update_fields=["stats_training_tag_slugs", "programming_min_event_shifts"])

        # 4 normal shifts + 3 training shifts = 4 event shifts (below threshold of 5)
        self._add_past_shifts(self.vol_1, 4)
        self._add_past_shifts(self.vol_1, 3, event=training_event)

        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        self.assertEqual(response.context["total_shifts"], 4)
        self.assertFalse(response.context["programming_gate_met"])

    # ── Heatmap ───────────────────────────────────────────────────────────────

    def test_heatmap_data_shape(self):
        self._add_past_shifts(self.vol_1, 5)
        self.client.login(username="vol1", password="testpass")
        response = self.client.get(self.url_own)
        heatmap_rows = response.context["heatmap_rows"]
        self.assertTrue(len(heatmap_rows) > 0)
        for row in heatmap_rows:
            self.assertIn("year", row)
            self.assertEqual(len(row["months"]), 12)
            for cell in row["months"]:
                self.assertIn("count", cell)
                self.assertIn("level", cell)
                self.assertIn(cell["level"], [0, 1, 2, 3, 4])
