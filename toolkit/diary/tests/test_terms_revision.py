"""Tests for EventTermsRevision signal and event hub display (task 9.71)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from toolkit.diary.models import Event, EventTermsRevision
from toolkit.diary.tests.common import DiaryTestsMixin

User = get_user_model()


class EventTermsRevisionSignalTests(TestCase):
    """Unit tests for the pre_save signal that creates revision records."""

    def setUp(self):
        self.event = Event.objects.create(
            name="Test Event",
            terms="Original terms text here.",
            outside_hire=False,
            private=False,
        )

    def test_no_revision_on_new_event(self):
        """Creating a new event should not create a revision (nothing to snapshot)."""
        self.assertEqual(self.event.terms_revisions.count(), 0)

    def test_revision_created_when_terms_change(self):
        self.event.terms = "Completely new terms."
        self.event.save()
        self.assertEqual(self.event.terms_revisions.count(), 1)
        rev = self.event.terms_revisions.first()
        self.assertEqual(rev.terms_text, "Original terms text here.")

    def test_revision_created_when_outside_hire_changes(self):
        self.event.outside_hire = True
        self.event.save()
        self.assertEqual(self.event.terms_revisions.count(), 1)
        rev = self.event.terms_revisions.first()
        self.assertFalse(rev.outside_hire)

    def test_revision_created_when_private_changes(self):
        self.event.private = True
        self.event.save()
        self.assertEqual(self.event.terms_revisions.count(), 1)
        rev = self.event.terms_revisions.first()
        self.assertFalse(rev.private)

    def test_no_revision_when_unaudited_field_changes(self):
        self.event.name = "New Name"
        self.event.save()
        self.assertEqual(self.event.terms_revisions.count(), 0)

    def test_saved_by_captured(self):
        user = User.objects.create_user(username="editor", password="pw")
        self.event._saved_by = user
        self.event.terms = "Updated terms."
        self.event.save()
        rev = self.event.terms_revisions.first()
        self.assertEqual(rev.saved_by, user)

    def test_saved_by_none_when_not_set(self):
        self.event.terms = "Updated terms."
        self.event.save()
        rev = self.event.terms_revisions.first()
        self.assertIsNone(rev.saved_by)

    def test_multiple_changes_create_multiple_revisions(self):
        self.event.terms = "Second version."
        self.event.save()
        self.event.terms = "Third version."
        self.event.save()
        self.assertEqual(self.event.terms_revisions.count(), 2)

    def test_revision_snapshot_reflects_state_before_save(self):
        """Each revision captures the pre-save values, not the new ones."""
        self.event.terms = "Second version."
        self.event.save()
        self.event.terms = "Third version."
        self.event.save()
        terms_texts = set(
            self.event.terms_revisions.values_list("terms_text", flat=True)
        )
        self.assertEqual(terms_texts, {"Original terms text here.", "Second version."})


class EventTermsRevisionViewTests(DiaryTestsMixin, TestCase):
    """Integration tests: _saved_by is wired in EditEventView and hub renders history."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_edit_event_view_records_saved_by(self):
        """POSTing to edit-event-details should capture the logged-in user on the revision."""
        url = reverse("edit-event-details", kwargs={"event_id": self.e4.pk})
        self.client.post(
            url,
            data={
                "name": self.e4.name,
                "terms": "Brand new agreed terms.",
                "duration": "01:00:00",
            },
        )
        self.e4.refresh_from_db()
        rev = self.e4.terms_revisions.first()
        self.assertIsNotNone(rev)
        admin_user = User.objects.get(username="admin")
        self.assertEqual(rev.saved_by, admin_user)

    def test_edit_event_view_revision_captures_old_value(self):
        original_terms = self.e4.terms
        url = reverse("edit-event-details", kwargs={"event_id": self.e4.pk})
        self.client.post(
            url,
            data={
                "name": self.e4.name,
                "terms": "Completely different terms now.",
                "duration": "01:00:00",
            },
        )
        rev = self.e4.terms_revisions.first()
        self.assertEqual(rev.terms_text, original_terms)

    def test_event_hub_shows_revision_history(self):
        """The event hub should show a 'Change history' section when revisions exist."""
        self.e4.terms = "Updated terms for hub test."
        self.e4.save()

        url = reverse("edit-event-details-view", kwargs={"event_id": self.e4.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Change history")
        self.assertContains(response, "1 revision")

    def test_event_hub_no_history_section_when_no_revisions(self):
        """Events with no revisions should not show the Change history section."""
        # e2 has no terms, so changing its name won't trigger a revision
        url = reverse("edit-event-details-view", kwargs={"event_id": self.e2.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Change history")
