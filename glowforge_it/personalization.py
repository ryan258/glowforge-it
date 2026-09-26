"""Collision-checked personalization masks for registered maker jobs."""


import numpy as np
from PIL import Image, ImageDraw, ImageFont


POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")


def render_text_stamp(image, text, *, position="bottom-left", size_px=24, margin_px=12):
    """Render a separate one-bit text mask and reject overlap with existing burns."""
    if not isinstance(text, str) or not text.strip() or "\n" in text or "\r" in text:
        raise ValueError("Stamp text must be non-empty single-line text.")
    if len(text) > 240:
        raise ValueError("Stamp text must be at most 240 characters.")
    if position not in POSITIONS:
        raise ValueError(f"Stamp position must be one of {POSITIONS}.")
    if type(size_px) is not int or size_px < 6:
        raise ValueError("Stamp size must be an integer of at least 6 pixels.")
    if type(margin_px) is not int or margin_px < 0:
        raise ValueError("Stamp margin must be a nonnegative integer.")

    width, height = image.size
    font = ImageFont.load_default(size=size_px)
    probe = ImageDraw.Draw(Image.new("1", (1, 1), 1))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font, anchor="lt")
    text_width, text_height = right - left, bottom - top
    if text_width + 2 * margin_px > width or text_height + 2 * margin_px > height:
        raise ValueError("Stamp text and margin do not fit inside the output canvas.")

    x = margin_px if position.endswith("left") else width - margin_px - text_width
    y = margin_px if position.startswith("top") else height - margin_px - text_height
    stamp = Image.new("1", (width, height), 1)
    ImageDraw.Draw(stamp).text((x, y), text, fill=0, font=font, anchor="lt")

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    existing_burn = (rgba[:, :, 3] > 0) & (rgba[:, :, 0] < 128)
    stamp_burn = np.asarray(stamp, dtype=bool) == 0
    if np.any(stamp_burn & (rgba[:, :, 3] < 255)):
        stamp.close()
        raise ValueError("Stamp extends outside the usable shape; choose another position or margin.")
    overlap = existing_burn & stamp_burn
    if np.any(overlap):
        stamp.close()
        raise ValueError(
            f"Stamp would overlap {int(overlap.sum())} existing burn pixels at {position}; "
            "choose another position, margin, or source layout."
        )

    return stamp, {
        "text": text,
        "position": position,
        "size_px": size_px,
        "margin_px": margin_px,
        "bounds_px": [x, y, x + text_width, y + text_height],
        "overlap_checked": True,
        "shape_checked": True,
    }
