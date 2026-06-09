# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
import datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import Event, Showing
from toolkit.diary.tests.common import DiaryTestsMixin


def _make_queue_event(name, status, days_ahead=30):
    """Create a minimal event + showing in the queue."""
    event = Event(name=name, programming_status=status)
    event.save()
    start = timezone.now() + datetime.timedelta(days=days_ahead)
    showing = Showing(event=event, start=start)
    showing.save()
    return event


class ProgrammingQueueViewTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.draft = _make_queue_event("Draft Event", "draft")
        self.proposed = _make_queue_event("Proposed Event", "proposed", days_ahead=60)
        self.returned = _make_queue_event("Returned Event", "rejected", days_ahead=45)
        self.active = _make_queue_event("Active Event", "active")
        self.url = reverse("programming-queue")

    def test_get_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_read_only_user_can_view(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_get_shows_draft_proposed_returned(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Draft Event")
        self.assertContains(response, "Proposed Event")
        self.assertContains(response, "Returned Event")

    def test_get_excludes_active_events(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "Active Event")

    def test_empty_queue_shows_success_alert(self):
        Event.objects.filter(pk__in=[
            self.draft.pk, self.proposed.pk, self.returned.pk
        ]).update(programming_status="active")
        response = self.client.get(self.url)
        self.assertContains(response, "queue is empty")


class ProgrammingStatusUpdateTests(DiaryTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.event = _make_queue_event("Test Event", "draft")
        self.url = reverse("update-event-programming-status", kwargs={"event_id": self.event.pk})
        self.queue_url = reverse("programming-queue")

    def _post(self, action, notes=""):
        return self.client.post(self.url, {
            "action": action,
            "next": self.queue_url,
            "notes": notes,
        })

    def test_propose_sets_proposed(self):
        response = self._post("propose")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "proposed")
        self.assertIsNotNone(self.event.programming_status_changed_at)

    def test_withdraw_sets_draft(self):
        self.event.programming_status = "proposed"
        self.event.save()
        response = self._post("withdraw")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "draft")

    def test_return_for_changes_sets_rejected(self):
        self.event.programming_status = "proposed"
        self.event.save()
        response = self._post("return_for_changes", notes="Needs a budget breakdown.")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "rejected")
        self.assertIn("Needs a budget breakdown.", self.event.programming_notes)

    def test_approve_at_meeting_sets_active_with_approval_metadata(self):
        self.event.programming_status = "proposed"
        self.event.save()
        response = self._post("approve_at_meeting")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "active")
        self.assertEqual(self.event.approval_type, "meeting")
        self.assertIsNotNone(self.event.approved_at_meeting_date)

    def test_make_active_bypasses_meeting(self):
        response = self._post("make_active")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "active")
        self.assertNotEqual(self.event.approval_type, "meeting")

    def test_save_notes_appends_without_status_change(self):
        self.event.programming_status = "proposed"
        self.event.save()
        response = self._post("save_notes", notes="Looks good, pending room confirmation.")
        self.assertRedirects(response, self.queue_url)
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "proposed")
        self.assertIn("Looks good, pending room confirmation.", self.event.programming_notes)

    def test_re_propose_from_returned_stays_in_queue(self):
        """Regression: re-proposing a returned event must keep it in the queue."""
        self.event.programming_status = "rejected"
        self.event.save()
        self._post("propose")
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "proposed")
        # Verify it appears in the queue
        response = self.client.get(self.queue_url)
        self.assertContains(response, "Test Event")

    def test_invalid_action_returns_error(self):
        response = self._post("not_a_real_action")
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "draft")

    def test_requires_write_permission(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self._post("propose")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("programming-queue", response["Location"])
        self.event.refresh_from_db()
        self.assertEqual(self.event.programming_status, "draft")
