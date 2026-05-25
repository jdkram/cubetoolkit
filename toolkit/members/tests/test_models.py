import datetime

from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from toolkit.members.models import Member, TrainingRecord, Volunteer

from .common import MembersTestsMixin


class TestTrainingRecord(MembersTestsMixin, TestCase):
    def setUp(self):
        super().setUp()

    def test_clean_ok(self):
        record = TrainingRecord(
            training_type=TrainingRecord.GENERAL_TRAINING,
            volunteer=self.vol_1,
            role=None,
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=2, day=27),
        )
        record.clean()
        record.save()

    def test_clean_save_fail_no_type(self):
        record = TrainingRecord(
            training_type="",
            volunteer=self.vol_1,
            role=None,
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=2, day=27),
        )
        # not validated by clean() as forms will correctly validate this
        self.assertRaises(IntegrityError, record.save)

    def test_clean_save_fail_no_role(self):
        record = TrainingRecord(
            training_type=TrainingRecord.ROLE_TRAINING,
            volunteer=self.vol_1,
            role=None,
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=2, day=27),
        )
        self.assertRaises(ValidationError, record.clean)
        self.assertRaises(IntegrityError, record.save)

    def test_clean_save_fail_role_when_general(self):
        record = TrainingRecord(
            training_type=TrainingRecord.GENERAL_TRAINING,
            volunteer=self.vol_1,
            role=self.vol_1.roles.all()[0],
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=2, day=27),
        )
        self.assertRaises(ValidationError, record.clean)
        # This isn't (currently) enforced:
        record.save()

    @override_settings(DEFAULT_TRAINING_EXPIRY_MONTHS=6)
    @patch("toolkit.members.models.get_site_config")
    @patch("toolkit.members.models.timezone_now")
    def test_has_expired_true(self, now_mock, config_mock):
        config_mock.return_value.default_training_expiry_months = 6

        now_mock.return_value.date.return_value = datetime.date(
            day=6, month=7, year=2010
        )

        record = TrainingRecord(
            training_type=TrainingRecord.GENERAL_TRAINING,
            volunteer=self.vol_1,
            role=None,
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=1, day=5),
        )
        self.assertTrue(record.has_expired())
        self.assertTrue(record.has_expired(expiry_age=0))
        self.assertFalse(record.has_expired(expiry_age=7))

    @override_settings(DEFAULT_TRAINING_EXPIRY_MONTHS=6)
    @patch("toolkit.members.models.timezone_now")
    def test_has_expired_false(self, now_mock):

        now_mock.return_value.date.return_value = datetime.date(
            day=6, month=7, year=2010
        )

        record = TrainingRecord(
            training_type=TrainingRecord.GENERAL_TRAINING,
            volunteer=self.vol_1,
            role=None,
            trainer="Nike Air Jordan",
            notes="A#",
            training_date=datetime.date(year=2010, month=1, day=6),
        )
        self.assertFalse(record.has_expired())


class TestVolunteerModel(MembersTestsMixin, TestCase):
    def test_latest_general_training_record_unsaved(self):
        v = Volunteer(member=self.mem_1)
        self.assertIsNone(v.latest_general_training_record())

    def test_latest_general_training_record_saved(self):
        self.assertIsNone(self.vol_1.latest_general_training_record())

        record = TrainingRecord(
            training_type=TrainingRecord.GENERAL_TRAINING,
            volunteer=self.vol_1,
            role=None,
            trainer="Adidas, I guess?",
            notes="440Hz",
            training_date=datetime.date(year=2020, month=4, day=20),
        )
        record.clean()
        record.save()

        self.assertEqual(record, self.vol_1.latest_general_training_record())


class TestMemberModel(TestCase):
    """Unit tests for Member model logic not covered by view tests."""

    def _make_member(self, **kwargs):
        defaults = {"name": "Test Person", "email": "test@example.com"}
        defaults.update(kwargs)
        return Member.objects.create(**defaults)

    # ── mailout_key ────────────────────────────────────────────────────────

    def test_mailout_key_auto_generated_on_create(self):
        member = self._make_member()
        self.assertIsNotNone(member.mailout_key)
        self.assertNotEqual(member.mailout_key, "")

    def test_mailout_key_is_unique_across_members(self):
        m1 = self._make_member(email="a@example.com")
        m2 = self._make_member(email="b@example.com")
        self.assertNotEqual(m1.mailout_key, m2.mailout_key)

    def test_mailout_key_not_overwritten_on_resave(self):
        member = self._make_member()
        original_key = member.mailout_key
        member.name = "Updated name"
        member.save()
        member.refresh_from_db()
        self.assertEqual(member.mailout_key, original_key)

    # ── mailout_recipients() ───────────────────────────────────────────────

    def test_mailout_recipients_includes_eligible_member(self):
        member = self._make_member(mailout=True, mailout_failed=False)
        self.assertIn(member, Member.objects.mailout_recipients())

    def test_mailout_recipients_excludes_opted_out(self):
        member = self._make_member(mailout=False)
        self.assertNotIn(member, Member.objects.mailout_recipients())

    def test_mailout_recipients_excludes_failed(self):
        member = self._make_member(mailout_failed=True)
        self.assertNotIn(member, Member.objects.mailout_recipients())

    def test_mailout_recipients_excludes_empty_email(self):
        # email is now mandatory (blank=False) so we can't create one,
        # but the manager guard is still worth verifying via the filter chain
        qs = Member.objects.mailout_recipients()
        self.assertFalse(qs.filter(email="").exists())


class TestVolunteerStatusModel(MembersTestsMixin, TestCase):
    """Volunteer.status and active-field sync."""

    def test_default_status_is_active(self):
        self.assertEqual(self.vol_1.status, Volunteer.STATUS_ACTIVE)

    def test_active_field_true_when_status_active(self):
        self.assertTrue(self.vol_1.active)

    def test_status_dormant_sets_active_false(self):
        self.vol_1.status = Volunteer.STATUS_DORMANT
        self.vol_1.save()
        self.vol_1.refresh_from_db()
        self.assertFalse(self.vol_1.active)

    def test_status_retired_sets_active_false(self):
        self.vol_1.status = Volunteer.STATUS_RETIRED
        self.vol_1.save()
        self.vol_1.refresh_from_db()
        self.assertFalse(self.vol_1.active)

    def test_reactivating_to_active_restores_active_true(self):
        self.vol_1.status = Volunteer.STATUS_DORMANT
        self.vol_1.save()
        self.vol_1.status = Volunteer.STATUS_ACTIVE
        self.vol_1.save()
        self.vol_1.refresh_from_db()
        self.assertTrue(self.vol_1.active)
