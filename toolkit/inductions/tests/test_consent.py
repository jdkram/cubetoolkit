# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Consent renewal and privacy-policy-change notification tests.

Covers: consent_policy_version stamped at signup, the two reminder commands
(send_consent_renewal_reminders, send_policy_change_notification), and the
"mark privacy policy as updated" admin action.
"""
import datetime
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import get_site_config
from toolkit.inductions.models import InductionSignup, InductionsSettings
from toolkit.inductions.tests.common import InductionsTestsMixin
from toolkit.inductions.views import _create_volunteer_from_signup
from toolkit.members.models import Member, Volunteer


def _set_config(**kwargs):
    config = get_site_config()
    for key, value in kwargs.items():
        setattr(config, key, value)
    config.save()
    return config


def _days_ago(days):
    return timezone.now() - datetime.timedelta(days=days)


def _mk_signup(session, name, email):
    return InductionSignup.objects.create(session=session, name=name, email=email)


class SignupStampsPolicyVersion(InductionsTestsMixin, TestCase):
    def test_signup_stamps_current_policy_version(self):
        self.settings.privacy_policy_version = 3
        self.settings.save()
        v = _create_volunteer_from_signup(_mk_signup(self.session, "Jo Bloggs", "jo@test.example"))
        self.assertEqual(v.consent_policy_version, 3)


class ConsentRenewalReminders(InductionsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        _set_config(consent_renewal_days=365, consent_renewal_grace_days=30)

    def _make_vol(self, username, gdpr_opt_in=None, reminder_sent_at=None, status=Volunteer.STATUS_ACTIVE, retention_exempt=False):
        from django.contrib.auth.models import User
        member = Member.objects.create(name=f"CR {username}", email=f"{username}@cr.test", gdpr_opt_in=gdpr_opt_in)
        user = User.objects.create_user(username, f"{username}@cr.test", "pw")
        return Volunteer.objects.create(
            member=member, user=user, status=status,
            retention_exempt=retention_exempt,
            consent_reminder_sent_at=reminder_sent_at,
        )

    def _run(self, *args):
        out = StringIO()
        call_command("send_consent_renewal_reminders", *args, stdout=out)
        return out.getvalue()

    def test_reminds_volunteer_with_stale_consent(self):
        vol = self._make_vol("stale", gdpr_opt_in=_days_ago(400))
        self._run()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["stale@cr.test"])
        vol.refresh_from_db()
        self.assertIsNotNone(vol.consent_reminder_sent_at)

    def test_no_reminder_for_recent_consent(self):
        self._make_vol("fresh", gdpr_opt_in=_days_ago(10))
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_resend_within_same_cycle(self):
        self._make_vol("recent-reminder", gdpr_opt_in=_days_ago(400), reminder_sent_at=_days_ago(5))
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_retention_exempt_not_reminded(self):
        self._make_vol("exempt", gdpr_opt_in=_days_ago(400), retention_exempt=True)
        self._run()
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_sends_nothing(self):
        self._make_vol("dryrun", gdpr_opt_in=_days_ago(400))
        self._run("--dry-run")
        self.assertEqual(len(mail.outbox), 0)

    def test_disabled_when_renewal_days_zero(self):
        _set_config(consent_renewal_days=0)
        self._make_vol("disabled", gdpr_opt_in=_days_ago(400))
        self._run()
        self.assertEqual(len(mail.outbox), 0)


class PolicyChangeNotification(InductionsTestsMixin, TestCase):
    def _make_vol(self, username, consent_policy_version=1, status=Volunteer.STATUS_ACTIVE, retention_exempt=False):
        from django.contrib.auth.models import User
        member = Member.objects.create(name=f"PC {username}", email=f"{username}@pc.test")
        user = User.objects.create_user(username, f"{username}@pc.test", "pw")
        return Volunteer.objects.create(
            member=member, user=user, status=status,
            retention_exempt=retention_exempt,
            consent_policy_version=consent_policy_version,
        )

    def test_notifies_volunteer_behind_current_version(self):
        vol = self._make_vol("behind", consent_policy_version=1)
        self.settings.privacy_policy_version = 2
        self.settings.save()
        out = StringIO()
        call_command("send_policy_change_notification", stdout=out)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["behind@pc.test"])
        vol.refresh_from_db()
        self.assertIsNotNone(vol.consent_reminder_sent_at)

    def test_does_not_notify_volunteer_already_current(self):
        self._make_vol("current", consent_policy_version=2)
        self.settings.privacy_policy_version = 2
        self.settings.save()
        out = StringIO()
        call_command("send_policy_change_notification", stdout=out)
        self.assertEqual(len(mail.outbox), 0)

    def test_retention_exempt_not_notified(self):
        self._make_vol("exempt", consent_policy_version=1, retention_exempt=True)
        self.settings.privacy_policy_version = 2
        self.settings.save()
        out = StringIO()
        call_command("send_policy_change_notification", stdout=out)
        self.assertEqual(len(mail.outbox), 0)


class MarkPolicyUpdatedAdminAction(InductionsTestsMixin, TestCase):
    def _make_vol(self, username, consent_policy_version=1):
        from django.contrib.auth.models import User
        member = Member.objects.create(name=f"MP {username}", email=f"{username}@mp.test")
        user = User.objects.create_user(username, f"{username}@mp.test", "pw")
        return Volunteer.objects.create(
            member=member, user=user, status=Volunteer.STATUS_ACTIVE,
            consent_policy_version=consent_policy_version,
        )

    def test_bumps_version_and_notifies(self):
        self._make_vol("v1a", consent_policy_version=1)
        self._make_vol("v1b", consent_policy_version=1)
        self.login_admin()
        resp = self.client.post(reverse("inductions:manage_mark_policy_updated"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["notified"], 2)
        self.assertEqual(len(mail.outbox), 2)

        cfg = InductionsSettings.load()
        self.assertEqual(cfg.privacy_policy_version, 2)
        self.assertIsNotNone(cfg.privacy_policy_updated_at)

    def test_requires_panopticon(self):
        self.login_nobody()
        resp = self.client.post(reverse("inductions:manage_mark_policy_updated"))
        self.assertNotEqual(resp.status_code, 200)

    def test_get_not_allowed(self):
        self.login_admin()
        resp = self.client.get(reverse("inductions:manage_mark_policy_updated"))
        self.assertEqual(resp.status_code, 405)
