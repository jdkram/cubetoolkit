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

# Disable 'allow editing from magic IP range' for now
CUBE_IP_ADDRESSES = ()

DEFAULT_MUGSHOT = "/static/content/ss_logo_e3cae3_pink3.jpg"

# Currently only used for setting an outer limit on what year printed
# programmes can be uploaded
DAWN_OF_TIME = 1998

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

