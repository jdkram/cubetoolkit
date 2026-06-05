# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
import hashlib
import logging
import os

from django.conf import settings
from django.core.cache import cache
from django.template import Library

from easy_thumbnails.files import get_thumbnailer

logger = logging.getLogger(__file__)

register = Library()


def _crop_thumbnail_url(source, crop_x, crop_y, crop_w, crop_h, bar_colour, target_w, target_h):
    """
    Generate a PIL-based thumbnail with letterbox bars, then crop.

    If the source image's aspect ratio differs from the target, it is centred
    on a canvas before the crop box is applied. Bar colour controls the fill:
    - empty string → transparent bars (RGBA canvas, alpha=0)
    - "#rrggbb" string → solid-colour bars

    The result is always saved as PNG to support the transparent case.

    Results are disk-cached under MEDIA_ROOT/diary/thumbs_cropped/ keyed by a
    SHA-1 of all parameters. Stale entries from previous renders are orphaned.
    """
    try:
        from PIL import Image

        src_path = source.path
        key = (
            f"{src_path}|{crop_x:.6f}|{crop_y:.6f}|{crop_w:.6f}|{crop_h:.6f}"
            f"|{bar_colour}|{target_w}|{target_h}"
        )
        cache_hash = hashlib.sha1(key.encode()).hexdigest()[:20]

        thumb_rel = f"diary/thumbs_cropped/c_{cache_hash}.png"
        thumb_abs = os.path.join(settings.MEDIA_ROOT, thumb_rel)

        os.makedirs(os.path.dirname(thumb_abs), exist_ok=True)

        if not os.path.exists(thumb_abs):
            with Image.open(src_path) as img:
                img = img.convert("RGBA")

                orig_w, orig_h = img.size
                target_ratio = target_w / target_h
                actual_ratio = orig_w / orig_h

                if abs(actual_ratio - target_ratio) >= 0.02:
                    if actual_ratio > target_ratio:
                        canvas_w = orig_w
                        canvas_h = round(orig_w / target_ratio)
                    else:
                        canvas_h = orig_h
                        canvas_w = round(orig_h * target_ratio)

                    if bar_colour:
                        hex_colour = bar_colour.lstrip("#")
                        try:
                            r, g, b = (int(hex_colour[i: i + 2], 16) for i in (0, 2, 4))
                            fill = (r, g, b, 255)
                        except (ValueError, IndexError):
                            fill = (0, 0, 0, 0)
                    else:
                        fill = (0, 0, 0, 0)

                    canvas = Image.new("RGBA", (canvas_w, canvas_h), fill)
                    paste_x = (canvas_w - orig_w) // 2
                    paste_y = (canvas_h - orig_h) // 2
                    canvas.paste(img, (paste_x, paste_y))
                    img = canvas

                orig_w, orig_h = img.size
                x1 = max(0, round(crop_x * orig_w))
                y1 = max(0, round(crop_y * orig_h))
                x2 = min(orig_w, round((crop_x + crop_w) * orig_w))
                y2 = min(orig_h, round((crop_y + crop_h) * orig_h))
                cropped = img.crop((x1, y1, x2, y2))
                resized = cropped.resize((target_w, target_h), Image.LANCZOS)
                resized.save(thumb_abs, "PNG", optimize=True)

        return settings.MEDIA_URL + thumb_rel
    except Exception:
        logger.exception(f"Failed generating cropped thumbnail for {source}")
        return ""


def thumbnail_url(source, alias):
    """
    Return the thumbnail URL for a source file using an aliased set of options.

    When the source field's model instance has a crop box set (crop_x/y/w/h) and
    the alias is 'indexview', generates a PIL-based thumbnail at the dimensions
    configured in SiteConfiguration (thumbnail_crop_width/height). If bar_colour
    is also set, letterbox bars are applied before cropping (Option B: original
    file is never modified). Falls back to easy_thumbnails for all other cases.

    Example usage::

        <img src="{{ person.photo|thumbnail_url:'small' }}" alt="">
    """
    try:
        instance = getattr(source, "instance", None)
        crop_x = getattr(instance, "crop_x", None)

        if crop_x is not None and alias == "indexview":
            crop_y = getattr(instance, "crop_y", None)
            crop_w = getattr(instance, "crop_w", None)
            crop_h = getattr(instance, "crop_h", None)
            if None not in (crop_y, crop_w, crop_h) and crop_w > 0 and crop_h > 0:
                dims = cache.get("thumbnail_crop_dims")
                if dims is None:
                    from toolkit.diary.models import get_site_config
                    cfg = get_site_config()
                    dims = (cfg.thumbnail_crop_width or 600, cfg.thumbnail_crop_height or 900)
                    cache.set("thumbnail_crop_dims", dims, timeout=60)
                target_w, target_h = dims
                bar_colour = getattr(instance, "bar_colour", "") or ""
                url = _crop_thumbnail_url(
                    source, crop_x, crop_y, crop_w, crop_h, bar_colour, target_w, target_h
                )
                if url:
                    return url

        thumb = get_thumbnailer(source)[alias]
    except Exception:
        logger.exception(f"Failed generating thumbnail for {source}, {alias}")
        return ""
    return thumb.url


register.filter(thumbnail_url)
