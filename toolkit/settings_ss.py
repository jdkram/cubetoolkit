from toolkit.settings_common import *

ROOT_URLCONF = "toolkit.urls_flat"

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

# Prompt volunteers to email when clearing a rota slot
ROTA_CLEAR_EMAIL_PROMPT_ENABLED = False

# Disable 'allow editing from magic IP range' for now
CUBE_IP_ADDRESSES = ()

DEFAULT_MUGSHOT = "/static/content/ss_logo_e3cae3_pink3.jpg"

# Currently only used for setting an outer limit on what year printed
# programmes can be uploaded
DAWN_OF_TIME = 1998

# URL to an image copyright guidance document (e.g. on NextCloud).
# When set, a link appears next to the image upload field in the event editor.
# Leave as None if no guidance document exists yet.
IMAGE_COPYRIGHT_GUIDANCE_URL = None

###############################################################################
#
# Below here are Django settings
#

ADMINS = ("Marcus Valentine", "REDACTED")

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

