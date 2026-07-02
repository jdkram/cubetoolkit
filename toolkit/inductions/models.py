# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


DEFAULT_CONFIRMATION_SUBJECT = "[{venue}] Your induction sign-up — {session_title}"
DEFAULT_CONFIRMATION_BODY = (
    "Hi {name},\n\n"
    "You're signed up for the {session_title} at {venue}.\n\n"
    "When: {session_date}\n"
    "Where: {session_location}\n\n"
    "Add to your calendar: {calendar_url}\n\n"
    "See you there!"
)

DEFAULT_REMINDER_SUBJECT = "[{venue}] Reminder: induction coming up — {session_title}"
DEFAULT_REMINDER_BODY = (
    "Hi {name},\n\n"
    "Just a reminder that the {session_title} is coming up soon.\n\n"
    "When: {session_date}\n"
    "Where: {session_location}\n\n"
    "Add to your calendar: {calendar_url}\n\n"
    "See you there!"
)

DEFAULT_WELCOME_SUBJECT = "[{venue}] Welcome — set your toolkit password"
DEFAULT_WELCOME_BODY = (
    "Hi {name},\n\n"
    "Welcome to {venue}! You've been checked in to the {session_title} and "
    "your volunteer account is ready.\n\n"
    "Your username is: {username}\n\n"
    "Set your password using this link (valid for {validity}):\n\n"
    "{password_url}\n\n"
    "If the link has expired, you can request a new one by entering your email "
    "at: {password_reset_url}\n\n"
    "If you weren't expecting this email, you can safely ignore it."
)

DEFAULT_ACCESS_NEEDS_ACK_SUBJECT = "[{venue}] We've received your induction request"
DEFAULT_ACCESS_NEEDS_ACK_BODY = (
    "Hi {name},\n\n"
    "Thanks for getting in touch. We've received your request for a 1:1 induction "
    "and someone will be in touch soon to arrange a time that works for you.\n\n"
    "If you have any questions in the meantime, feel free to reply to this email."
)


class InductionsSettings(models.Model):
    """Singleton configuration for the inductions feature."""

    inductions_enabled = models.BooleanField(
        default=False,
        help_text="Enable the inductions sign-up workflow. When off, all public induction URLs return 404. If you're handling inductions sign-ups through another route (e.g. Google Forms) then you'll want to leave this unchecked.",
    )
    induction_purge_days = models.PositiveIntegerField(
        default=7,
        help_text="Days after a session date before pending/no-show sign-ups are automatically purged.",
    )
    default_max_signups = models.PositiveIntegerField(
        null=True, blank=True,
        help_text=(
            "Suggested starting value for the 'maximum sign-ups' field when creating a new "
            "induction session — each session's own cap can then be adjusted or cleared "
            "independently. Leave blank to suggest no cap."
        ),
    )

    # Email templates — use {name}, {venue}, {session_title}, {session_date},
    # {session_location}, {calendar_url}, {password_url}, {welcome_pack_url}, {validity}
    confirmation_email_subject = models.CharField(
        max_length=200, blank=True,
        help_text="Leave blank to use the default. Variables: {name} {venue} {session_title}",
    )
    confirmation_email_body = models.TextField(
        blank=True,
        help_text="Leave blank to use the default. Variables: {name} {venue} {session_title} {session_date} {session_location} {calendar_url}",
    )
    reminder_email_subject = models.CharField(
        max_length=200, blank=True,
        help_text="Leave blank to use the default.",
    )
    reminder_email_body = models.TextField(blank=True)

    welcome_email_subject = models.CharField(
        max_length=200, blank=True,
        help_text="Leave blank to use the default. Variables: {name} {username} {venue} {session_title} {validity} {password_url} {password_reset_url}",
    )
    welcome_email_body = models.TextField(blank=True)

    access_needs_ack_subject = models.CharField(max_length=200, blank=True, verbose_name="Access needs acknowledgement subject")
    access_needs_ack_body = models.TextField(blank=True, verbose_name="Access needs acknowledgement body")

    welcome_pack_url = models.CharField(
        max_length=500, blank=True,
        help_text="URL to a welcome pack document included in the welcome email.",
    )
    welcome_pack_label = models.CharField(
        max_length=100, default="Welcome pack",
        help_text="Link text for the welcome pack URL.",
    )

    privacy_policy_url = models.CharField(
        max_length=500, blank=True,
        help_text="URL to your GDPR/privacy policy. Linked from the sign-up consent checkbox. Leave blank to omit the link.",
    )
    privacy_policy_version = models.PositiveIntegerField(
        default=1,
        help_text="Bumped automatically when the policy is marked as updated. Volunteers who last consented to an earlier version are flagged for renewal and emailed immediately.",
    )
    privacy_policy_updated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the privacy policy was last marked as updated.",
    )
    access_needs_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Enable the 1:1 induction request page. "
            "Uncheck to hide it — useful if you don't currently offer 1:1 inductions."
        ),
    )
    access_needs_intro_text = models.TextField(
        blank=True,
        help_text=(
            "Introductory paragraph on the 1:1 induction request form. "
            "Leave blank to use the default text."
        ),
    )

    organiser_notification_email = models.EmailField(
        default="inductions@example.com",
        help_text=(
            "Email address that receives organiser notifications (new 1:1 request, "
            "session full, etc.). Set this to a real address before going live."
        ),
    )
    notify_on_each_signup = models.BooleanField(
        default=False,
        help_text=(
            "Also send a notification for every new sign-up, not just when a session reaches capacity. "
            "Useful for small or closely-watched sessions."
        ),
    )

    _CACHE_KEY = "inductions.settings.v1"

    class Meta:
        db_table = "InductionsSettings"
        verbose_name = "Inductions settings"
        verbose_name_plural = "Inductions settings"

    def __str__(self):
        return "Inductions settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self._CACHE_KEY)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        cfg = cache.get(cls._CACHE_KEY)
        if cfg is None:
            cfg, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls._CACHE_KEY, cfg, timeout=300)
        return cfg

    def get_confirmation_subject(self):
        return self.confirmation_email_subject or DEFAULT_CONFIRMATION_SUBJECT

    def get_confirmation_body(self):
        return self.confirmation_email_body or DEFAULT_CONFIRMATION_BODY

    def get_reminder_subject(self):
        return self.reminder_email_subject or DEFAULT_REMINDER_SUBJECT

    def get_reminder_body(self):
        return self.reminder_email_body or DEFAULT_REMINDER_BODY

    def get_welcome_subject(self):
        return self.welcome_email_subject or DEFAULT_WELCOME_SUBJECT

    def get_welcome_body(self):
        return self.welcome_email_body or DEFAULT_WELCOME_BODY

    def get_access_needs_ack_subject(self):
        return self.access_needs_ack_subject or DEFAULT_ACCESS_NEEDS_ACK_SUBJECT

    def get_access_needs_ack_body(self):
        return self.access_needs_ack_body or DEFAULT_ACCESS_NEEDS_ACK_BODY


def get_inductions_settings():
    return InductionsSettings.load()


def _default_purge_after():
    cfg = InductionsSettings.load()
    return timezone.now() + timezone.timedelta(days=cfg.induction_purge_days)


def _unique_slug(base_slug):
    slug = base_slug
    n = 1
    while InductionSession.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{n}"
        n += 1
    return slug


class InductionSession(models.Model):
    TYPE_REGULAR = "regular"
    TYPE_SMALL_GROUP = "small_group"
    TYPE_ONE_TO_ONE = "one_to_one"
    TYPE_CHOICES = [
        (TYPE_REGULAR, "Regular"),
        (TYPE_SMALL_GROUP, "Small group"),
        (TYPE_ONE_TO_ONE, "1:1 (access needs)"),
    ]

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_PURGED = "purged"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_PURGED, "Purged"),
    ]

    title = models.CharField(max_length=200)
    max_signups = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maximum sign-ups for this session. Leave blank for unlimited sign-ups.",
    )
    session_type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default=TYPE_REGULAR,
    )
    date = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    # JSON list of {"label": "...", "type": "text|checkbox|select", "required": bool, "options": [...]}
    custom_questions = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN,
    )
    slug = models.SlugField(max_length=100, unique=True)
    purge_after = models.DateTimeField(
        help_text=(
            "Personal details (name, email, and answers) for anyone still pending or marked "
            "no-show are automatically deleted after this date, and the session is marked "
            "'Purged'. Sign-ups who were checked in and already have a volunteer account are "
            "not affected. Runs automatically once a day — defaults to the session date plus "
            "the site-wide purge window (set in Inductions settings)."
        ),
    )
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_induction_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.title} ({self.date:%Y-%m-%d})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.title} {self.date:%m %d}")[:90] or "induction"
            self.slug = _unique_slug(base)
        if not self.purge_after:
            cfg = InductionsSettings.load()
            self.purge_after = self.date + timezone.timedelta(days=cfg.induction_purge_days)
        super().save(*args, **kwargs)

    def effective_capacity(self):
        """Return this session's sign-up cap, or None if unlimited."""
        return self.max_signups

    @property
    def is_full(self):
        if not self.pk:
            return False
        cap = self.effective_capacity()
        if cap is None:
            return False
        return self.signups.count() >= cap

    @property
    def checked_in_count(self):
        return self.signups.filter(status=InductionSignup.STATUS_CHECKED_IN).count()

    @property
    def pending_count(self):
        return self.signups.filter(status=InductionSignup.STATUS_PENDING).count()

    @property
    def total_count(self):
        return self.signups.count()


class InductionSignup(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CHECKED_IN = "checked_in"
    STATUS_NO_SHOW = "no_show"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CHECKED_IN, "Checked in"),
        (STATUS_NO_SHOW, "No show"),
    ]

    session = models.ForeignKey(
        InductionSession, on_delete=models.CASCADE, related_name="signups",
    )
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    custom_responses = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    volunteer = models.ForeignKey(
        "members.Volunteer",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="induction_signups",
    )
    desired_username = models.CharField(
        max_length=150,
        blank=True,
        help_text="If set, used as the volunteer's login username instead of auto-generating from name.",
    )
    phone = models.CharField(max_length=64, blank=True)
    address = models.CharField(max_length=128, blank=True)
    postcode = models.CharField(max_length=16, blank=True)
    signed_up_at = models.DateTimeField(auto_now_add=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="checked_in_signups",
    )

    class Meta:
        ordering = ["signed_up_at"]

    def __str__(self):
        return f"{self.name or '(purged)'} — {self.session}"

    @property
    def first_name(self):
        parts = (self.name or "").split(None, 1)
        return parts[0] if parts else ""

    @property
    def last_name(self):
        parts = (self.name or "").split(None, 1)
        return parts[1] if len(parts) > 1 else ""

    @property
    def preview_username(self):
        """Best-guess username for display before account creation. Not collision-checked."""
        if self.desired_username:
            return self.desired_username
        parts = (self.name or "").split()
        first = parts[0] if parts else "volunteer"
        last = parts[-1] if len(parts) > 1 else ""
        return f"{first}{last}"


class InductionRequest(models.Model):
    """Access-needs induction request queue (1:1 pathway)."""

    STATUS_PENDING = "pending"
    STATUS_CONTACTED = "contacted"
    STATUS_SCHEDULED = "scheduled"
    STATUS_COMPLETED = "completed"
    STATUS_DECLINED = "declined"
    STATUS_PURGED = "purged"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONTACTED, "Contacted"),
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_PURGED, "Purged"),
    ]

    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    access_needs = models.TextField()
    rough_availability = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    linked_session = models.ForeignKey(
        InductionSession,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="access_requests",
    )
    volunteer = models.ForeignKey(
        "members.Volunteer",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="induction_request",
    )
    notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    purge_after = models.DateTimeField()

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.name or '(purged)'} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.purge_after:
            cfg = InductionsSettings.load()
            # Stale requests that never get scheduled are purged after purge_days * 4
            # (reasonable window to follow up before data is dropped)
            self.purge_after = timezone.now() + timezone.timedelta(
                days=cfg.induction_purge_days * 4
            )
        super().save(*args, **kwargs)
