import hashlib
import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.template import Library

from easy_thumbnails.files import get_thumbnailer

logger = logging.getLogger(__file__)

register = Library()


def _crop_thumbnail_url(source, crop_x, crop_y, crop_w, crop_h, target_w, target_h):
    """
    Generate a cropped thumbnail using PIL and return its media URL.

    Results are cached on disk under MEDIA_ROOT/diary/thumbs_cropped/ keyed by a
    hash of the source path, crop parameters, and target dimensions. Stale entries
    from previous crops are orphaned (they never block a fresh render).
    """
    try:
        from PIL import Image

        src_path = source.path
        key = f"{src_path}|{crop_x:.6f}|{crop_y:.6f}|{crop_w:.6f}|{crop_h:.6f}|{target_w}|{target_h}"
        cache_hash = hashlib.sha1(key.encode()).hexdigest()[:20]

        thumb_rel = f"diary/thumbs_cropped/c_{cache_hash}.jpg"
        thumb_abs = os.path.join(settings.MEDIA_ROOT, thumb_rel)

        os.makedirs(os.path.dirname(thumb_abs), exist_ok=True)

        if not os.path.exists(thumb_abs):
            with Image.open(src_path) as img:
                orig_w, orig_h = img.size
                x1 = max(0, round(crop_x * orig_w))
                y1 = max(0, round(crop_y * orig_h))
                x2 = min(orig_w, round((crop_x + crop_w) * orig_w))
                y2 = min(orig_h, round((crop_y + crop_h) * orig_h))
                cropped = img.crop((x1, y1, x2, y2))
                resized = cropped.resize((target_w, target_h), Image.LANCZOS)
                resized.convert("RGB").save(thumb_abs, "JPEG", quality=85, optimize=True)

        return settings.MEDIA_URL + thumb_rel
    except Exception:
        logger.exception(f"Failed generating cropped thumbnail for {source}")
        return ""


def thumbnail_url(source, alias):
    """
    Return the thumbnail URL for a source file using an aliased set of options.

    When the source field's model instance has a crop box set (crop_x/y/w/h) and
    the alias is 'indexview', generates a PIL-based cropped thumbnail at the
    dimensions configured in SiteConfiguration (thumbnail_crop_width/height).
    Falls back to easy_thumbnails for all other cases.

    Example usage::

        <img src="{{ person.photo|thumbnail_url:'small' }}" alt="">
    """
    try:
        instance = getattr(source, "instance", None)
        crop_x = getattr(instance, "crop_x", None)

        if crop_x is not None and alias == "indexview":
            crop_y = instance.crop_y
            crop_w = instance.crop_w
            crop_h = instance.crop_h
            if None not in (crop_y, crop_w, crop_h) and crop_w > 0 and crop_h > 0:
                dims = cache.get("thumbnail_crop_dims")
                if dims is None:
                    from toolkit.diary.models import get_site_config
                    cfg = get_site_config()
                    dims = (cfg.thumbnail_crop_width or 600, cfg.thumbnail_crop_height or 900)
                    cache.set("thumbnail_crop_dims", dims, timeout=60)
                target_w, target_h = dims
                url = _crop_thumbnail_url(source, crop_x, crop_y, crop_w, crop_h, target_w, target_h)
                if url:
                    return url

        thumb = get_thumbnailer(source)[alias]
    except Exception:
        logger.exception(f"Failed generating thumbnail for {source}, {alias}")
        return ""
    return thumb.url


register.filter(thumbnail_url)
