# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import datetime

import django.contrib.auth.models as auth_models

from toolkit.members.models import Member, Volunteer
from toolkit.operations.models import MaintenanceTask


class OperationsTestsMixin:
    def setUp(self):
        self._setup_test_users()
        self._setup_test_data()
        return super().setUp()

    def _setup_test_users(self):
        from toolkit.test_common import create_toolkit_test_users
        users = create_toolkit_test_users(is_admin_superuser=False)
        self.user_admin = users.admin
        self.user_ro = users.read_only
        self.user_none = users.no_perm

        self.mem_vol = Member.objects.create(
            name="Test Volunteer", email="vol@test.example", number="99"
        )
        self.user_vol = auth_models.User.objects.create_user(
            "volunteer", "vol@test.example", "T3stPassword!3"
        )
        self.vol = Volunteer.objects.create(member=self.mem_vol, user=self.user_vol)

    def _setup_test_data(self):
        self.task_annual = MaintenanceTask.objects.create(
            name="Fire alarm annual service",
            category=MaintenanceTask.CATEGORY_SECURITY_FIRE,
            frequency=MaintenanceTask.FREQUENCY_ANNUAL,
        )
        self.task_committed = MaintenanceTask.objects.create(
            name="Gutter clearance",
            category=MaintenanceTask.CATEGORY_PROPERTY,
            frequency=MaintenanceTask.FREQUENCY_ANNUAL,
            committed_to=self.vol,
            committed_on=datetime.date.today(),
        )
