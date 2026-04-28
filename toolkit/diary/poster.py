"""Placeholder poster image generator for events.

human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 4.7"]; status: "#ai-input"
"""

import os
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

# Bundled font path (relative to this module)
_BUNDLED_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "util",
    "management",
    "commands",
    "seed_data",
    "fonts",
    "DejaVuSans-Bold.ttf",
)

# System fallback fonts (checked in order)
_FONT_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _find_bold_font():
    """Return path to a bold font, preferring bundled DejaVu."""
    candidates = [_BUNDLED_FONT] + _FONT_FALLBACKS
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def make_poster_image(event_name, bg_colour, width=800, height=450):
    """Generate a bold typographic poster: gradient background, text stretched to fill.

    Args:
        event_name: The text to render (usually the event name).
        bg_colour: Tuple of (r, g, b) for the background gradient base.
        width: Image width in pixels (default 800).
        height: Image height in pixels (default 450).

    Returns:
        PIL Image object (RGB mode).
    """
    r0, g0, b0 = bg_colour
    # Gradient: slightly lighter at top, darker at bottom
    top_c = (min(255, r0 + 40), min(255, g0 + 40), min(255, b0 + 50))
    bot_c = (max(0, r0 - 15), max(0, g0 - 15), max(0, b0 - 10))

    # Build gradient pixel by pixel
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

    # Choose text colour based on background luminance
    lum = 0.299 * r0 + 0.587 * g0 + 0.114 * b0
    text_colour = (255, 255, 255) if lum < 128 else (0, 0, 0)

    font_path = _find_bold_font()
    pad = 24

    # Wrap words into lines of roughly equal character length
    words = event_name.upper().split()
    total_chars = sum(len(w) for w in words)
    if total_chars <= 10:
        n_lines = 1
    elif total_chars <= 22:
        n_lines = 2
    elif total_chars <= 40:
        n_lines = 3
    else:
        n_lines = 4

    target_per_line = total_chars / n_lines
    raw_lines = []
    current = []
    current_len = 0
    for word in words:
        if current and current_len + len(word) > target_per_line and len(raw_lines) < n_lines - 1:
            raw_lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word)
    if current:
        raw_lines.append(" ".join(current))

    # Each line is rendered at high resolution then scaled to fill its slot exactly
    usable_w = width - pad * 2
    usable_h = height - pad * 2
    gap = max(4, height // 80)
    slot_h = (usable_h - gap * (len(raw_lines) - 1)) // len(raw_lines)

    def font_at(size):
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    resample = getattr(Image.Resampling, "LANCZOS", Image.BICUBIC)
    render_size = 300
    y = pad
    for line in raw_lines:
        f = font_at(render_size)
        probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bb = probe.textbbox((0, 0), line, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        if tw <= 0 or th <= 0:
            y += slot_h + gap
            continue

        text_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(text_img).text(
            (-bb[0], -bb[1]), line, fill=(*text_colour, 255), font=f
        )
        stretched = text_img.resize((usable_w, slot_h), resample=resample)
        img.paste(stretched, (pad, y), stretched)
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

    # Generate the image
    img = make_poster_image(event.name, bg_colour)

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
