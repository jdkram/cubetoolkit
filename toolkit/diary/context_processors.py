from django.conf import settings

from toolkit.diary.models import EventTag, SiteConfiguration, get_site_config
from toolkit.inductions.models import get_inductions_settings

_FEATURE_NAMES = [
    "diary_read",
    "diary_calendar",
    "programming_queue_read",
    "programming_queue_write",
    "event_templates",
    "event_tags",
    "roles",
    "rooms",
    "diary_reports",
    "printed_programmes",
    "rota_vacancies",
    "donations_manage",
]


def diary_settings(request):
    config = get_site_config()
    user = request.user
    feature_perms = {
        name: SiteConfiguration._passes_level(
            user, getattr(config, f"perm_{name}", SiteConfiguration.PERM_PROGRAMMER)
        )
        for name in _FEATURE_NAMES
    }
    return {
        "MULTIROOM_ENABLED": settings.MULTIROOM_ENABLED,
        "MEMBERSHIP_EXPIRY_ENABLED": settings.MEMBERSHIP_EXPIRY_ENABLED,
        "IMAGE_COPYRIGHT_GUIDANCE_URL": config.image_copyright_guidance_url or None,
        "ALT_TEXT_GUIDANCE_URL": config.alt_text_guidance_url or None,
        "site_config": config,
        "inductions_settings": get_inductions_settings(),
        "feature_perms": feature_perms,
    }


def promoted_tags(request):
    # This returns a QuerySet, so the database won't get accessed unless
    # 'promoted_tags' is referenced.
    return {"promoted_tags": EventTag.objects.filter(promoted=True)}
