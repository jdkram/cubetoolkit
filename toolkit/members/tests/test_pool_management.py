# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.8"]; status: "#ai-written"
"""Tests for volunteer pool-management tools: auto-dormancy, purge, the
returning-volunteer experience, and the pool-health dashboard."""
import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.diary.models import Role, RotaEntry, Showing, Event, get_site_config
from toolkit.members.models import AnonymisationLog, Member, Volunteer

from .common import MembersTestsMixin


def _days_ago(days):
    return timezone.now() - datetime.timedelta(days=days)


class PoolManagementBase(MembersTestsMixin, TestCase):
    def _make_vol(self, username, status=Volunteer.STATUS_ACTIVE,
                  last_login=None, joined_days_ago=1):
        """Create a Member + User + Volunteer with controlled login timestamps.

        date_joined, last_login, and Volunteer.created_at are all set via
        .update() so we bypass auto_now_add and User creation defaults, placing
        accounts precisely in time. joined_days_ago applies to all three so
        the volunteer's induction date is consistent with their login history.
        """
        member = Member.objects.create(name=f"PM {username}", email=f"{username}@pm.test")
        user = User.objects.create_user(username, f"{username}@pm.test", "pw")
        User.objects.filter(pk=user.pk).update(
            date_joined=_days_ago(joined_days_ago), last_login=last_login
        )
        vol = Volunteer.objects.create(member=member, user=user, status=status)
        Volunteer.objects.filter(pk=vol.pk).update(created_at=_days_ago(joined_days_ago))
        return Volunteer.objects.get(pk=vol.pk)

    def _set_config(self, **kwargs):
        config = get_site_config()
        for key, value in kwargs.items():
            setattr(config, key, value)
        config.save()
        return config


class TestAutoDormancy(PoolManagementBase):
    def setUp(self):
        super().setUp()
        self._set_config(
            volunteer_dormancy_days=365,
            volunteer_never_logged_in_grace_days=90,
        )

    def _run(self, *args):
        out = StringIO()
        call_command("auto_dormancy", *args, stdout=out)
        return out.getvalue()

    def test_inactive_active_volunteer_becomes_dormant(self):
        vol = self._make_vol("stale", last_login=_days_ago(400))
        self._run()
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)

    def test_recently_active_volunteer_unchanged(self):
        vol = self._make_vol("recent", last_login=_days_ago(10))
        self._run()
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)

    def test_never_logged_in_past_grace_becomes_dormant(self):
        # This is the cohort the old months-based command silently skipped.
        vol = self._make_vol("neverold", last_login=None, joined_days_ago=200)
        self._run()
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)

    def test_never_logged_in_within_grace_unchanged(self):
        vol = self._make_vol("newjoiner", last_login=None, joined_days_ago=10)
        self._run()
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)

    def test_retired_and_suspended_untouched(self):
        retired = self._make_vol("ret", status=Volunteer.STATUS_RETIRED,
                                 last_login=_days_ago(400))
        suspended = self._make_vol("sus", status=Volunteer.STATUS_SUSPENDED,
                                   last_login=_days_ago(400))
        self._run()
        retired.refresh_from_db()
        suspended.refresh_from_db()
        self.assertEqual(retired.status, Volunteer.STATUS_RETIRED)
        self.assertEqual(suspended.status, Volunteer.STATUS_SUSPENDED)

    def test_dry_run_makes_no_changes(self):
        vol = self._make_vol("stale", last_login=_days_ago(400))
        output = self._run("--dry-run")
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)
        self.assertIn("DRY RUN", output)

    def test_both_thresholds_zero_disables(self):
        self._set_config(
            volunteer_dormancy_days=0, volunteer_never_logged_in_grace_days=0
        )
        vol = self._make_vol("stale", last_login=_days_ago(400))
        output = self._run()
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)
        self.assertIn("disabled", output)

    def test_future_rota_commitment_preserved(self):
        # Going dormant is not a suspension: future shifts must NOT be released.
        vol = self._make_vol("stale", last_login=_days_ago(400))
        role = Role.objects.create(name="PM Role", standard=True)
        event = Event.objects.create(name="PM Event")
        showing = Showing.objects.create(
            event=event, start=timezone.now() + datetime.timedelta(days=7),
            confirmed=True,
        )
        entry = RotaEntry.objects.create(
            showing=showing, role=role, volunteer=vol, name=vol.member.name, rank=1
        )
        self._run()
        entry.refresh_from_db()
        self.assertEqual(entry.volunteer_id, vol.pk)


class TestPurgeCandidatesAndCommand(PoolManagementBase):
    def setUp(self):
        super().setUp()
        self._set_config(volunteer_purge_days=1095)

    def test_purge_candidates_queryset(self):
        old_dormant = self._make_vol("od", status=Volunteer.STATUS_DORMANT,
                                     last_login=_days_ago(1200), joined_days_ago=1200)
        old_retired = self._make_vol("or", status=Volunteer.STATUS_RETIRED,
                                     last_login=_days_ago(1200), joined_days_ago=1200)
        recent_dormant = self._make_vol("rd", status=Volunteer.STATUS_DORMANT,
                                        last_login=_days_ago(30))
        active_old = self._make_vol("ao", status=Volunteer.STATUS_ACTIVE,
                                    last_login=_days_ago(1200), joined_days_ago=1200)
        pks = set(
            Volunteer.objects.purge_candidates(1095).values_list("pk", flat=True)
        )
        self.assertIn(old_dormant.pk, pks)
        self.assertIn(old_retired.pk, pks)
        self.assertNotIn(recent_dormant.pk, pks)
        self.assertNotIn(active_old.pk, pks)

    def test_never_logged_in_uses_join_date(self):
        # Falls back to date_joined when last_login is null.
        old = self._make_vol("nlo", status=Volunteer.STATUS_DORMANT,
                             last_login=None, joined_days_ago=1200)
        pks = set(Volunteer.objects.purge_candidates(1095).values_list("pk", flat=True))
        self.assertIn(old.pk, pks)

    def test_purge_days_zero_disables(self):
        self._make_vol("od", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200))
        self.assertEqual(Volunteer.objects.purge_candidates(0).count(), 0)

    def _run(self, *args):
        out = StringIO()
        call_command("purge_stale_volunteers", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_default_makes_no_changes(self):
        vol = self._make_vol("od", status=Volunteer.STATUS_DORMANT,
                             last_login=_days_ago(1200), joined_days_ago=1200)
        output = self._run()
        vol.refresh_from_db()
        self.assertNotIn("anon-", vol.user.username)
        self.assertEqual(AnonymisationLog.objects.count(), 0)
        self.assertIn("Dry run", output)

    def test_apply_without_confirm_aborts(self):
        self._make_vol("od", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200), joined_days_ago=1200)
        with self.assertRaises(CommandError):
            self._run("--apply")
        self.assertEqual(AnonymisationLog.objects.count(), 0)

    def test_apply_wrong_phrase_aborts(self):
        self._make_vol("od", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200), joined_days_ago=1200)
        with self.assertRaises(CommandError):
            self._run("--apply", "--confirm", "do it")
        self.assertEqual(AnonymisationLog.objects.count(), 0)

    def test_apply_correct_phrase_anonymises(self):
        vol = self._make_vol("od", status=Volunteer.STATUS_DORMANT,
                             last_login=_days_ago(1200), joined_days_ago=1200)
        # Past rota history that must survive (de-identified).
        role = Role.objects.create(name="PM Role", standard=True)
        event = Event.objects.create(name="PM Event")
        showing = Showing.objects.create(
            event=event, start=timezone.now() - datetime.timedelta(days=30),
            confirmed=True,
        )
        entry = RotaEntry.objects.create(
            showing=showing, role=role, volunteer=vol, name=vol.member.name, rank=1
        )
        count = Volunteer.objects.purge_candidates(1095).count()
        self._run("--apply", "--confirm", f"anonymise {count} volunteers")

        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ANONYMISED)
        self.assertTrue(vol.user.username.startswith("anon-"))
        self.assertEqual(AnonymisationLog.objects.filter(volunteer_pk=vol.pk).count(), 1)
        # Rota row preserved, but FK/name cleared.
        entry.refresh_from_db()
        self.assertIsNone(entry.volunteer_id)
        self.assertEqual(entry.name, "")


class TestReactivateSelf(PoolManagementBase):
    def test_dormant_volunteer_reactivates(self):
        vol = self._make_vol("dz", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        resp = self.client.post(reverse("volunteer-reactivate-self"))
        self.assertEqual(resp.status_code, 302)
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)

    def test_retired_volunteer_not_reactivated(self):
        vol = self._make_vol("rz", status=Volunteer.STATUS_RETIRED)
        self.client.force_login(vol.user)
        self.client.post(reverse("volunteer-reactivate-self"))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_RETIRED)

    def test_get_not_allowed(self):
        vol = self._make_vol("gz", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("volunteer-reactivate-self"))
        self.assertEqual(resp.status_code, 405)


class TestWelcomeCardAndDashboard(PoolManagementBase):
    def test_welcome_card_shown_to_dormant(self):
        vol = self._make_vol("wb", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("toolkit-index"))
        self.assertTrue(resp.context["welcome_back"])

    def test_welcome_card_not_shown_to_active(self):
        vol = self._make_vol("ac", status=Volunteer.STATUS_ACTIVE)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("toolkit-index"))
        self.assertFalse(resp.context.get("welcome_back", False))

    def test_welcome_card_dismissed_via_param(self):
        vol = self._make_vol("dm", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        self.client.get(reverse("toolkit-index"), {"dismiss_welcome": "1"})
        resp = self.client.get(reverse("toolkit-index"))
        self.assertFalse(resp.context.get("welcome_back", False))

    def test_pool_health_dashboard(self):
        self._set_config(volunteer_purge_days=1095)
        # Dormant, never logged in, within retention window — appears in "recently dormant"
        self._make_vol("never", status=Volunteer.STATUS_DORMANT, last_login=None,
                       joined_days_ago=200)
        # Retired, previously logged in, past retention window — appears in "long inactive"
        self._make_vol("purge", status=Volunteer.STATUS_RETIRED,
                       last_login=_days_ago(1200), joined_days_ago=1200)
        self.assertTrue(self.client.login(username="admin", password="T3stPassword!"))
        resp = self.client.get(reverse("view-volunteer-pool-health"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "volunteer_pool_health.html")
        # Three-tier sections are present.
        self.assertContains(resp, "Never logged in")
        self.assertContains(resp, "Long inactive")
        self.assertContains(resp, "Recently dormant")

    def test_pool_health_requires_superuser(self):
        vol = self._make_vol("plain", status=Volunteer.STATUS_ACTIVE)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("view-volunteer-pool-health"))
        self.assertNotEqual(resp.status_code, 200)


class TestBeginnerHighlightHint(PoolManagementBase):
    def test_dormant_volunteer_forces_beginner_highlight(self):
        vol = self._make_vol("bh", status=Volunteer.STATUS_DORMANT)
        # Rota edit requires the change_rotaentry permission.
        from django.contrib.auth.models import Permission
        vol.user.user_permissions.add(
            Permission.objects.get(codename="change_rotaentry")
        )
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("rota-edit"))
        self.assertTrue(resp.context["force_beginner_highlight"])

    def test_active_volunteer_does_not_force_highlight(self):
        vol = self._make_vol("ah", status=Volunteer.STATUS_ACTIVE)
        from django.contrib.auth.models import Permission
        vol.user.user_permissions.add(
            Permission.objects.get(codename="change_rotaentry")
        )
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("rota-edit"))
        self.assertFalse(resp.context["force_beginner_highlight"])


class TestRetentionExempt(PoolManagementBase):
    def test_exempt_volunteer_excluded_from_purge_candidates(self):
        self._set_config(volunteer_purge_days=1095)
        vol = self._make_vol("ex", status=Volunteer.STATUS_DORMANT,
                             last_login=_days_ago(1200), joined_days_ago=1200)
        vol.retention_exempt = True
        vol.save()
        pks = set(Volunteer.objects.purge_candidates(1095).values_list("pk", flat=True))
        self.assertNotIn(vol.pk, pks)

    def test_non_exempt_volunteer_included_in_purge_candidates(self):
        self._set_config(volunteer_purge_days=1095)
        vol = self._make_vol("ne", status=Volunteer.STATUS_DORMANT,
                             last_login=_days_ago(1200), joined_days_ago=1200)
        pks = set(Volunteer.objects.purge_candidates(1095).values_list("pk", flat=True))
        self.assertIn(vol.pk, pks)

    def test_exempt_section_shown_on_pool_health(self):
        vol = self._make_vol("exv", status=Volunteer.STATUS_DORMANT)
        vol.retention_exempt = True
        vol.retention_exempt_reason = "Founding member"
        vol.save()
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("view-volunteer-pool-health"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Retention-exempt")
        self.assertContains(resp, "PM exv")


class TestAdminRestoreVolunteer(PoolManagementBase):
    def test_restores_dormant_to_active(self):
        vol = self._make_vol("rv", status=Volunteer.STATUS_DORMANT)
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.post(reverse("admin-restore-volunteer", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(resp.status_code, 302)
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)

    def test_restores_retired_to_active(self):
        vol = self._make_vol("rr", status=Volunteer.STATUS_RETIRED)
        self.client.login(username="admin", password="T3stPassword!")
        self.client.post(reverse("admin-restore-volunteer", kwargs={"volunteer_id": vol.pk}))
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_ACTIVE)

    def test_non_superuser_forbidden(self):
        vol = self._make_vol("nsp", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        resp = self.client.post(reverse("admin-restore-volunteer", kwargs={"volunteer_id": vol.pk}))
        self.assertNotEqual(resp.status_code, 200)
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)

    def test_get_not_allowed(self):
        vol = self._make_vol("gna", status=Volunteer.STATUS_DORMANT)
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("admin-restore-volunteer", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(resp.status_code, 405)


class TestAutoDormancyGUI(PoolManagementBase):
    def setUp(self):
        super().setUp()
        self._set_config(volunteer_dormancy_days=365, volunteer_never_logged_in_grace_days=90)

    def test_preview_shows_candidates(self):
        self._make_vol("ia", status=Volunteer.STATUS_ACTIVE, last_login=_days_ago(400), joined_days_ago=400)
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("auto-dormancy-preview"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PM ia")

    def test_apply_marks_dormant(self):
        vol = self._make_vol("ap", status=Volunteer.STATUS_ACTIVE, last_login=_days_ago(400), joined_days_ago=400)
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.post(reverse("auto-dormancy-apply"))
        self.assertEqual(resp.status_code, 302)
        vol.refresh_from_db()
        self.assertEqual(vol.status, Volunteer.STATUS_DORMANT)

    def test_non_superuser_cannot_preview(self):
        vol = self._make_vol("nsp2", status=Volunteer.STATUS_ACTIVE)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("auto-dormancy-preview"))
        self.assertNotEqual(resp.status_code, 200)


class TestAnonymiseMembershipGuard(PoolManagementBase):
    def test_warning_shown_for_active_member(self):
        import datetime as dt
        vol = self._make_vol("mg", status=Volunteer.STATUS_DORMANT)
        vol.member.membership_expires = (timezone.now() + dt.timedelta(days=30)).date()
        vol.member.save()
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("anonymise-volunteer", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["has_active_membership"])
        self.assertContains(resp, "active membership")

    def test_no_warning_for_expired_member(self):
        import datetime as dt
        vol = self._make_vol("em", status=Volunteer.STATUS_DORMANT)
        vol.member.membership_expires = (timezone.now() - dt.timedelta(days=30)).date()
        vol.member.save()
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("anonymise-volunteer", kwargs={"volunteer_id": vol.pk}))
        self.assertFalse(resp.context["has_active_membership"])

    def test_purge_command_skips_active_member(self):
        import datetime as dt
        self._set_config(volunteer_purge_days=1095)
        vol = self._make_vol("pm", status=Volunteer.STATUS_DORMANT,
                             last_login=_days_ago(1200), joined_days_ago=1200)
        vol.member.membership_expires = (timezone.now() + dt.timedelta(days=30)).date()
        vol.member.save()
        out = StringIO()
        call_command("purge_stale_volunteers", stdout=out)
        output = out.getvalue()
        self.assertIn("Skipping", output)
        self.assertIn("active membership", output)
        vol.refresh_from_db()
        self.assertNotEqual(vol.status, Volunteer.STATUS_ANONYMISED)


class TestLastGaspEmail(PoolManagementBase):
    from django.test import override_settings

    def setUp(self):
        super().setUp()
        config = get_site_config()
        config.last_gasp_email_enabled = True
        config.last_gasp_email_subject = "Still with us, {name}?"
        config.last_gasp_email_body = "Hi {name}, we miss you at {venue}."
        config.last_gasp_cooldown_days = 30
        config.save()

    def test_preview_renders(self):
        vol = self._make_vol("lg", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200))
        self.client.login(username="admin", password="T3stPassword!")
        resp = self.client.get(reverse("last-gasp-email", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PM lg")
        self.assertContains(resp, "Still with us")

    def test_send_creates_log_entry(self):
        from toolkit.members.models import LastGaspEmailLog
        vol = self._make_vol("lgsend", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200))
        self.client.login(username="admin", password="T3stPassword!")
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            self.client.post(reverse("last-gasp-email", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(LastGaspEmailLog.objects.filter(volunteer=vol).count(), 1)

    def test_cooldown_blocks_second_send(self):
        from toolkit.members.models import LastGaspEmailLog
        vol = self._make_vol("lgcd", status=Volunteer.STATUS_DORMANT, last_login=_days_ago(1200))
        LastGaspEmailLog.objects.create(volunteer=vol, sent_by=None)
        self.client.login(username="admin", password="T3stPassword!")
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            resp = self.client.post(reverse("last-gasp-email", kwargs={"volunteer_id": vol.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(LastGaspEmailLog.objects.filter(volunteer=vol).count(), 1)

    def test_non_superuser_forbidden(self):
        vol = self._make_vol("lgperm", status=Volunteer.STATUS_DORMANT)
        self.client.force_login(vol.user)
        resp = self.client.get(reverse("last-gasp-email", kwargs={"volunteer_id": vol.pk}))
        self.assertNotEqual(resp.status_code, 200)
