import os
import logging
import binascii
import datetime

from monthdelta import monthdelta

import django.db  # Used for raw query for stats
from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.utils.timezone import now as timezone_now
from django.core.exceptions import ValidationError

from toolkit.diary.models import Role, get_site_config
from toolkit.util import generate_random_string

logger = logging.getLogger(__name__)


class MemberManager(models.Manager):
    # Used with Member class, to encapsulate logic about selecting which
    # members should get the mailout, and other such things

    def mailout_recipients(self):
        """Get all members who should be sent the mailout"""
        return (
            self.filter(email__isnull=False)
            .exclude(email="")
            .exclude(mailout_failed=True)
            .filter(mailout=True)
        )

    # A few hard-coded SQL queries to get some of the more complex statistics:
    def get_stat_popular_email_domains(self) -> dict[str, int]:
        # Get 10 most popular email domains amongst active subscribers
        with django.db.connection.cursor() as cursor:
            cursor.execute(
                "SELECT "
                " SUBSTRING_INDEX(`email`, '@', -1) AS domain, "
                " COUNT(1) AS num "
                "FROM Members "
                "WHERE email != '' "
                "AND mailout_failed = FALSE "
                "AND mailout = TRUE "
                "GROUP BY domain "
                "ORDER BY num DESC "
                "LIMIT 10"
            )
            return dict(cursor.fetchall())

    def get_stat_popular_postcode_prefixes(self):
        # Get 10 most popular postcode prefixes
        with django.db.connection.cursor() as cursor:
            cursor.execute(
                "SELECT "
                " SUBSTRING_INDEX(`postcode`, ' ', 1) AS firstbit, "
                " COUNT(1) AS num "
                "FROM Members "
                "WHERE postcode != '' "
                "GROUP BY firstbit "
                "ORDER BY num DESC "
                "LIMIT 10"
            )
            postcode_stats = [row for row in cursor.fetchall()]
        return postcode_stats

    def expired(self):
        """Get all members with an expiry date defined, where that date is in
        the past"""
        return self.filter(membership_expires__isnull=False).filter(
            membership_expires__lt=timezone_now().date()
        )

    def unexpired(self):
        """Get all members either without an expiry date defined, or with an
        expiry date in the future (or today)"""
        return self.filter(
            Q(membership_expires__isnull=True)
            | Q(membership_expires__gte=timezone_now().date())
        )


def get_default_membership_expiry():
    if not settings.MEMBERSHIP_EXPIRY_ENABLED:
        return None
    try:
        days = get_site_config().membership_length_days
    except Exception:
        # SiteConfiguration table may not exist yet during early migrations
        days = 365
    return timezone_now().date() + datetime.timedelta(days=days)


class Member(models.Model):

    # This is the primary key used in the old perl/bdb system, used as the
    # user-facing membership number (rather than using the private key).
    # Defaults to = pk. Note; not actually a number!
    number = models.CharField(max_length=10, editable=False)

    name = models.CharField(max_length=64)
    email = models.EmailField(max_length=64)

    address = models.CharField(max_length=128, blank=True)
    posttown = models.CharField(max_length=64, blank=True)
    postcode = models.CharField(max_length=16, blank=True)
    country = models.CharField(max_length=32, blank=True)

    website = models.CharField(max_length=128, blank=True)
    phone = models.CharField(max_length=64, blank=True)
    altphone = models.CharField(max_length=64, blank=True)
    personal_pronouns = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    is_member = models.BooleanField(default=True)
    membership_expires = models.DateField(
        null=True, blank=True, default=get_default_membership_expiry
    )

    mailout = models.BooleanField(default=True)
    mailout_failed = models.BooleanField(default=False)
    # Used for "click to unsubscribe"/"edit details" etc:
    mailout_key = models.CharField(
        max_length=32,
        blank=False,
        null=False,
        editable=False,
        default=generate_random_string,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    gdpr_opt_in = models.DateTimeField(null=True, blank=True)

    # Custom manager, includes helpful methods for selecting members:
    objects = MemberManager()

    class Meta:
        db_table = "Members"

    def __str__(self):
        return self.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        # If a user number hasn't been set, save a placeholder, then re-save
        # with the private key as the number:
        set_number = False
        if self.number == "":
            set_number = True
            self.number = "?"

        result = super().save(*args, **kwargs)

        if set_number:
            self.number = self._generate_membership_number()
            self.save()

        return result

    def _generate_membership_number(self):
        membership_no = "?"

        if not self.pk:
            # No private key! Use a hash of the name:
            logger.error(
                "Trying to generate membership number without a "
                "private key. Falling back to hash of name."
            )
            membership_no = binascii.crc32(self.name) & 0xFFFFFFFF
        else:
            offset = 0
            # If private key is already in use as a membership number try
            # multiples of 100000 higher...
            while Member.objects.filter(number=str(self.pk + offset)).count():
                offset += 100000
            membership_no = str(self.pk + offset)

        return membership_no

    def has_expired(self):
        if settings.MEMBERSHIP_EXPIRY_ENABLED and self.membership_expires:
            return self.membership_expires < timezone_now().date()
        else:
            return False


#    weak_email_validator = \
#       re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}\b")
#    def weak_validate_email(self):
#        pass


class Volunteer(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
    )

    member = models.OneToOneField(
        "Member", related_name="volunteer", on_delete=models.CASCADE
    )

    STATUS_ACTIVE = "active"
    STATUS_DORMANT = "dormant"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_DORMANT, "Dormant"),
        (STATUS_RETIRED, "Retired"),
    ]

    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    portrait = models.ImageField(
        upload_to=settings.VOLUNTEER_PORTRAIT_DIR,
        max_length=256,
        null=True,
        blank=True,
    )

    # Set automatically by the auto_dormancy management command when last_login
    # exceeds volunteer_dormancy_months in SiteConfiguration. Does not restrict
    # access — purely informational. Clear it once you've made contact.
    login_inactive = models.BooleanField(
        default=False,
        help_text="Flagged by the auto-dormancy check: this volunteer has not logged in recently. Cleared manually after follow-up.",
    )

    # Roles
    roles = models.ManyToManyField(
        Role, db_table="Volunteer_Roles", blank=True
    )

    # Collective memberships
    collectives = models.ManyToManyField(
        "labs.Collective", blank=True, related_name="volunteers"
    )

    # Access rider
    access_intro = models.TextField(
        blank=True, max_length=500,
        help_text="A sentence or two about yourself for context (optional).",
    )
    access_needs = models.TextField(
        blank=True,
        help_text="What you need to participate in shifts and events at the venue.",
    )
    access_links = models.TextField(
        blank=True, max_length=500,
        help_text="Links to further information about your access needs (optional).",
    )

    # Emergency contact (panopticon-visible only; not included in the directory)
    emergency_contact_name = models.CharField(max_length=128, blank=True)
    emergency_contact_relationship = models.CharField(max_length=64, blank=True)
    emergency_contact_phone = models.CharField(max_length=64, blank=True)

    # Directory sharing controls — all opt-in, default off.
    # `dir_share_listed` is the master toggle (am I in the directory at all?).
    # When listed, `dir_share_name_style` chooses how the name appears.
    NAME_STYLE_FULL = "full"
    NAME_STYLE_INITIAL = "initial"
    NAME_STYLE_CHOICES = [
        (NAME_STYLE_FULL, "Full name"),
        (NAME_STYLE_INITIAL, "First name + initial"),
    ]
    dir_share_listed = models.BooleanField(default=False)
    dir_share_name_style = models.CharField(
        max_length=10, choices=NAME_STYLE_CHOICES, default=NAME_STYLE_FULL,
    )
    dir_share_pronouns = models.BooleanField(default=False)
    dir_share_email = models.BooleanField(default=False)
    dir_share_phone = models.BooleanField(default=False)
    dir_share_access_rider = models.BooleanField(default=False)
    dir_share_collectives = models.BooleanField(default=False)

    # Weekly digest email opt-in
    weekly_digest = models.BooleanField(
        default=False,
        help_text="Send a weekly email summary of upcoming shifts, new programme items, and starred events.",
    )
    last_digest_sent_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set automatically after each digest send. Used to compute the 'new on programme' lookback window.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Volunteers"

    def save(self, *args, **kwargs):
        # Keep `active` in sync with `status` — `status` is the source of truth.
        self.active = self.status == self.STATUS_ACTIVE
        try:
            current_portrait_file = self.portrait.file.name
        except (OSError, ValueError):
            current_portrait_file = None

        if current_portrait_file != self.__original_portrait:
            # Delete old image:
            if self.__original_portrait:
                logging.info(
                    f"Deleting old volunteer portrait '{self.__original_portrait}'"
                )
                try:
                    os.unlink(self.__original_portrait)
                except OSError as err:
                    logging.error(
                        f"Failed deleting old volunteer portrait '{self.__original_portrait}': {err}"
                    )
                self.__original_portrait = None

        return super().save(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store current filename of portrait (if any) so that, at save, changes
        # can be detected and the old image deleted:
        try:
            self.__original_portrait = (
                self.portrait.file.name if self.portrait else None
            )
        except (OSError, ValueError):
            self.__original_portrait = None

    def directory_display_name(self):
        """Name string to show in the directory, honouring sharing prefs."""
        if not self.dir_share_listed:
            return ""
        if self.dir_share_name_style == self.NAME_STYLE_INITIAL:
            parts = self.member.name.split()
            if len(parts) >= 2:
                return f"{parts[0]} {parts[-1][0]}."
        return self.member.name

    def is_old(self):
        return (
            self.created_at
            and self.created_at.date() <= settings.DAWN_OF_TOOLKIT
        )

    def latest_general_training_record(self):
        if self.pk is None:
            return None
        records = self.training_records.filter(
            training_type=TrainingRecord.GENERAL_TRAINING
        ).order_by("-training_date")[:1]
        return records[0] if records else None


class TrainingRecord(models.Model):
    ROLE_TRAINING = "R"
    GENERAL_TRAINING = "G"
    GENERAL_TRAINING_DESC = "General Safety Training"

    TRAINING_TYPE_CHOICES = (
        (ROLE_TRAINING, "Role Specific Training"),
        (GENERAL_TRAINING, GENERAL_TRAINING_DESC),
    )

    class Meta:
        db_table = "TrainingRecords"
        ordering = ["role", "training_date", "volunteer"]

    volunteer = models.ForeignKey(
        Volunteer, related_name="training_records", on_delete=models.CASCADE
    )
    training_type = models.CharField(
        max_length=1, choices=TRAINING_TYPE_CHOICES, blank=False
    )

    role = models.ForeignKey(
        Role,
        related_name="training_records",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    # Default to when the record is created:
    training_date = models.DateField(default=datetime.date.today)
    trainer = models.CharField(max_length=128)
    notes = models.TextField(blank=True)

    def __repr__(self):
        return (
            f"TrainingRecord(volunteer={self.volunteer_id}, type={self.training_type}, "
            f"role={self.role_id}, date={self.training_date} trainer={self.trainer})"
        )

    def clean(self):
        if self.training_type == self.ROLE_TRAINING and self.role is None:
            raise ValidationError({"role": "This field is required."})
        elif (
            self.training_type == self.GENERAL_TRAINING
            and self.role is not None
        ):
            raise ValidationError(
                {
                    "role": "Training role must not be set for 'General Safety' "
                    "training records."
                }
            )

    def save(self, *args, **kwargs):
        if self.training_type not in (
            self.GENERAL_TRAINING,
            self.ROLE_TRAINING,
        ):
            raise django.db.IntegrityError("training_type invalid or missing")
        if self.training_type == self.ROLE_TRAINING and self.role is None:
            raise django.db.IntegrityError(
                "role not defined but training_type is role"
            )
        return super().save(*args, **kwargs)

    def has_expired(self, expiry_age=None):
        if expiry_age is None:
            expiry_age = get_site_config().default_training_expiry_months
        threshold = timezone_now().date() - monthdelta(expiry_age)
        return self.training_date and self.training_date < threshold


class AnonymisationLog(models.Model):
    # Audit trail for GDPR right-to-erasure actions. Stores no PII — only
    # enough to demonstrate that a request was acted on and when.
    volunteer_pk = models.IntegerField()
    performed_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "AnonymisationLog"

    def __str__(self):
        return f"Anonymisation of volunteer pk={self.volunteer_pk} at {self.created_at}"


class PanopticonGrant(models.Model):
    """Audit record created when a user is granted Panopticon (is_superuser) access.

    Exists for accountability: the access list page shows who has Panopticon
    access, why, when it was granted, and when it was last reviewed.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="panopticon_grant"
    )
    reason = models.TextField(
        help_text="Why does this person have Panopticon access?"
    )
    granted_at = models.DateField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    last_reviewed_at = models.DateField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "PanopticonGrant"
        ordering = ["granted_at"]

    def __str__(self):
        return f"Panopticon grant for {self.user.username}"

    def review_overdue(self):
        """True if no review has been recorded or it is more than 365 days old."""
        if not self.last_reviewed_at:
            return True
        delta = datetime.date.today() - self.last_reviewed_at
        return delta.days > 365


class ProgrammerGrant(models.Model):
    """Lightweight record created when a user is granted Programmer group membership."""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="programmer_grant"
    )
    granted_at = models.DateField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        db_table = "ProgrammerGrant"
        ordering = ["user__username"]

    def __str__(self):
        return f"Programmer grant for {self.user.username}"
