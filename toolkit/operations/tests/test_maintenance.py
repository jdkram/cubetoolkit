# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django.test import TestCase
from django.urls import reverse

from toolkit.operations.models import MaintenanceRecord, MaintenanceTask

from .common import OperationsTestsMixin


class MaintenanceTaskModelTests(OperationsTestsMixin, TestCase):
    def test_next_due_with_no_records_is_created_plus_frequency(self):
        # No completions yet: next_due falls back to today + frequency period.
        expected = datetime.date.today() + datetime.timedelta(days=365)
        self.assertAlmostEqual(
            (self.task_annual.next_due - expected).days, 0, delta=2
        )

    def test_next_due_uses_latest_record(self):
        MaintenanceRecord.objects.create(
            task=self.task_annual, completed_date=datetime.date(2026, 1, 1)
        )
        self.task_annual.refresh_from_db()
        self.assertEqual(self.task_annual.next_due, datetime.date(2027, 1, 1))

    def test_next_due_override_takes_precedence(self):
        MaintenanceRecord.objects.create(
            task=self.task_annual,
            completed_date=datetime.date(2026, 1, 1),
            next_due_override=datetime.date(2026, 6, 1),
        )
        self.task_annual.refresh_from_db()
        self.assertEqual(self.task_annual.next_due, datetime.date(2026, 6, 1))

    def test_status_overdue(self):
        MaintenanceRecord.objects.create(
            task=self.task_annual,
            completed_date=datetime.date(2020, 1, 1),
        )
        self.task_annual.refresh_from_db()
        self.assertEqual(self.task_annual.status, MaintenanceTask.STATUS_OVERDUE)

    def test_status_ok_when_far_in_future(self):
        MaintenanceRecord.objects.create(
            task=self.task_annual, completed_date=datetime.date.today()
        )
        self.task_annual.refresh_from_db()
        self.assertEqual(self.task_annual.status, MaintenanceTask.STATUS_OK)

    def test_stale_commitment_false_when_recent(self):
        self.assertFalse(self.task_committed.stale_commitment)

    def test_stale_commitment_true_when_old_and_incomplete(self):
        self.task_committed.committed_on = datetime.date.today() - datetime.timedelta(days=400)
        self.task_committed.save()
        self.assertTrue(self.task_committed.stale_commitment)

    def test_stale_commitment_false_once_completed(self):
        self.task_committed.committed_on = datetime.date.today() - datetime.timedelta(days=400)
        self.task_committed.save()
        MaintenanceRecord.objects.create(
            task=self.task_committed, completed_date=datetime.date.today()
        )
        self.task_committed.refresh_from_db()
        self.assertFalse(self.task_committed.stale_commitment)


class ScheduleViewTests(OperationsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_list_shows_active_tasks(self):
        response = self.client.get(reverse("operations-schedule"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.task_annual.name)

    def test_inactive_task_not_shown(self):
        self.task_annual.active = False
        self.task_annual.save()
        response = self.client.get(reverse("operations-schedule"))
        self.assertNotContains(response, self.task_annual.name)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("operations-schedule"))
        self.assertRedirects(
            response, reverse("login", query={"next": reverse("operations-schedule")})
        )


class TaskAddTests(OperationsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_shows_form(self):
        response = self.client.get(reverse("operations-task-add"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_task(self):
        data = {
            "name": "PAT testing",
            "category": MaintenanceTask.CATEGORY_COMPLIANCE_LEGAL,
            "frequency": MaintenanceTask.FREQUENCY_ANNUAL,
            "frequency_notes": "",
            "contractor": "",
            "keyholder_required": False,
            "skills_required": "",
            "time_commitment": "",
            "nextcloud_link": "",
            "notes": "",
            "active": True,
        }
        response = self.client.post(reverse("operations-task-add"), data)
        self.assertRedirects(response, reverse("operations-schedule"))
        self.assertTrue(MaintenanceTask.objects.filter(name="PAT testing").exists())

    def test_read_only_user_forbidden(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(reverse("operations-task-add"))
        self.assertEqual(response.status_code, 403)


class TaskMarkDoneTests(OperationsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_post_creates_record_and_clears_commitment(self):
        url = reverse("operations-task-mark-done", kwargs={"task_id": self.task_committed.pk})
        response = self.client.post(url, {
            "completed_date": datetime.date.today().isoformat(),
            "completed_by_name": "Contractor Co",
            "notes": "All clear",
            "next_due_override": "",
        })
        self.assertRedirects(response, reverse("operations-schedule"))
        self.assertTrue(
            MaintenanceRecord.objects.filter(task=self.task_committed, completed_by_name="Contractor Co").exists()
        )
        self.task_committed.refresh_from_db()
        self.assertIsNone(self.task_committed.committed_to)

    def test_read_only_user_forbidden(self):
        self.client.logout()
        self.client.login(username="read_only", password="T3stPassword!1")
        url = reverse("operations-task-mark-done", kwargs={"task_id": self.task_annual.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class TaskCommitTests(OperationsTestsMixin, TestCase):
    def setUp(self):
        super().setUp()

    def test_volunteer_can_commit_to_uncommitted_task(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("operations-task-commit", kwargs={"task_id": self.task_annual.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("operations-schedule"))
        self.task_annual.refresh_from_db()
        self.assertEqual(self.task_annual.committed_to, self.vol)
        self.assertEqual(self.task_annual.committed_on, datetime.date.today())

    def test_committing_already_committed_task_does_not_change_committer(self):
        other_user = None
        from toolkit.members.models import Member, Volunteer
        other_member = Member.objects.create(name="Other Vol", email="other@test.example", number="98")
        import django.contrib.auth.models as auth_models
        other_user = auth_models.User.objects.create_user("other_vol", "other@test.example", "T3stPassword!4")
        other_vol = Volunteer.objects.create(member=other_member, user=other_user)
        self.client.login(username="other_vol", password="T3stPassword!4")
        url = reverse("operations-task-commit", kwargs={"task_id": self.task_committed.pk})
        self.client.post(url)
        self.task_committed.refresh_from_db()
        self.assertEqual(self.task_committed.committed_to, self.vol)


class TaskUncommitTests(OperationsTestsMixin, TestCase):
    def test_committer_can_uncommit_own_task(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("operations-task-uncommit", kwargs={"task_id": self.task_committed.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("operations-schedule"))
        self.task_committed.refresh_from_db()
        self.assertIsNone(self.task_committed.committed_to)
        self.assertIsNone(self.task_committed.committed_on)

    def test_write_user_can_uncommit_any_task(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("operations-task-uncommit", kwargs={"task_id": self.task_committed.pk})
        self.client.post(url)
        self.task_committed.refresh_from_db()
        self.assertIsNone(self.task_committed.committed_to)

    def test_other_volunteer_cannot_uncommit_someone_elses_task(self):
        import django.contrib.auth.models as auth_models
        from toolkit.members.models import Member, Volunteer
        other_member = Member.objects.create(name="Other Vol", email="other2@test.example", number="97")
        other_user = auth_models.User.objects.create_user("other_vol2", "other2@test.example", "T3stPassword!5")
        Volunteer.objects.create(member=other_member, user=other_user)
        self.client.login(username="other_vol2", password="T3stPassword!5")
        url = reverse("operations-task-uncommit", kwargs={"task_id": self.task_committed.pk})
        self.client.post(url)
        self.task_committed.refresh_from_db()
        self.assertIsNotNone(self.task_committed.committed_to)
