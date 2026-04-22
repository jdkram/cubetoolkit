from django.conf import settings

from toolkit.diary.models import EventTag, get_site_config


def diary_settings(request):
    config = get_site_config()
    return {
        "MULTIROOM_ENABLED": settings.MULTIROOM_ENABLED,
        "MEMBERSHIP_EXPIRY_ENABLED": settings.MEMBERSHIP_EXPIRY_ENABLED,
        "IMAGE_COPYRIGHT_GUIDANCE_URL": config.image_copyright_guidance_url or None,
        "ALT_TEXT_GUIDANCE_URL": config.alt_text_guidance_url or None,
        "site_config": config,
    }


def promoted_tags(request):
    # This returns a QuerySet, so the database won't get accessed unless
    # 'promoted_tags' is referenced.
    return {"promoted_tags": EventTag.objects.filter(promoted=True)}
