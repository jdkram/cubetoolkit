# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import django.contrib.auth.models as auth_models

from toolkit.members.models import Member, Volunteer
from toolkit.labs.models import Bulletin, Collective, DonationItem, Job, RoomNote


class LabsTestsMixin:
    def setUp(self):
        self._setup_test_users()
        self._setup_test_data()
        return super().setUp()

    def _setup_test_users(self):
        # Standard admin/read_only/no_perm + toolkit.write/read perms.
        # See toolkit/test_common.py for rationale; tests reference
        # self.user_admin / self.user_ro / self.user_none directly (e.g. as
        # Bulletin.author / Job.posted_by), so we expose them on self.
        #
        # labs deliberately keeps 'admin' as a non-superuser write-perm user
        # (Programmer-tier equivalent) so the panopticon-only tests in
        # test_bulletins / test_security exercise the write-but-not-superuser
        # rejection path. diary and members do mark their admin as superuser
        # (Panopticon tier); the helper defaults to True, labs overrides.
        from toolkit.test_common import create_toolkit_test_users
        users = create_toolkit_test_users(is_admin_superuser=False)
        self.user_admin = users.admin
        self.user_ro = users.read_only
        self.user_none = users.no_perm

        # A user with a linked Volunteer profile — needed for join/leave tests
        self.mem_vol = Member.objects.create(
            name="Test Volunteer", email="vol@test.example", number="99"
        )
        self.user_vol = auth_models.User.objects.create_user(
            "volunteer", "vol@test.example", "T3stPassword!3"
        )
        self.vol = Volunteer.objects.create(member=self.mem_vol, user=self.user_vol)

    def _setup_test_data(self):
        self.col_open = Collective.objects.create(
            name="Film Collective", slug="film", active=True, invite_only=False
        )
        self.col_invite = Collective.objects.create(
            name="Secret Collective", slug="secret", active=True, invite_only=True
        )
        self.col_inactive = Collective.objects.create(
            name="Retired Collective", slug="retired", active=False
        )
        self.col_public = Collective.objects.create(
            name="Public Collective",
            slug="public-one",
            active=True,
            invite_only=False,
            listed_publicly=True,
            public_copy="Come join us!",
        )

        self.don_wanted = DonationItem.objects.create(
            name="Old Sofa", category="Furniture", status=DonationItem.STATUS_WANTED
        )
        self.don_not_needed = DonationItem.objects.create(
            name="VHS Player", category="Electronics", status=DonationItem.STATUS_NOT_NEEDED
        )

        self.note_cinema = RoomNote.objects.create(
            room_id="room-cinema", body="Mind the step", updated_by=self.user_admin
        )

        self.job_open = Job.objects.create(
            title="Fix projector", urgency=Job.URGENCY_HIGH, posted_by=self.user_admin
        )
        self.job_claimed = Job.objects.create(
            title="Paint walls",
            urgency=Job.URGENCY_LOW,
            posted_by=self.user_admin,
            claimed_by=self.user_vol,
        )

        self.bulletin = Bulletin.objects.create(
            title="Fire drill Friday", body="Evacuation at 3pm.", author=self.user_admin
        )
        self.bulletin_pinned = Bulletin.objects.create(
            title="Important notice", body="Read this.", author=self.user_admin, pinned=True
        )
