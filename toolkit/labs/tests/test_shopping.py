# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from toolkit.labs.models import ConsumableItem, NeedFlag, ProcurementPledge

from .common import LabsTestsMixin


class ShoppingListViewTests(LabsTestsMixin, TestCase):
    """Main shopping list view — login required."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_list_accessible_to_logged_in_user(self):
        response = self.client.get(reverse("labs-shopping"))
        self.assertEqual(response.status_code, 200)

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("labs-shopping"))
        self.assertNotEqual(response.status_code, 200)

    def test_item_appears_in_list(self):
        response = self.client.get(reverse("labs-shopping"))
        self.assertContains(response, "Hand soap")

    def test_inactive_item_not_shown(self):
        self.item.active = False
        self.item.save()
        response = self.client.get(reverse("labs-shopping"))
        self.assertNotContains(response, "Hand soap")

    def test_flagged_item_shows_needed_badge(self):
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        response = self.client.get(reverse("labs-shopping"))
        self.assertContains(response, "Needed")

    def test_recently_resolved_section_shows_resolved_flags(self):
        flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        flag.resolved_at = timezone.now()
        flag.resolved_by = self.vol
        flag.save()
        response = self.client.get(reverse("labs-shopping"))
        self.assertContains(response, "Recently restocked")


class ShoppingItemDetailTests(LabsTestsMixin, TestCase):
    """Item detail view."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Bin bags", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_detail_accessible(self):
        response = self.client.get(reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bin bags")

    def test_inactive_item_returns_404(self):
        self.item.active = False
        self.item.save()
        response = self.client.get(reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}))
        self.assertEqual(response.status_code, 404)

    def test_open_flag_shown_on_detail(self):
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        response = self.client.get(reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}))
        self.assertContains(response, "Needed")

    def test_history_section_shows_resolved_flags(self):
        flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        flag.resolved_at = timezone.now()
        flag.resolved_by = self.vol
        flag.save()
        response = self.client.get(reverse("labs-shopping-item", kwargs={"item_id": self.item.pk}))
        self.assertContains(response, "History")


class ShoppingFlagTests(LabsTestsMixin, TestCase):
    """Flagging an item as needed."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Dishwasher tablets", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_flag_creates_need_flag(self):
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        self.client.post(url)
        self.assertEqual(NeedFlag.objects.filter(item=self.item, resolved_at__isnull=True).count(), 1)

    def test_flag_sets_flagged_by_to_volunteer(self):
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        self.client.post(url)
        flag = NeedFlag.objects.get(item=self.item)
        self.assertEqual(flag.flagged_by, self.vol)

    def test_duplicate_flag_does_not_create_second_flag(self):
        NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        self.client.post(url)
        self.assertEqual(NeedFlag.objects.filter(item=self.item, resolved_at__isnull=True).count(), 1)

    def test_flag_with_notes(self):
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        self.client.post(url, {"notes": "Last one used Thursday"})
        flag = NeedFlag.objects.get(item=self.item)
        self.assertEqual(flag.notes, "Last one used Thursday")

    def test_flag_redirects_to_shopping_list(self):
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-shopping"))

    def test_flag_requires_login(self):
        self.client.logout()
        url = reverse("labs-shopping-flag", kwargs={"item_id": self.item.pk})
        response = self.client.post(url)
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(NeedFlag.objects.filter(item=self.item).count(), 0)


class ShoppingPledgeTests(LabsTestsMixin, TestCase):
    """Pledging to get a flagged item."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Hand soap", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_pledge_creates_procurement_pledge(self):
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.assertTrue(ProcurementPledge.objects.filter(need_flag=self.flag).exists())

    def test_pledge_sets_pledged_by(self):
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertEqual(pledge.pledged_by, self.vol)

    def test_pledge_with_eta(self):
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url, {"eta_date": "2026-06-01", "eta_notes": "Friday cleaning club"})
        pledge = ProcurementPledge.objects.get(need_flag=self.flag)
        self.assertEqual(pledge.eta_date, datetime.date(2026, 6, 1))
        self.assertEqual(pledge.eta_notes, "Friday cleaning club")

    def test_pledge_on_already_pledged_flag_does_not_create_second_pledge(self):
        ProcurementPledge.objects.create(need_flag=self.flag, pledged_by=self.vol)
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.assertEqual(ProcurementPledge.objects.filter(need_flag=self.flag).count(), 1)

    def test_pledge_redirects_to_shopping_list(self):
        url = reverse("labs-shopping-pledge", kwargs={"flag_id": self.flag.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-shopping"))

    def test_pledge_cancel_removes_pledge(self):
        pledge = ProcurementPledge.objects.create(need_flag=self.flag, pledged_by=self.vol)
        url = reverse("labs-shopping-pledge-cancel", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.assertFalse(ProcurementPledge.objects.filter(pk=pledge.pk).exists())

    def test_pledge_cancel_by_non_pledger_cancels(self):
        # Any logged-in volunteer can cancel anyone's pledge — avoids stale pledges
        # blocking others from signing up when the original pledger never follows through.
        from toolkit.members.models import Member, Volunteer
        import django.contrib.auth.models as auth_models
        mem2 = Member.objects.create(name="Other Vol", email="other@test.example", number="100")
        user2 = auth_models.User.objects.create_user("other_vol", "other@test.example", "T3stPassword!4")
        Volunteer.objects.create(member=mem2, user=user2)
        ProcurementPledge.objects.create(need_flag=self.flag, pledged_by=self.vol)

        self.client.logout()
        self.client.login(username="other_vol", password="T3stPassword!4")
        url = reverse("labs-shopping-pledge-cancel", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.assertFalse(ProcurementPledge.objects.filter(need_flag=self.flag).exists())


class ShoppingResolveTests(LabsTestsMixin, TestCase):
    """Marking a flag as resolved."""

    def setUp(self):
        super().setUp()
        self.item = ConsumableItem.objects.create(
            name="Sponges", category=ConsumableItem.CATEGORY_CLEANING
        )
        self.flag = NeedFlag.objects.create(item=self.item, flagged_by=self.vol)
        self.client.login(username="volunteer", password="T3stPassword!3")

    def test_resolve_sets_resolved_at(self):
        url = reverse("labs-shopping-resolve", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.flag.refresh_from_db()
        self.assertIsNotNone(self.flag.resolved_at)

    def test_resolve_sets_resolved_by(self):
        url = reverse("labs-shopping-resolve", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.resolved_by, self.vol)

    def test_resolve_also_marks_pledge_fulfilled(self):
        pledge = ProcurementPledge.objects.create(need_flag=self.flag, pledged_by=self.vol)
        url = reverse("labs-shopping-resolve", kwargs={"flag_id": self.flag.pk})
        self.client.post(url)
        pledge.refresh_from_db()
        self.assertIsNotNone(pledge.fulfilled_at)

    def test_resolve_redirects_to_shopping_list(self):
        url = reverse("labs-shopping-resolve", kwargs={"flag_id": self.flag.pk})
        response = self.client.post(url)
        self.assertRedirects(response, reverse("labs-shopping"))

    def test_resolve_already_resolved_flag_returns_404(self):
        self.flag.resolved_at = timezone.now()
        self.flag.save()
        url = reverse("labs-shopping-resolve", kwargs={"flag_id": self.flag.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)


class ConsumableItemModelTests(LabsTestsMixin, TestCase):
    """Model-level tests."""

    def test_open_flag_property_returns_none_when_no_flag(self):
        item = ConsumableItem.objects.create(name="Pens", category=ConsumableItem.CATEGORY_STATIONERY)
        self.assertIsNone(item.open_flag)

    def test_open_flag_property_returns_flag_when_open(self):
        item = ConsumableItem.objects.create(name="Pens", category=ConsumableItem.CATEGORY_STATIONERY)
        flag = NeedFlag.objects.create(item=item, flagged_by=self.vol)
        self.assertEqual(item.open_flag, flag)

    def test_open_flag_property_returns_none_when_resolved(self):
        item = ConsumableItem.objects.create(name="Pens", category=ConsumableItem.CATEGORY_STATIONERY)
        flag = NeedFlag.objects.create(item=item, flagged_by=self.vol, resolved_at=timezone.now())
        self.assertIsNone(item.open_flag)

    def test_need_flag_is_resolved_property(self):
        item = ConsumableItem.objects.create(name="Pens", category=ConsumableItem.CATEGORY_STATIONERY)
        flag = NeedFlag.objects.create(item=item, flagged_by=self.vol)
        self.assertFalse(flag.is_resolved)
        flag.resolved_at = timezone.now()
        flag.save()
        self.assertTrue(flag.is_resolved)
