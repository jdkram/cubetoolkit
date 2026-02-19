from django.conf import settings

from toolkit.diary.models import EventTag


def diary_settings(request):
    return {
        "MULTIROOM_ENABLED": settings.MULTIROOM_ENABLED,
        "IMAGE_COPYRIGHT_GUIDANCE_URL": getattr(
            settings, "IMAGE_COPYRIGHT_GUIDANCE_URL", None
        ),
    }


def promoted_tags(request):
    # This returns a QuerySet, so the database won't get accessed unless
    # 'promoted_tags' is referenced.
    return {"promoted_tags": EventTag.objects.filter(promoted=True)}
