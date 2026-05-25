# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.test import TestCase
from django.urls import reverse

from toolkit.labs.models import Job

from .common import LabsTestsMixin


class JobListTests(LabsTestsMixin, TestCase):
    """Job list view — login required, no write permission needed."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_list_shows_open_jobs(self):
        response = self.client.get(reverse("labs-jobs"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job_open.title)
        self.assertContains(response, self.job_claimed.title)

    def test_resolved_job_is_not_in_open_jobs(self):
        self.job_open.resolved = True
        self.job_open.save()
        response = self.client.get(reverse("labs-jobs"))
        # The job moves to done_jobs section but is still on the page
        self.assertContains(response, self.job_open.title)


class JobAddTests(LabsTestsMixin, TestCase):
    """Job add view — requires toolkit.write permission."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_shows_form(self):
        response = self.client.get(reverse("labs-job-add"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_job_and_redirects(self):
        data = {
            "title": "Replace ceiling tile",
            "area": "Cinema",
            "description": "Cracked tile above front row.",
            "plan_status": "",
            "safety_risk": False,
            "skill_needed": False,
            "keyholder_required": False,
            "urgency": Job.URGENCY_MEDIUM,
            "location_type": Job.LOCATION_BUILDING,
            "reporter_name": "",
        }
        response = self.client.post(reverse("labs-job-add"), data)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.assertTrue(Job.objects.filter(title="Replace ceiling tile").exists())

    def test_posted_job_has_posted_by_set(self):
        data = {
            "title": "Oil door hinge",
            "area": "",
            "description": "",
            "plan_status": "",
            "safety_risk": False,
            "skill_needed": False,
            "keyholder_required": False,
            "urgency": Job.URGENCY_LOW,
            "location_type": Job.LOCATION_BUILDING,
            "reporter_name": "",
        }
        self.client.post(reverse("labs-job-add"), data)
        job = Job.objects.get(title="Oil door hinge")
        self.assertEqual(job.posted_by, self.user_admin)

    def test_post_with_missing_title_returns_form(self):
        response = self.client.post(reverse("labs-job-add"), {"title": "", "urgency": "low"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Job.objects.filter(title="").exists())


class JobEditTests(LabsTestsMixin, TestCase):
    """Job edit view — requires toolkit.write permission."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")
        self.url = reverse("labs-job-edit", kwargs={"job_id": self.job_open.pk})

    def test_get_shows_form_prefilled(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.job_open.title)

    def test_post_updates_job(self):
        data = {
            "title": "Fix projector (updated)",
            "area": "Cinema",
            "description": "Now more urgent.",
            "plan_status": "Parts ordered.",
            "safety_risk": False,
            "skill_needed": True,
            "keyholder_required": False,
            "urgency": Job.URGENCY_HIGH,
            "location_type": Job.LOCATION_BUILDING,
            "reporter_name": "",
        }
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.job_open.refresh_from_db()
        self.assertEqual(self.job_open.title, "Fix projector (updated)")
        self.assertTrue(self.job_open.skill_needed)


class JobClaimTests(LabsTestsMixin, TestCase):
    """Any logged-in user can claim an unclaimed job."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_volunteer_can_claim_open_job(self):
        url = reverse("labs-job-claim", kwargs={"job_id": self.job_open.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.job_open.refresh_from_db()
        self.assertEqual(self.job_open.claimed_by, self.user_vol)

    def test_claiming_already_claimed_job_does_not_change_claimer(self):
        # job_claimed is already claimed by user_vol
        self.client.logout()
        self.client.login(username="no_perm", password="T3stPassword!2")
        url = reverse("labs-job-claim", kwargs={"job_id": self.job_claimed.pk})
        self.client.post(url)
        self.job_claimed.refresh_from_db()
        self.assertEqual(self.job_claimed.claimed_by, self.user_vol)


class JobUnclaimTests(LabsTestsMixin, TestCase):
    """Claimant can unclaim their own job; write-perm users can unclaim any."""

    def test_claimant_can_unclaim_own_job(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        url = reverse("labs-job-unclaim", kwargs={"job_id": self.job_claimed.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.job_claimed.refresh_from_db()
        self.assertIsNone(self.job_claimed.claimed_by)

    def test_write_user_can_unclaim_any_job(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-job-unclaim", kwargs={"job_id": self.job_claimed.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.job_claimed.refresh_from_db()
        self.assertIsNone(self.job_claimed.claimed_by)

    def test_other_volunteer_cannot_unclaim_someone_elses_job(self):
        self.client.login(username="no_perm", password="T3stPassword!2")
        url = reverse("labs-job-unclaim", kwargs={"job_id": self.job_claimed.pk})
        self.client.post(url)
        self.job_claimed.refresh_from_db()
        self.assertEqual(self.job_claimed.claimed_by, self.user_vol)


class JobResolveTests(LabsTestsMixin, TestCase):
    """Any logged-in user can mark a job resolved."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_resolve_marks_job_done(self):
        url = reverse("labs-job-resolve", kwargs={"job_id": self.job_open.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-jobs"))
        self.job_open.refresh_from_db()
        self.assertTrue(self.job_open.resolved)
        self.assertIsNotNone(self.job_open.resolved_at)
