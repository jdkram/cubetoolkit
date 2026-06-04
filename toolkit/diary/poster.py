"""Placeholder poster image generator for events.

human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-input"
"""

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "util", "management", "commands", "seed_data", "fonts",
)

# Preferred display fonts in order — heavy/black weight gives the best poster look
_FONT_CANDIDATES = [
    os.path.join(_FONTS_DIR, "Anton-Regular.ttf"),        # bundled — preferred
    os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf"),      # bundled fallback
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _find_bold_font():
    """Return path to the best available display font."""
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _layout_lines(words):
    """One word per line; short connector words (≤3 chars) merge with the next word.

    This keeps articles and prepositions (A, AN, THE, OF, IN, FOR, ...) attached
    to the word they modify rather than floating alone on a line.
    """
    lines = []
    i = 0
    while i < len(words):
        w = words[i]
        if len(w) <= 3 and i + 1 < len(words):
            lines.append(w + " " + words[i + 1])
            i += 2
        else:
            lines.append(w)
            i += 1
    return lines or [""]


def make_poster_image(event_name, bg_colour, width=600, height=900):
    """Generate a bold typographic poster: gradient background, text stretched to fill.

    Layout: one word per line, each word scaled full-bleed to the image width.
    Short connector words (≤2 chars) are joined to the following word.

    Args:
        event_name: The text to render (usually the event name).
        bg_colour: Tuple of (r, g, b) for the background gradient base.
        width: Image width in pixels (default 600).
        height: Image height in pixels (default 900).

    Returns:
        PIL Image object (RGB mode).
    """
    r0, g0, b0 = bg_colour
    top_c = (min(255, r0 + 40), min(255, g0 + 40), min(255, b0 + 50))
    bot_c = (max(0, r0 - 15), max(0, g0 - 15), max(0, b0 - 10))

    pixels = []
    for y in range(height):
        t = y / max(height - 1, 1)
        pixels.extend([(
            int(top_c[0] + (bot_c[0] - top_c[0]) * t),
            int(top_c[1] + (bot_c[1] - top_c[1]) * t),
            int(top_c[2] + (bot_c[2] - top_c[2]) * t),
        )] * width)

    img = Image.new("RGB", (width, height))
    img.putdata(pixels)

    lum = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
    text_colour = (255, 255, 255) if lum < 128 else (0, 0, 0)

    font_path = _find_bold_font()
    raw_lines = _layout_lines(event_name.upper().split())

    PROBE = 300
    resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
    gap = max(2, height // 300)

    def font_at(size):
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    probe_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f = font_at(PROBE)

    # Measure natural height per line (uniformly scaled to fill width)
    def measure(line):
        bb = probe_draw.textbbox((0, 0), line, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        return max(1, tw), max(1, th)

    bboxes = [measure(l) for l in raw_lines]
    natural_hs = [max(1, int(th * width / tw)) for tw, th in bboxes]

    n = len(raw_lines)
    total_text_h = sum(natural_hs) + gap * (n - 1)

    # If block overflows, compress slot heights uniformly; otherwise centre vertically.
    if total_text_h > height:
        fit = height / total_text_h
        slot_hs = [max(1, int(h * fit)) for h in natural_hs]
        y0 = 0
    else:
        slot_hs = natural_hs
        y0 = (height - total_text_h) // 2

    # Render each line: scale to fill width uniformly (no 2D distortion).
    # If the slot is shorter than the natural width-filling height (overflow case),
    # scale to fit within the slot instead — lines may be slightly narrower than
    # full width but letters are never clipped.
    y = y0
    for line, (tw, th), slot_h in zip(raw_lines, bboxes, slot_hs):
        scale_x = width / tw
        scale_y = slot_h / th
        scale = min(scale_x, scale_y)   # uniform fit — no distortion, no clipping
        rw = max(1, int(tw * scale))
        rh = max(1, int(th * scale))
        x = (width - rw) // 2          # centre horizontally within image

        text_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(text_img).text((-probe_draw.textbbox((0,0), line, font=f)[0],
                                       -probe_draw.textbbox((0,0), line, font=f)[1]),
                                      line, fill=(*text_colour, 255), font=f)
        rendered = text_img.resize((rw, rh), resample=resample)
        img.paste(rendered, (x, y), rendered)
        y += slot_h + gap

    return img


def generate_event_placeholder(event, tag=None, colour_hex=None):
    """Generate a placeholder poster image for an event and save it as a MediaItem.

    Args:
        event: The Event instance to generate a poster for.
        tag: Optional EventTag to derive the background colour from.
             If not provided, uses the event's first tag or a default colour.
        colour_hex: Optional hex colour string (e.g. "#FF5733") to override the tag colour.

    Returns:
        The created MediaItem instance (already saved and attached to the event).
    """
    from toolkit.diary.models import MediaItem

    # Determine background colour: explicit hex takes priority, then tag, then default
    if colour_hex:
        # Parse hex colour like "#FF5733" -> (255, 87, 51)
        hex_clean = colour_hex.lstrip('#')
        bg_colour = tuple(int(hex_clean[i:i+2], 16) for i in (0, 2, 4))
    else:
        if tag is None:
            tag = event.tags.first()
        if tag and hasattr(tag, 'colour') and tag.colour:
            hex_colour = tag.colour.lstrip('#')
            bg_colour = tuple(int(hex_colour[i:i+2], 16) for i in (0, 2, 4))
        else:
            bg_colour = (180, 40, 40)  # Default deep red

    # Generate the image at the configured thumbnail dimensions
    from toolkit.diary.models import get_site_config
    cfg = get_site_config()
    img = make_poster_image(
        event.name,
        bg_colour,
        width=cfg.thumbnail_crop_width or 600,
        height=cfg.thumbnail_crop_height or 900,
    )

    # Save to BytesIO
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=90)
    buffer.seek(0)

    # Create MediaItem
    media_item = MediaItem(
        caption=f"Generated poster for {event.name}",
        alt_text=f"Typographic poster for {event.name}",
        credit="Auto-generated",
    )

    # Save the file
    filename = f"event_{event.id}_poster.jpg"
    media_item.media_file.save(filename, ContentFile(buffer.getvalue()), save=True)

    # Attach to event
    event.media.add(media_item)

    return media_item
