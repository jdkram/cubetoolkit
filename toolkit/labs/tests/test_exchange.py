# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.test import TestCase, override_settings
from django.urls import reverse

from toolkit.diary.models import get_site_config
from toolkit.labs.models import ExchangeItem
from .common import LabsTestsMixin


class ExchangeEnabledMixin(LabsTestsMixin):
    """Enable community exchange in SiteConfiguration for each test."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()
        self.item_give = ExchangeItem.objects.create(
            name="Old kettle",
            listing_type=ExchangeItem.TYPE_GIVE,
            category=ExchangeItem.CATEGORY_KITCHEN,
            condition=ExchangeItem.CONDITION_GOOD,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
            added_by=self.user_vol,
        )
        self.item_lend = ExchangeItem.objects.create(
            name="DeWalt drill",
            listing_type=ExchangeItem.TYPE_LEND,
            category=ExchangeItem.CATEGORY_TOOLS,
            condition=ExchangeItem.CONDITION_GOOD,
            owner_type=ExchangeItem.OWNER_VOLUNTEER,
            owner_volunteer=self.vol,
            added_by=self.user_vol,
        )


class ExchangeGateTests(LabsTestsMixin, TestCase):
    """Exchange returns 404 when feature flag is off."""

    def test_list_404_when_disabled(self):
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange"))
        self.assertEqual(response.status_code, 404)

    def test_add_404_when_disabled(self):
        cfg = get_site_config()
        cfg.community_exchange_enabled = False
        cfg.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange-add"))
        self.assertEqual(response.status_code, 404)


class ExchangeAnonTests(LabsTestsMixin, TestCase):
    """Anonymous users are redirected to login."""

    def setUp(self):
        super().setUp()
        cfg = get_site_config()
        cfg.community_exchange_enabled = True
        cfg.save()

    def test_anon_list_redirects(self):
        response = self.client.get(reverse("labs-exchange"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_anon_add_redirects(self):
        response = self.client.get(reverse("labs-exchange-add"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


class ExchangeListTests(ExchangeEnabledMixin, TestCase):
    def test_list_shows_active_items(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old kettle")
        self.assertContains(response, "DeWalt drill")

    def test_filter_by_type_give(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange") + "?type=give")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old kettle")
        self.assertNotContains(response, "DeWalt drill")

    def test_filter_by_type_lend(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange") + "?type=lend")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Old kettle")
        self.assertContains(response, "DeWalt drill")

    def test_filter_by_category(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange") + "?category=kitchen")
        self.assertContains(response, "Old kettle")
        self.assertNotContains(response, "DeWalt drill")

    def test_withdrawn_items_hidden_by_default(self):
        self.item_give.status = ExchangeItem.STATUS_WITHDRAWN
        self.item_give.active = False
        self.item_give.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange"))
        self.assertNotContains(response, "Old kettle")

    def test_inactive_items_never_shown(self):
        self.item_give.active = False
        self.item_give.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange") + "?unavailable=1")
        self.assertNotContains(response, "Old kettle")


class ExchangeItemDetailTests(ExchangeEnabledMixin, TestCase):
    def test_detail_view_200(self):
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange-item", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old kettle")

    def test_edit_link_shown_to_owner(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.get(reverse("labs-exchange-item", kwargs={"item_id": self.item_give.pk}))
        self.assertContains(response, "Edit listing")

    def test_edit_link_hidden_from_other_volunteer(self):
        other_user = self.user_ro
        response = self.client.force_login(other_user) or self.client.get(
            reverse("labs-exchange-item", kwargs={"item_id": self.item_give.pk})
        )
        self.assertNotContains(response, "Edit listing")


class ExchangeAddTests(ExchangeEnabledMixin, TestCase):
    def test_get_add_form(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.get(reverse("labs-exchange-add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Offer something")

    def test_post_creates_item(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-exchange-add"), {
            "listing_type": ExchangeItem.TYPE_GIVE,
            "name": "Spare bookshelf",
            "description": "Pine, good condition",
            "category": ExchangeItem.CATEGORY_FURNITURE,
            "condition": ExchangeItem.CONDITION_GOOD,
            "owner_type": ExchangeItem.OWNER_VOLUNTEER,
            "owner_volunteer": self.vol.pk,
            "location_notes": "Bring a car",
            "status": ExchangeItem.STATUS_AVAILABLE,
            "notes": "",
        })
        self.assertEqual(response.status_code, 302)
        item = ExchangeItem.objects.get(name="Spare bookshelf")
        self.assertEqual(item.added_by, self.user_vol)
        self.assertEqual(item.listing_type, ExchangeItem.TYPE_GIVE)


class ExchangeEditTests(ExchangeEnabledMixin, TestCase):
    def test_owner_can_edit(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.get(reverse("labs-exchange-edit", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 200)

    def test_other_user_cannot_edit(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.get(reverse("labs-exchange-edit", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 403)

    def test_superuser_can_edit_any(self):
        self.user_admin.is_superuser = True
        self.user_admin.save()
        self.client.login(username="admin", password="T3stPassword!")
        response = self.client.get(reverse("labs-exchange-edit", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 200)


class ExchangeWithdrawTests(ExchangeEnabledMixin, TestCase):
    def test_owner_can_withdraw(self):
        self.client.login(username="volunteer", password="T3stPassword!3")
        response = self.client.post(reverse("labs-exchange-withdraw", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 302)
        self.item_give.refresh_from_db()
        self.assertFalse(self.item_give.active)
        self.assertEqual(self.item_give.status, ExchangeItem.STATUS_WITHDRAWN)

    def test_other_user_cannot_withdraw(self):
        self.client.login(username="read_only", password="T3stPassword!1")
        response = self.client.post(reverse("labs-exchange-withdraw", kwargs={"item_id": self.item_give.pk}))
        self.assertEqual(response.status_code, 403)


class ExchangeModelTests(TestCase):
    def test_status_label_give_available(self):
        item = ExchangeItem(listing_type=ExchangeItem.TYPE_GIVE, status=ExchangeItem.STATUS_AVAILABLE)
        self.assertEqual(item.status_label(), "Available")

    def test_status_label_give_claimed(self):
        item = ExchangeItem(listing_type=ExchangeItem.TYPE_GIVE, status=ExchangeItem.STATUS_CLAIMED)
        self.assertEqual(item.status_label(), "Gone to a good home")

    def test_status_label_lend_available(self):
        item = ExchangeItem(listing_type=ExchangeItem.TYPE_LEND, status=ExchangeItem.STATUS_AVAILABLE)
        self.assertEqual(item.status_label(), "Available to borrow")

    def test_status_label_lend_on_loan(self):
        item = ExchangeItem(listing_type=ExchangeItem.TYPE_LEND, status=ExchangeItem.STATUS_ON_LOAN)
        self.assertEqual(item.status_label(), "On loan")

    def test_str(self):
        item = ExchangeItem(name="Spare kettle")
        self.assertEqual(str(item), "Spare kettle")

    def test_is_available_true(self):
        item = ExchangeItem(status=ExchangeItem.STATUS_AVAILABLE)
        self.assertTrue(item.is_available)

    def test_is_available_false(self):
        item = ExchangeItem(status=ExchangeItem.STATUS_CLAIMED)
        self.assertFalse(item.is_available)
