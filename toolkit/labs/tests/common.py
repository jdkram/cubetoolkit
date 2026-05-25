# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
import django.contrib.auth.models as auth_models
import django.contrib.contenttypes.models as ct_models

from toolkit.members.models import Member, Volunteer
from toolkit.labs.models import Bulletin, Collective, DonationItem, Job, RoomNote


class LabsTestsMixin:
    def setUp(self):
        self._setup_test_users()
        self._setup_test_data()
        return super().setUp()

    def _setup_test_users(self):
        ct = ct_models.ContentType.objects.get_or_create(model="", app_label="toolkit")[0]
        write_perm = auth_models.Permission.objects.get_or_create(
            name="Write access to all toolkit content",
            content_type=ct,
            codename="write",
        )[0]
        read_perm = auth_models.Permission.objects.get_or_create(
            name="Read access to all toolkit content",
            content_type=ct,
            codename="read",
        )[0]

        self.user_admin = auth_models.User.objects.create_user(
            "admin", "admin@test.example", "T3stPassword!"
        )
        self.user_admin.user_permissions.add(write_perm, read_perm)

        self.user_ro = auth_models.User.objects.create_user(
            "read_only", "ro@test.example", "T3stPassword!1"
        )
        self.user_ro.user_permissions.add(read_perm)

        self.user_none = auth_models.User.objects.create_user(
            "no_perm", "none@test.example", "T3stPassword!2"
        )

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
