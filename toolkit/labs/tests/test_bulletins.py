# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.labs.models import Bulletin, BulletinRead
from toolkit.diary.models import SiteConfiguration, get_site_config

from .common import LabsTestsMixin


class BulletinListTests(LabsTestsMixin, TestCase):
    """Bulletin board — login required."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_list_shows_active_bulletins(self):
        response = self.client.get(reverse("labs-bulletins"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.bulletin.title)
        self.assertContains(response, self.bulletin_pinned.title)

    def test_pinned_bulletin_appears_first_in_context(self):
        response = self.client.get(reverse("labs-bulletins"))
        bulletins = response.context["bulletins"]
        self.assertEqual(bulletins[0], self.bulletin_pinned)

    def test_expired_bulletin_not_shown(self):
        past = timezone.now() - datetime.timedelta(days=1)
        expired = Bulletin.objects.create(
            title="Old news", body="Gone.", author=self.user_admin, expires_at=past
        )
        response = self.client.get(reverse("labs-bulletins"))
        titles = [b.title for b in response.context["bulletins"]]
        self.assertNotIn(expired.title, titles)

    def test_read_bulletin_is_marked_as_read(self):
        BulletinRead.objects.create(bulletin=self.bulletin, user=self.user_vol)
        response = self.client.get(reverse("labs-bulletins"))
        bulletins = response.context["bulletins"]
        bulletin_obj = next(b for b in bulletins if b.id == self.bulletin.id)
        self.assertTrue(bulletin_obj.is_read)

    def test_unread_bulletin_is_not_marked_as_read(self):
        response = self.client.get(reverse("labs-bulletins"))
        bulletins = response.context["bulletins"]
        bulletin_obj = next(b for b in bulletins if b.id == self.bulletin.id)
        self.assertFalse(bulletin_obj.is_read)


class BulletinArchiveTests(LabsTestsMixin, TestCase):
    """Archive shows bulletins that have passed their expiry."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_active_bulletins_not_in_archive(self):
        response = self.client.get(reverse("labs-bulletins-archive"))
        self.assertEqual(response.status_code, 200)
        titles = [b.title for b in response.context["bulletins"]]
        self.assertNotIn(self.bulletin.title, titles)

    def test_explicitly_expired_bulletin_appears_in_archive(self):
        past = timezone.now() - datetime.timedelta(days=1)
        expired = Bulletin.objects.create(
            title="Last week's notice", body="Done.", author=self.user_admin, expires_at=past
        )
        response = self.client.get(reverse("labs-bulletins-archive"))
        titles = [b.title for b in response.context["bulletins"]]
        self.assertIn(expired.title, titles)


class BulletinAddTests(LabsTestsMixin, TestCase):
    """Any logged-in user can post bulletins when site config is BULLETIN_POST_ALL."""

    def setUp(self):
        super().setUp()
        # Default is BULLETIN_POST_PROGRAMMER; set ALL so volunteer user can post
        cfg = get_site_config()
        cfg.bulletin_post_permission = SiteConfiguration.BULLETIN_POST_ALL
        cfg.save()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_get_shows_form(self):
        response = self.client.get(reverse("labs-bulletin-add"))
        self.assertEqual(response.status_code, 200)

    def test_post_creates_bulletin(self):
        data = {"title": "New water boiler", "body": "The boiler has been replaced."}
        response = self.client.post(reverse("labs-bulletin-add"), data)
        self.assertRedirects(response, reverse("labs-bulletins"))
        self.assertTrue(Bulletin.objects.filter(title="New water boiler").exists())

    def test_posted_bulletin_has_author_set(self):
        data = {"title": "Venue meeting notes", "body": "Notes from the meeting."}
        self.client.post(reverse("labs-bulletin-add"), data)
        b = Bulletin.objects.get(title="Venue meeting notes")
        self.assertEqual(b.author, self.user_vol)

    def test_post_with_empty_title_returns_form(self):
        response = self.client.post(reverse("labs-bulletin-add"), {"title": "", "body": "x"})
        self.assertEqual(response.status_code, 200)

    def test_bulletin_post_all_allows_any_logged_in_user(self):
        # Default site config: BULLETIN_POST_ALL — even no_perm users can post
        self.client.logout()
        self.client.login(username="no_perm", password="T3stPassword!2")
        cfg = get_site_config()
        cfg.bulletin_post_permission = SiteConfiguration.BULLETIN_POST_ALL
        cfg.save()
        response = self.client.get(reverse("labs-bulletin-add"))
        self.assertEqual(response.status_code, 200)

    def test_bulletin_post_programmer_blocks_basic_user(self):
        cfg = get_site_config()
        cfg.bulletin_post_permission = SiteConfiguration.BULLETIN_POST_PROGRAMMER
        cfg.save()
        response = self.client.get(reverse("labs-bulletin-add"))
        self.assertEqual(response.status_code, 403)

    def test_bulletin_post_panopticon_blocks_write_user(self):
        self.client.logout()
        self.client.login(username="admin", password="T3stPassword!")
        cfg = get_site_config()
        cfg.bulletin_post_permission = SiteConfiguration.BULLETIN_POST_PANOPTICON
        cfg.save()
        response = self.client.get(reverse("labs-bulletin-add"))
        self.assertEqual(response.status_code, 403)


class BulletinPinTests(LabsTestsMixin, TestCase):
    """Pinning toggles — requires toolkit.write."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_pin_unpinned_bulletin(self):
        url = reverse("labs-bulletin-pin", kwargs={"bulletin_id": self.bulletin.pk})
        self.client.post(url)
        self.bulletin.refresh_from_db()
        self.assertTrue(self.bulletin.pinned)

    def test_unpin_pinned_bulletin(self):
        url = reverse("labs-bulletin-pin", kwargs={"bulletin_id": self.bulletin_pinned.pk})
        self.client.post(url)
        self.bulletin_pinned.refresh_from_db()
        self.assertFalse(self.bulletin_pinned.pinned)


class BulletinDeleteTests(LabsTestsMixin, TestCase):
    """Delete — superuser only."""

    def test_superuser_can_delete_bulletin(self):
        self.user_admin.is_superuser = True
        self.user_admin.save()
        self.client.login(username="admin", password="T3stPassword!")
        bulletin_pk = self.bulletin.pk
        url = reverse("labs-bulletin-delete", kwargs={"bulletin_id": bulletin_pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-bulletins"))
        self.assertFalse(Bulletin.objects.filter(pk=bulletin_pk).exists())

    def test_non_superuser_gets_403(self):
        self.client.login(username="admin", password="T3stPassword!")
        url = reverse("labs-bulletin-delete", kwargs={"bulletin_id": self.bulletin.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Bulletin.objects.filter(pk=self.bulletin.pk).exists())


class BulletinReadTests(LabsTestsMixin, TestCase):
    """Mark-as-read actions."""

    def setUp(self):
        super().setUp()
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_bulletin_read_creates_read_record(self):
        url = reverse("labs-bulletin-read", kwargs={"bulletin_id": self.bulletin.pk})
        self.client.post(url)
        self.assertTrue(
            BulletinRead.objects.filter(bulletin=self.bulletin, user=self.user_vol).exists()
        )

    def test_bulletin_read_is_idempotent(self):
        url = reverse("labs-bulletin-read", kwargs={"bulletin_id": self.bulletin.pk})
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(
            BulletinRead.objects.filter(bulletin=self.bulletin, user=self.user_vol).count(), 1
        )

    def test_read_all_marks_all_active_bulletins(self):
        url = reverse("labs-bulletins-read-all")
        self.client.post(url)
        unread_count = (
            BulletinRead.objects
            .filter(user=self.user_vol, bulletin__in=[self.bulletin, self.bulletin_pinned])
            .count()
        )
        self.assertEqual(unread_count, 2)

    def test_read_all_does_not_duplicate_existing_reads(self):
        BulletinRead.objects.create(bulletin=self.bulletin, user=self.user_vol)
        url = reverse("labs-bulletins-read-all")
        self.client.post(url)
        self.assertEqual(
            BulletinRead.objects.filter(bulletin=self.bulletin, user=self.user_vol).count(), 1
        )
