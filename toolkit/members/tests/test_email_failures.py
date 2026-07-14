# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""SMTP failures in notification emails must not 500 the surrounding view (9.154).

Each test routes email through the real LoggingEmailBackend wrapper with a
deliberately failing inner backend (toolkit.util.tests.FailingBackend), so
the whole stack from view to backend is exercised.
"""
from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.members.models import LastGaspEmailLog, Member, Volunteer

from .common import MembersTestsMixin


@override_settings(
    EMAIL_BACKEND="toolkit.util.email_backend.LoggingEmailBackend",
    TOOLKIT_WRAPPED_EMAIL_BACKEND="toolkit.util.tests.FailingBackend",
)
class EmailFailureViewTests(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(
            self.client.login(username="admin", password="T3stPassword!")
        )

    def _set_config(self, **kwargs):
        config = get_site_config()
        for key, value in kwargs.items():
            setattr(config, key, value)
        config.save()
        return config

    def test_suspension_email_failure_shows_error_not_500(self):
        url = reverse(
            "send-suspension-email", kwargs={"volunteer_id": self.vol_1.pk}
        )
        session = self.client.session
        session[f"suspension_email_pending_{self.vol_1.pk}"] = True
        session.save()

        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "failed to send")
        # The pending flag survives so the send can be retried:
        self.assertTrue(
            self.client.session.get(f"suspension_email_pending_{self.vol_1.pk}")
        )

    def test_last_gasp_failure_shows_error_and_starts_no_cooldown(self):
        self._set_config(last_gasp_email_enabled=True)
        url = reverse("last-gasp-email", kwargs={"volunteer_id": self.vol_1.pk})

        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "failed to send")
        # No log row: the cooldown must not start for an email never sent.
        self.assertFalse(
            LastGaspEmailLog.objects.filter(volunteer=self.vol_1).exists()
        )

    def test_bulk_last_gasp_reports_failures_and_continues(self):
        self._set_config(last_gasp_email_enabled=True)
        url = reverse("bulk-last-gasp-email")

        response = self.client.post(
            url,
            data={
                "action": "send",
                "volunteer_ids": [self.vol_1.pk, self.vol_3.pk],
                "subject": "Are you still with us?",
                "body": "Hi {name}, are you still volunteering with {venue}?",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sent to 0 volunteers")
        self.assertContains(response, "2 failed to send")
        self.assertFalse(LastGaspEmailLog.objects.exists())

    def test_new_volunteer_saved_despite_email_failures(self):
        # With an email address set, creating a volunteer triggers the welcome
        # email; failure must warn, not 500, and the volunteer must exist.
        response = self.client.post(
            reverse("add-volunteer"),
            data={
                "mem-name": "Doomed Email Volunteer",
                "mem-email": "doomed@example.com",
                "vol-status": "active",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created volunteer")
        self.assertContains(response, "welcome email")
        member = Member.objects.get(name="Doomed Email Volunteer")
        self.assertTrue(Volunteer.objects.filter(member=member).exists())
