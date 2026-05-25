from toolkit.settings_common import *

ROOT_URLCONF = "toolkit.urls_flat"

# CODE-LEVEL feature flags — changing these in settings_*.py takes effect on restart.
MULTIROOM_ENABLED = True
HTML_MAILOUT_ENABLED = True
MEMBERSHIP_EXPIRY_ENABLED = True

VENUE = {
    "name": "Star and Shadow",
    "longname": "Star and Shadow",
    "cinemaname": "Star and Shadow Cinema",
    "url": "https://starandshadow.org.uk/",
    "contact_page": "/about/contact/",
    "piwik_id": 29,
    "twitter": "https://twitter.com/StarAndShadow",
    "facebook": "https://www.facebook.com/StarAndShadow",
    "instagram": "https://www.instagram.com/starandshadowcinema/",
    "bluesky": "",   # TODO: add Bluesky handle when confirmed
    "mastodon": "",  # TODO: add Mastodon URL if account exists
    "flickr": "",
    "vimeo": "",
    "youtube": "https://www.youtube.com/channel/UCJxp1CvJlDsWBEJrguvhoLw/",
    "nav_menu_img": "content/ss_logo_e3cae3_pink3.jpg",
    "internal_header_img": "content/star_and_shadow_100_82.png",
    "wagtale_admin_img": "/static/content/star_and_shadow_100_82.png",
    "favicon": "/static/favicon/favicon_ss.ico",
    "font_h2": "https://fonts.googleapis.com/css?family=Lato",
    # This is used as the hostname for unsubscribe links in emails
    # i.e. emails will have links added to
    # [this]/members/100/unsubscribe)
    "email_unsubscribe_host": "https://starandshadow.org.uk",
    # Default address to which reports of a successful mailout
    # delivery are sent:
    "mailout_delivery_report_to": "info@starandshadow.org.uk",
    # "From" address for mailout
    "mailout_from_address": "info@starandshadow.org.uk",
    # email address shown when volunteer removes themselves from rota
    "vols_email": "volunteers@lists.starandshadow.org.uk",
    # email address(es) notified when volunteers are added or deactivated
    # (leave empty to disable these notifications)
    "vols_admin_address": [],
    "show_user_management": True,
}

WAGTAIL_SITE_NAME = "The Star and Shadow"

# Prompt volunteers to email when clearing a rota slot.
# SEED-ONLY — overridden by SiteConfiguration at runtime.
ROTA_CLEAR_EMAIL_PROMPT_ENABLED = False

# Disable 'allow editing from magic IP range' for now
CUBE_IP_ADDRESSES = ()

DEFAULT_MUGSHOT = "/static/content/ss_logo_e3cae3_pink3.jpg"

# Hide event images for shows before the S+S digital archive began.
# Volunteers (authenticated users) always see images regardless.
# SEED-ONLY — overridden by SiteConfiguration at runtime.
SHOW_ARCHIVE_IMAGES = False
# SEED-ONLY — overridden by SiteConfiguration at runtime.
IMAGES_START_DATE = "1 May 2018"

# S+S films start at the advertised time — no adverts or trailers.
# SEED-ONLY — overridden by SiteConfiguration at runtime.
FILMS_START_ON_TIME = True

# Tags are not yet well-used at S+S; hide them from the rota to reduce clutter.
# SEED-ONLY — overridden by SiteConfiguration at runtime.
ROTA_SHOW_TAGS = False

# Currently only used for setting an outer limit on what year printed
# programmes can be uploaded
DAWN_OF_TIME = 1998

# URL to an image copyright / image rights guidance document (e.g. on NextCloud).
# When set, a link ("image copyright guidance") appears below the image upload
# field on the event edit form (diary/templates/form_event.html), alongside a
# ⚠️ reminder to check image rights before uploading. Helps programmers find
# freely-licensed images and avoid copyright issues.
# Set to None to hide the link entirely.
IMAGE_COPYRIGHT_GUIDANCE_URL = "https://example.com/TODO-replace-with-nextcloud-url"  # TODO: replace with real URL

# URL for alt text writing guidance shown alongside the alt text field on image
# upload. Set to None to show the field without a link.
ALT_TEXT_GUIDANCE_URL = None  # TODO: add URL when volunteer documentation exists

###############################################################################
#
# Below here are Django settings
#

ADMINS = []

# Enable Django admin for S+S (urls_flat.py mounts it at /toolkit/admin/)
INSTALLED_APPS = INSTALLED_APPS + ("django.contrib.admin",)

TEMPLATES[0]["DIRS"] = (
    os.path.join(BASE_DIR, "star_and_shadow_templates"),
    os.path.join(BASE_DIR, "templates"),
)

# S+S-specific limits and configuration
# Increase rota role count limit from default 8 to 30 to accommodate larger volunteer rotas
# See docs/LIVESITE_FIXES.md § "Rota role count limitation" for context
MAX_COUNT_PER_ROLE = 30

