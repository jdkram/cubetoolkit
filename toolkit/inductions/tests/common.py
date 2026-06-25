# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
"""Shared fixtures for the inductions test suite.

Mirrors the LabsTestsMixin pattern: one superuser ("admin"), one authenticated
non-superuser ("nobody"), the inductions feature enabled, and a single open
session with one pending signup. Per-test data is layered on top.
"""
from django.contrib.auth.models import User
from django.utils import timezone

from toolkit.inductions.models import (
    InductionSession,
    InductionSignup,
    InductionsSettings,
)


class InductionsTestsMixin:
    def setUp(self):
        self.admin = User.objects.create_user(
            "admin", "admin@test.example", "T3stPassword!", is_superuser=True
        )
        self.nobody = User.objects.create_user(
            "nobody", "nobody@test.example", "T3stPassword!2"
        )

        self.settings = InductionsSettings.load()
        self.settings.inductions_enabled = True
        self.settings.access_needs_enabled = True
        self.settings.default_max_signups = None  # no cap unless a test sets one
        self.settings.organiser_notification_email = "organiser@test.example"
        self.settings.save()

        self.session = InductionSession.objects.create(
            title="Volunteer Induction August 2026",
            date=timezone.now() + timezone.timedelta(days=4),
            location="Cinema",
        )
        self.signup = InductionSignup.objects.create(
            session=self.session,
            name="Alice Smith",
            email="alice@test.example",
        )
        return super().setUp()

    # ── helpers ──────────────────────────────────────────────────────────
    def login_admin(self):
        self.assertTrue(self.client.login(username="admin", password="T3stPassword!"))

    def login_nobody(self):
        self.assertTrue(self.client.login(username="nobody", password="T3stPassword!2"))

    def valid_signup_post(self, **overrides):
        """A minimally-valid public sign-up POST (consent + age gate ticked)."""
        data = {
            "first_name": "Bob",
            "last_name": "Jones",
            "email": "bob@test.example",
            "age_confirm": "on",
            "consent": "on",
        }
        data.update(overrides)
        return data
