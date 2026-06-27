import logging

from django.db import models

logger = logging.getLogger(__name__)


DEFAULT_FILMS_START_BANNER_TEXT = (
    "We don't show adverts or trailers, so please arrive promptly, as films "
    "start as soon as most people have arrived."
)


class SiteConfiguration(models.Model):
    """Singleton (pk=1) holding runtime-editable site settings.

    A Panopticon edits these via /toolkit/site-config/ instead of needing a
    code deploy. The DB row is the source of truth; settings.py values are
    only used to seed the row in the initial data migration.
    """

    # --- Display & UX ---
    films_start_on_time = models.BooleanField(
        default=False,
        help_text="Show a banner on public event detail pages stating that films start on time.",
    )
    films_start_on_time_banner_text = models.TextField(
        blank=True,
        default=DEFAULT_FILMS_START_BANNER_TEXT,
        help_text="The banner copy. Only shown when 'Films start on time' is enabled.",
    )
    rota_show_tags = models.BooleanField(
        default=True,
        help_text=(
            "Show coloured event tag badges (e.g. 'family-friendly', 'accessible') on the "
            "edit rota page, along with a filter bar for narrowing the rota by tag. "
            "Useful once events are consistently tagged; turn off to reduce visual clutter "
            "if tags are rarely used at your venue."
        ),
    )
    rota_clear_email_prompt_enabled = models.BooleanField(
        default=True,
        help_text=(
            "When a volunteer removes themselves from a rota slot, show a reminder "
            "prompt asking them to notify the volunteers list. "
            "Edit the prompt text in the field below."
        ),
    )
    rota_clear_email_prompt_text = models.TextField(
        blank=True,
        default=(
            "Slot cleared.\n"
            "Please consider emailing {email} to say that the shift needs covering."
        ),
        help_text=(
            "The message shown when a volunteer clears their rota slot. "
            "Use {email} as a placeholder; it will be replaced with the volunteers list address "
            "set in the 'Volunteers list email' field below. "
            "Only shown when 'Rota clear email prompt' is enabled above."
        ),
    )
    vols_email = models.EmailField(
        blank=True,
        default="",
        max_length=254,
        verbose_name="Volunteers list email",
        help_text=(
            "The email address of the volunteers mailing list. "
            "Shown in the rota slot-cleared prompt (see above) when the {email} placeholder is used. "
            "Seeded from the VENUE settings on first run."
        ),
    )
    show_archive_images = models.BooleanField(
        default=True,
        help_text=(
            "If off, hide event images on the public site for events whose "
            "showings all predate the 'Images start date' below. Volunteers "
            "(authenticated users) always see images. Useful for taking "
            "pre-archive imagery offline quickly (e.g. copyright issues)."
        ),
    )
    images_start_date = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "Cutoff date for the 'Show archive images' setting above. Has no "
            "effect unless that setting is off. Leave blank to disable hiding."
        ),
    )

    # --- Age ratings ---
    age_rating_choices = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Age-rating options shown in the event edit form. "
            "e.g. BBFC: U / PG / 12A / 12 / 15 / 18. "
            "Leave the list empty to hide the age restriction field entirely."
        ),
    )

    # --- Terminology ---
    # What this venue calls a single dated occurrence of an event. Cinemas
    # screen "showings"; a mixed-programme venue may prefer "dates" so the word
    # also fits a workshop or club-night run. Defaults are cinema-first because
    # this codebase is primarily used by cinemas (see SPEC: good neighbours).
    occurrence_noun = models.CharField(
        max_length=32,
        default="showing",
        verbose_name="Occurrence noun (singular)",
        help_text=(
            "Lowercase singular word for one dated occurrence of an event "
            "(e.g. 'showing' for a cinema, 'date' or 'session' elsewhere). "
            "Used throughout the event-editing UI."
        ),
    )
    occurrence_noun_plural = models.CharField(
        max_length=32,
        default="showings",
        verbose_name="Occurrence noun (plural)",
        help_text="Plural of the occurrence noun (e.g. 'showings', 'dates').",
    )
    confirm_label = models.CharField(
        max_length=48,
        default="Confirm",
        help_text=(
            "Label on the button that makes an occurrence public and opens its rota. "
            "Cinemas may prefer the short 'Confirm'; venues wanting to spell out the "
            "dual effect can use e.g. 'Publish & open rota'."
        ),
    )

    # --- Calendar ---
    calendar_slot_min_hour = models.PositiveSmallIntegerField(
        default=10,
        help_text=(
            "Earliest hour shown in the 3-day and week calendar views (0–23). "
            "Events before this time are still shown but the grid starts here. "
            "Default 10 hides the dead early-morning hours."
        ),
    )

    # --- Break-even calculator ---
    breakeven_guidance_note = models.TextField(
        blank=True,
        default=(
            "Opening the doors at S&S costs roughly £200 before any additional costs —"
            " make sure this is factored in above."
            " Finance Collective sign-off required if total costs exceed"
            " £500 (standard) or £750 (music)."
        ),
        help_text=(
            "Guidance note shown below the break-even calculator on the event hub page. "
            "Plain text."
        ),
    )
    breakeven_fc_standard_threshold = models.PositiveSmallIntegerField(
        default=500,
        help_text=(
            "Gross cost threshold (£) for a standard event above which a Finance Collective "
            "sign-off is required. Triggers a warning in the break-even calculator."
        ),
    )
    breakeven_fc_music_threshold = models.PositiveSmallIntegerField(
        default=750,
        help_text=(
            "Gross cost threshold (£) for a music event above which a Finance Collective "
            "sign-off is required. Triggers a warning in the break-even calculator."
        ),
    )

    # --- Programme limits ---
    max_count_per_role = models.PositiveSmallIntegerField(
        default=8,
        help_text="Maximum number of slots per role on a single showing's rota.",
    )
    max_showing_dates_shown = models.PositiveSmallIntegerField(
        default=5,
        help_text=(
            "Maximum number of future showing dates to display on the public event "
            "detail page before collapsing extras into a 'Show more' section. "
            "Set to 0 to always show all dates."
        ),
    )
    programme_copy_summary_max_chars = models.PositiveSmallIntegerField(
        default=450,
        help_text="Maximum length of an event's copy summary (the listing blurb).",
    )
    programme_event_terms_min_words = models.PositiveSmallIntegerField(
        default=3,
        help_text="Minimum word count in an event's terms before it can be confirmed.",
    )
    programme_media_max_size_mb = models.PositiveSmallIntegerField(
        default=5,
        help_text="Maximum size in megabytes for an uploaded event image.",
    )
    thumbnail_crop_width = models.PositiveSmallIntegerField(
        default=600,
        help_text=(
            "Width of the programme card image ratio (e.g. 2 for 2:3, or 600 for 600×900). "
            "Used when padding uploaded images with letterbox bars and when generating typographic posters. "
            "Default 600 (2:3 portrait)."
        ),
    )
    thumbnail_crop_height = models.PositiveSmallIntegerField(
        default=900,
        help_text=(
            "Height of the programme card image ratio (e.g. 3 for 2:3, or 900 for 600×900). "
            "Default 900 (2:3 portrait)."
        ),
    )
    programme_accent_colour = models.CharField(
        max_length=7,
        default="#e91e8c",
        verbose_name="Programme accent colour",
        help_text=(
            "The primary brand colour used in the public programme (hex, e.g. #e91e8c). "
            "Shown as a suggested bar colour when editing event images."
        ),
    )

    # --- Mailout ---
    mailout_details_days_ahead = models.PositiveSmallIntegerField(
        default=9,
        help_text=(
            "This setting controls the members mailout — the periodic programme newsletter "
            "sent to people on the membership list (not volunteers, not the public website). "
            "Events whose next showing falls within this many days from the mailout send date "
            "will have their full event copy (synopsis, terms, etc.) included in the mailout. "
            "Events further away than this threshold, but within the listings window below, "
            "appear as brief listings only. Default is 9 days."
        ),
    )
    mailout_listings_days_ahead = models.PositiveSmallIntegerField(
        default=14,
        help_text=(
            "The outer window for the members mailout. Events whose next showing falls within "
            "this many days from the mailout send date will appear as brief listings (title, "
            "date, and time) even if they are outside the detailed copy window above. "
            "Events beyond this window are not included in the mailout at all. Default is 14 days."
        ),
    )

    # --- Membership ---
    membership_length_days = models.PositiveSmallIntegerField(
        default=365,
        help_text="Default length of a new membership in days. Only used when membership expiry is enabled.",
    )
    default_training_expiry_months = models.PositiveSmallIntegerField(
        default=12,
        help_text=(
            "Months after which a training record is shown as 'out of date' on the volunteer list. "
            "This is informational only — it does not affect rota sign-up. "
            "The training gate checks for any record, however old."
        ),
    )

    # --- Dashboard ---
    rota_gap_min_missing = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            "Show the 'rota gaps' dashboard widget for showings with at least this many "
            "unfilled required slots. Set to 0 to use only the percentage threshold."
        ),
    )
    rota_gap_min_pct = models.PositiveSmallIntegerField(
        default=0,
        help_text=(
            "Show the 'rota gaps' dashboard widget for showings where at least this "
            "percentage of required slots are unfilled (0–100). Set to 0 to use only "
            "the count threshold."
        ),
    )

    # --- Stats & programming ---
    programming_min_event_shifts = models.PositiveSmallIntegerField(
        default=10,
        verbose_name="Programming eligibility threshold",
        help_text=(
            "Minimum confirmed non-training shifts before a volunteer is considered ready to "
            "programme their own event. Shown on the volunteer stats page as a target — "
            "never enforced by the system."
        ),
    )
    stats_programming_note = models.TextField(
        blank=True,
        default="",
        verbose_name="Programming eligibility note",
        help_text=(
            "Optional extra text shown below the programming eligibility count on the volunteer stats page. "
            "Plain text only. Leave blank to show nothing."
        ),
    )
    stats_training_tag_slugs = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Tags excluded from shift count",
        help_text=(
            "Events tagged with any of these are excluded from a volunteer's confirmed shift "
            "count on the stats page. Use this to separate training and induction sessions "
            "from regular programming activity."
        ),
    )

    # --- Volunteers ---
    general_training_enabled = models.BooleanField(
        default=True,
        help_text=(
            "Show General Safety Training records and prompts across the volunteer list, "
            "profile 'Key dates', and training report. Disable if your venue does not run "
            "General Safety Training — role-specific training records remain available "
            "regardless of this setting. The GST training type is also hidden from the "
            "'add training record' form when disabled."
        ),
    )
    volunteer_dormancy_days = models.PositiveSmallIntegerField(
        default=365,
        help_text=(
            "Mark active volunteers as Dormant if they have not logged in for this many days. "
            "Dormant is a soft, reversible label: it does not disable login or rota signup. "
            "Set to 0 to never auto-mark dormancy. "
            "Applied by the 'auto_dormancy' management command (run periodically, e.g. via cron) "
            "and surfaced on the volunteer pool-health dashboard."
        ),
    )
    volunteer_never_logged_in_grace_days = models.PositiveSmallIntegerField(
        default=90,
        help_text=(
            "Mark active volunteers who have never logged in as Dormant once this many days "
            "have passed since their account was created (they were inducted but never engaged — "
            "likely re-induction candidates). Set to 0 to never auto-mark these. "
            "Applied by the 'auto_dormancy' command."
        ),
    )
    volunteer_purge_days = models.PositiveSmallIntegerField(
        default=1095,
        help_text=(
            "Flag dormant/retired volunteers as candidates for anonymisation (GDPR data "
            "minimisation) once their last activity is older than this many days. "
            "Set to 0 to never flag purge candidates. Surfaced on the pool-health dashboard; "
            "acted on only via the manual 'purge_stale_volunteers' command — never automatically."
        ),
    )

    DIGEST_DAY_DISABLED = 0
    DIGEST_DAY_CHOICES = [
        (0, "Disabled"),
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]
    volunteer_digest_day = models.PositiveSmallIntegerField(
        default=4,
        choices=DIGEST_DAY_CHOICES,
        help_text=(
            "Day of the week on which the volunteer digest email is sent. "
            "The scheduler fires the digest command daily at 09:00; this setting "
            "controls which day it actually sends. Set to Disabled to suppress sending "
            "without stopping the scheduler container."
        ),
    )

    # --- Guidance URLs ---
    image_copyright_guidance_url = models.URLField(
        blank=True,
        default="",
        max_length=500,
        help_text="Link shown next to the image upload field — e.g. a Nextcloud doc on image rights.",
    )
    alt_text_guidance_url = models.URLField(
        blank=True,
        default="https://design102.blog.gov.uk/2022/01/14/whats-the-alternative-how-to-write-good-alt-text/",
        max_length=500,
        help_text=(
            "Alt text (alternative text) is a short written description of an image, "
            "read aloud by screen readers for blind and partially-sighted users and shown "
            "when an image fails to load. This field sets a link shown next to the alt text "
            "input when uploading event images — point it at a guide to writing good alt text. "
            "Leave blank to hide the link."
        ),
    )
    access_rider_guidance_url = models.URLField(
        blank=True,
        default="https://weareunlimited.org.uk/resource/creating-your-own-access-rider/",
        max_length=500,
        help_text="Link shown in the Access Rider section of the volunteer profile — guidance on writing an access rider. Leave blank to hide the link.",
    )
    ticket_link_guidance_html = models.TextField(
        blank=True,
        default="",
        verbose_name="Ticket link setup guidance",
        help_text=(
            "HTML shown in a collapsible panel directly below the ticket link field on the "
            "event edit form. Use this to guide programmers through setting up tickets on "
            "your chosen platform. Leave blank to hide the panel entirely."
        ),
    )
    film_programming_guide_url = models.URLField(
        blank=True,
        default="",
        verbose_name="Film programming guide URL",
        help_text=(
            "URL linked at the bottom of the ticket link setup guide panel on the event edit form. "
            "Typically a full guide to your ticketing platform. Leave blank to omit the link."
        ),
    )

    # --- External APIs ---
    omdb_api_key = models.CharField(
        blank=True,
        default="",
        max_length=256,
        verbose_name="OMDb API key",
        help_text=(
            "API key for the Open Movie Database (OMDb). Used for film search and metadata import. "
            "Get a free key at https://www.omdbapi.com/apikey.aspx. "
            "If set here, this takes precedence over the OMDB_API_KEY environment variable."
        ),
    )
    certificate_lookup_url = models.CharField(
        blank=True,
        default="https://www.bbfc.co.uk/search?q={title}",
        max_length=512,
        verbose_name="Certificate lookup URL",
        help_text=(
            "URL template for looking up a film's certificate. "
            "Use {title} and {year} as placeholders — they will be URL-encoded and substituted when the link is generated. "
            "Example (BBFC): https://www.bbfc.co.uk/search?q={title} "
            "Leave blank to hide the lookup link."
        ),
    )

    # --- Collectives public page ---
    collectives_intro = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Introductory copy shown at the top of the public /labs/collectives/ page. "
            "Plain text. Leave blank to use the built-in default."
        ),
    )
    collectives_mailing_list_signup_url = models.URLField(
        blank=True,
        default="",
        max_length=500,
        verbose_name="Mailing list sign-up URL",
        help_text=(
            "URL for the mailing list sign-up page, shown in the help box on the "
            "<a href='/toolkit/labs/collectives/'>Collectives page</a>. "
            "Leave blank to hide the mailing list hint entirely."
        ),
    )

    # --- Donations page ---
    donations_intro = models.TextField(
        blank=True,
        default=(
            "<p>The most valuable things you can give us are your time, energy, and ideas. "
            "If you want to get involved, the best place to start is by volunteering at events "
            "or joining one of our working groups.</p>"
            "<p>That said, we do sometimes need physical things too, and this page lists what’s "
            "currently useful. Before bringing anything, please check the status: "
            "<strong>Wanted</strong> means yes please; <strong>Check first</strong> means it might "
            "work but talk to us first; <strong>Not needed</strong> means we’re already well "
            "supplied or can’t use it.</p>"
            "<p>One of our most precious resources as a DIY space is space itself. We share the "
            "building across a lot of different groups and uses, and it’s much easier to add "
            "things than to remove them. Please don’t drop anything off without checking first, "
            "even if it seems obviously useful.</p>"
        ),
        help_text="Introductory copy shown at the top of the public donations page. HTML.",
    )

    # --- Public site navigation ---
    show_donations_in_public_nav = models.BooleanField(
        default=False,
        help_text=(
            "Show a 'Donations wishlist' link in the public site navigation, "
            "pointing at the labs donations list. Off by default."
        ),
    )

    # --- Site-wide banner ---
    banner_active = models.BooleanField(
        default=False,
        help_text=(
            "Show a site-wide announcement banner at the top of every page "
            "(public and toolkit) for important notices."
        ),
    )
    BANNER_LEVEL_INFO = "info"
    BANNER_LEVEL_WARNING = "warning"
    BANNER_LEVEL_CRITICAL = "critical"
    BANNER_LEVEL_CHOICES = [
        (BANNER_LEVEL_INFO, "Info (blue)"),
        (BANNER_LEVEL_WARNING, "Warning (amber)"),
        (BANNER_LEVEL_CRITICAL, "Critical (red)"),
    ]
    banner_level = models.CharField(
        max_length=10,
        choices=BANNER_LEVEL_CHOICES,
        default=BANNER_LEVEL_INFO,
        help_text="Colour scheme for the banner.",
    )
    banner_text = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Banner content. Plain text; line breaks are preserved. "
            "Edit this and re-save to issue an updated notice — visitors who "
            "previously dismissed the banner will see the new version."
        ),
    )
    banner_dismissible = models.BooleanField(
        default=True,
        help_text=(
            "Allow visitors to dismiss the banner. Their choice is stored in "
            "their browser only, and resets when the banner text changes."
        ),
    )

    # --- Community exchange ---
    community_exchange_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable the community exchange — a browseable catalogue where volunteers can lend tools "
            "or give away items to one another. When off, the section is hidden from the nav."
        ),
    )

    # --- Lost & found ---
    lost_and_found_retain_days = models.PositiveSmallIntegerField(
        default=60,
        help_text=(
            "Number of days to retain unclaimed lost and found items before flagging for disposal. "
            "Set to 0 to disable flagging."
        ),
    )

    # --- Bulletins ---
    bulletin_default_expiry_days = models.PositiveSmallIntegerField(
        default=30,
        help_text=(
            "How many days a bulletin stays active if no explicit expiry is set. "
            "Default is 30. Set to 0 to keep bulletins active indefinitely by default."
        ),
    )
    bulletin_guidance = models.TextField(
        blank=True,
        default=(
            "Use bulletins for short notices relevant to the whole volunteer community: "
            "policy changes, updated contact details, new resources, or anything a volunteer "
            "needs to know before their next event.\n\n"
            'Good examples: "Keyholders can now be contacted via keyholders@lists.example.com '
            '— please use this if your event needs a keyholder." / "The Managing Immediate '
            'Risk Policy has been updated and applies to all volunteers: [link]" / "The '
            "projection booth door code has changed — use the code previously assigned to the "
            'cleaning cupboard."\n\n'
            "Before you post, remember that bulletins go to all 500+ active volunteers. "
            "If you need to send a callout ahead of an event, mailing lists are a better route."
        ),
        help_text=(
            "Guidance shown on the 'Post a bulletin' form. Use this to set local "
            "conventions: what kinds of notices belong here, how to write them, "
            "and examples of good and bad bulletins."
        ),
    )

    # --- Event links ---
    eventlink_extra_allowed_domains = models.TextField(
        blank=True,
        default="",
        help_text=(
            "Extra domains allowed for event resource links, one per line. "
            "Subdomains are accepted (e.g. 'nextcloud.example.org' also allows "
            "'files.nextcloud.example.org'). Built-in domains (riseup.net, "
            "nextcloud.com/org, chat.whatsapp.com, linktr.ee) are always allowed."
        ),
    )

    BULLETIN_POST_ALL = "all"
    BULLETIN_POST_PROGRAMMER = "programmer"
    BULLETIN_POST_PANOPTICON = "panopticon"
    BULLETIN_POST_CHOICES = [
        (BULLETIN_POST_ALL, "All volunteers"),
        (BULLETIN_POST_PROGRAMMER, "Programmers and Panopticon"),
        (BULLETIN_POST_PANOPTICON, "Panopticon only"),
    ]
    bulletin_post_permission = models.CharField(
        max_length=12,
        choices=BULLETIN_POST_CHOICES,
        default=BULLETIN_POST_PROGRAMMER,
        help_text="Who can post new bulletins.",
    )

    # --- Runtime-configurable feature access levels ---
    PERM_VOLUNTEER = "volunteer"
    PERM_PROGRAMMER = "programmer"
    PERM_PANOPTICON = "panopticon"
    PERMISSION_LEVEL_CHOICES = [
        (PERM_VOLUNTEER, "All volunteers"),
        (PERM_PROGRAMMER, "Programmer+"),
        (PERM_PANOPTICON, "Panopticon only"),
    ]

    perm_diary_read = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_VOLUNTEER,
        verbose_name="Diary — view diary list",
        help_text="Who can view the diary editing list (read-only for volunteers; event editing always requires Programmer+).",
    )
    perm_diary_calendar = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — calendar",
        help_text="Who can access the calendar edit view.",
    )
    perm_programming_queue_read = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_VOLUNTEER,
        verbose_name="Diary — programming queue (view)",
        help_text="Who can view the programming queue.",
    )
    perm_programming_queue_write = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — programming queue (change status)",
        help_text="Who can approve, return, or skip events in the programming queue.",
    )
    perm_event_templates = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — event templates",
        help_text="Who can access event templates (list and detail). Template import always requires Panopticon.",
    )
    perm_event_tags = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — event tags",
        help_text="Who can edit event tags.",
    )
    perm_roles = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — roles",
        help_text="Who can edit rota roles.",
    )
    perm_rooms = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — rooms",
        help_text="Who can edit rooms.",
    )
    perm_diary_reports = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — reports",
        help_text="Who can access copy, terms, and text reports.",
    )
    perm_printed_programmes = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Diary — printed programmes",
        help_text="Who can upload printed programmes.",
    )
    perm_rota_vacancies = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_VOLUNTEER,
        verbose_name="Rota — vacancies page",
        help_text="Who can see the rota vacancies page.",
    )
    perm_donations_manage = models.CharField(
        max_length=12,
        choices=PERMISSION_LEVEL_CHOICES,
        default=PERM_PROGRAMMER,
        verbose_name="Website — donations manage",
        help_text="Who can access the donations management page.",
    )

    # --- Last-gasp re-engagement email ---
    last_gasp_email_enabled = models.BooleanField(
        default=False,
        verbose_name="Enable last-gasp email features",
        help_text=(
            "A last-gasp email is a final, optional re-engagement message sent to a volunteer "
            "before their account is anonymised or deleted under data-retention rules — a courtesy "
            "“we’re about to remove your data, here’s a chance to come back” note. "
            "When enabled, the pool health page shows a button to send one to each purge candidate. "
            "(The email-address export, for sending outside the toolkit, is always available regardless of this setting.)"
        ),
    )
    last_gasp_email_subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Subject line. Use {name} for the volunteer's name and {venue} for the venue name.",
    )
    last_gasp_email_body = models.TextField(
        blank=True,
        help_text=(
            "Body text. Use {name} for the volunteer's name and {venue} for the venue name. "
            "Can be left blank even when the feature is enabled — the compose page will still open "
            "so you can write a message from scratch each time."
        ),
    )
    last_gasp_cooldown_days = models.PositiveSmallIntegerField(
        default=30,
        help_text="How many days must pass before a second last-gasp email can be sent to the same volunteer.",
    )

    # --- Suspension email ---
    suspension_email_subject = models.CharField(
        max_length=300,
        blank=True,
        default="Your volunteer account at {venue}",
        verbose_name="Suspension email subject",
        help_text=(
            "Subject line for the email offered when suspending a volunteer. "
            "Supports {name} and {venue} variables."
        ),
    )
    suspension_email_body = models.TextField(
        blank=True,
        default=(
            "Hi {name},\n\n"
            "This is to let you know that your volunteer account at {venue} has been suspended. "
            "Your login is currently disabled and you have been removed from upcoming shifts.\n\n"
            "If you have any questions or would like to discuss this, please get in touch.\n\n"
            "Best wishes,\n{venue}"
        ),
        verbose_name="Suspension email body",
        help_text=(
            "Body of the email offered when suspending a volunteer. "
            "Supports {name} and {venue} variables."
        ),
    )

    # --- Structured cost terms ---
    structured_cost_terms_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable structured cost fields (cost type, flat fee, % split, etc.) on event edit forms. "
            "When on, programmers can record the deal type directly rather than free-texting it into Terms. "
            "The Terms textarea remains available for unusual arrangements and legacy records."
        ),
    )
    structured_cost_required = models.BooleanField(
        default=False,
        help_text=(
            "Require cost type to be set (to something other than TBC) before any showing can be confirmed. "
            "Only takes effect when structured cost terms are enabled above. "
            "When cost type is set, the terms word-count check is automatically waived; "
            "TBC still falls back to the terms word-count check."
        ),
    )

    _CACHE_KEY = "diary.site_config.v1"

    class Meta:
        db_table = "SiteConfiguration"
        verbose_name = "Site configuration"
        verbose_name_plural = "Site configuration"

    def __str__(self):
        return "Site configuration"

    @staticmethod
    def _passes_level(user, level):
        """Return True if user meets the given PERM_* access level."""
        if level == SiteConfiguration.PERM_VOLUNTEER:
            return user.has_perm("diary.change_rotaentry")
        if level == SiteConfiguration.PERM_PROGRAMMER:
            return user.has_perm("toolkit.write")
        return user.is_superuser

    def save(self, *args, **kwargs):
        # Singleton: always pk=1
        self.pk = 1
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete(self._CACHE_KEY)

    def delete(self, *args, **kwargs):
        # Don't allow the singleton to be deleted
        pass

    @classmethod
    def load(cls):
        # Cache the singleton to avoid a SELECT per render. Local-memory
        # cache is per-worker; the 5-minute TTL bounds staleness in other
        # workers after a save.
        from django.core.cache import cache

        config = cache.get(cls._CACHE_KEY)
        if config is None:
            config, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls._CACHE_KEY, config, timeout=300)
        return config


# Single source of truth for how SiteConfiguration fields are grouped on the
# Panopticon edit page. The dict is insertion-ordered (Python 3.7+): section
# order is the key order, field order within a section is the list order.
#
# - SiteConfigurationForm auto-derives its field set from the model `_meta`
#   via `Meta.exclude = ("id",)`, so it independently picks up every model
#   field — the dict does not feed the form.
# - edit_site_configuration renders by iterating this dict.
# - The perm_* fields are intentionally NOT here: they are rendered via the
#   separate permission_rows table in the edit-site-configuration view, with
#   fixed rows interleaved; grouped_fields would double-render them.
# - toolkit/diary/tests/test_site_config.py enforces that every model field
#   is present on the form, and that every form field appears in either
#   grouped_fields OR permission_rows — so adding a setting means declaring
#   it on the model *and* adding it to SITE_CONFIG_FIELD_GROUPS (or to the
#   permission_rows list in the view), or the test fails loudly.
SITE_CONFIG_FIELD_GROUPS = {
    "Display & UX": [
        "films_start_on_time",
        "films_start_on_time_banner_text",
        "rota_show_tags",
        "rota_clear_email_prompt_enabled",
        "rota_clear_email_prompt_text",
        "vols_email",
        "show_archive_images",
        "images_start_date",
    ],
    "Terminology": [
        "occurrence_noun",
        "occurrence_noun_plural",
        "confirm_label",
    ],
    "Age ratings": ["age_rating_choices"],
    "Break-even calculator": [
        "breakeven_guidance_note",
        "breakeven_fc_standard_threshold",
        "breakeven_fc_music_threshold",
    ],
    "Calendar": ["calendar_slot_min_hour"],
    "Programme limits": [
        "max_count_per_role",
        "max_showing_dates_shown",
        "programme_copy_summary_max_chars",
        "programme_event_terms_min_words",
        "programme_media_max_size_mb",
        "thumbnail_crop_width",
        "thumbnail_crop_height",
        "programme_accent_colour",
    ],
    "Mailout": ["mailout_details_days_ahead", "mailout_listings_days_ahead"],
    "Membership & volunteers": [
        "membership_length_days",
        "default_training_expiry_months",
        "general_training_enabled",
        "volunteer_dormancy_days",
        "volunteer_never_logged_in_grace_days",
        "volunteer_purge_days",
        "volunteer_digest_day",
    ],
    "Last-gasp re-engagement email": [
        "last_gasp_email_enabled",
        "last_gasp_email_subject",
        "last_gasp_email_body",
        "last_gasp_cooldown_days",
    ],
    "Suspension email": [
        "suspension_email_subject",
        "suspension_email_body",
    ],
    "Dashboard": ["rota_gap_min_missing", "rota_gap_min_pct"],
    "Volunteer stats": [
        "programming_min_event_shifts",
        "stats_programming_note",
        "stats_training_tag_slugs",
    ],
    "Guidance URLs": [
        "image_copyright_guidance_url",
        "alt_text_guidance_url",
        "access_rider_guidance_url",
        "ticket_link_guidance_html",
        "film_programming_guide_url",
    ],
    "Structured cost terms": [
        "structured_cost_terms_enabled",
        "structured_cost_required",
    ],
    "Community exchange": ["community_exchange_enabled"],
    "Lost & found": ["lost_and_found_retain_days"],
    "Bulletins": [
        "bulletin_default_expiry_days",
        "bulletin_guidance",
        "bulletin_post_permission",
    ],
    "Event links": ["eventlink_extra_allowed_domains"],
    "Collectives": [
        "collectives_intro",
        "collectives_mailing_list_signup_url",
    ],
    "Donations page": [
        "donations_intro",
        "show_donations_in_public_nav",
    ],
    "Site-wide banner": [
        "banner_active",
        "banner_level",
        "banner_text",
        "banner_dismissible",
    ],
    "External APIs": ["omdb_api_key", "certificate_lookup_url"],
}


def get_site_config():
    """Return the SiteConfiguration singleton, creating it on first call."""
    return SiteConfiguration.load()
