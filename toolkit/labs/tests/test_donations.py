# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.test import TestCase
from django.urls import reverse

from toolkit.labs.models import DonationItem

from .common import LabsTestsMixin


class DonationListTests(LabsTestsMixin, TestCase):
    """Public donations page — no login required."""

    def test_page_loads_without_login(self):
        response = self.client.get(reverse("labs-donations"))
        self.assertEqual(response.status_code, 200)

    def test_shows_active_items(self):
        response = self.client.get(reverse("labs-donations"))
        self.assertContains(response, self.don_wanted.name)
        self.assertContains(response, self.don_not_needed.name)

    def test_hides_inactive_items(self):
        hidden = DonationItem.objects.create(
            name="Secret stash", category="Other", status=DonationItem.STATUS_WANTED, active=False
        )
        response = self.client.get(reverse("labs-donations"))
        self.assertNotContains(response, hidden.name)

    def test_items_grouped_by_category(self):
        response = self.client.get(reverse("labs-donations"))
        # Both categories from our fixtures should appear somewhere in the page
        self.assertContains(response, "Furniture")
        self.assertContains(response, "Electronics")


class DonationManageTests(LabsTestsMixin, TestCase):
    """Manage view — requires toolkit.write permission."""

    def setUp(self):
        super().setUp()
        self.client.login(username="admin", password="T3stPassword!")

    def test_get_shows_all_items(self):
        response = self.client.get(reverse("labs-donations-manage"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.don_wanted.name)

    def test_add_action_creates_item(self):
        data = {
            "_action": "add",
            "name": "Spare projector bulb",
            "category": "Electronics",
            "status": DonationItem.STATUS_WANTED,
            "active": True,
            "display_order": 0,
            "notes": "",
            "internal_notes": "",
            "contact": "",
        }
        response = self.client.post(reverse("labs-donations-manage"), data)
        self.assertRedirects(response, reverse("labs-donations-manage"))
        self.assertTrue(DonationItem.objects.filter(name="Spare projector bulb").exists())

    def test_add_action_sets_last_edited_by(self):
        data = {
            "_action": "add",
            "name": "Coffee machine",
            "category": "Appliances",
            "status": DonationItem.STATUS_CHECK_FIRST,
            "active": True,
            "display_order": 0,
            "notes": "",
            "internal_notes": "",
            "contact": "",
        }
        self.client.post(reverse("labs-donations-manage"), data)
        item = DonationItem.objects.get(name="Coffee machine")
        self.assertEqual(item.last_edited_by, self.user_admin)

    def test_edit_action_updates_item(self):
        data = {
            "_action": "edit",
            "item_id": self.don_wanted.pk,
            "name": "Old Sofa (updated)",
            "category": "Furniture",
            "status": DonationItem.STATUS_CHECK_FIRST,
            "active": True,
            "display_order": 0,
            "notes": "",
            "internal_notes": "",
            "contact": "",
        }
        response = self.client.post(reverse("labs-donations-manage"), data)
        self.assertRedirects(response, reverse("labs-donations-manage"))
        self.don_wanted.refresh_from_db()
        self.assertEqual(self.don_wanted.name, "Old Sofa (updated)")
        self.assertEqual(self.don_wanted.status, DonationItem.STATUS_CHECK_FIRST)

    def test_delete_action_removes_item(self):
        item_pk = self.don_not_needed.pk
        data = {"_action": "delete", "item_id": item_pk}
        response = self.client.post(reverse("labs-donations-manage"), data)
        self.assertRedirects(response, reverse("labs-donations-manage"))
        self.assertFalse(DonationItem.objects.filter(pk=item_pk).exists())

    def test_add_action_with_missing_name_returns_form(self):
        data = {
            "_action": "add",
            "name": "",
            "category": "Stuff",
            "status": DonationItem.STATUS_WANTED,
            "active": True,
            "display_order": 0,
            "notes": "",
            "internal_notes": "",
            "contact": "",
        }
        response = self.client.post(reverse("labs-donations-manage"), data)
        self.assertEqual(response.status_code, 200)
