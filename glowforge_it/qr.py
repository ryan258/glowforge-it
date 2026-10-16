"""Deterministic QR version-1/L renderer for protected sidecar marks."""

import numpy as np
import segno
from PIL import Image, ImageDraw

from .personalization import POSITIONS, shape_hint

QR_SIZE = 21


def _make_matrix(payload):
    """Version 1, error level L, byte mode, UTF-8: at most 17 bytes of payload."""
    if len(payload.encode("utf-8")) > 17:
        raise ValueError("QR payload must be at most 17 UTF-8 bytes for version 1/L.")
    code = segno.make(payload, version=1, error="l", mode="byte", encoding="utf-8", boost_error=False)
    return code.matrix


def render_qr_stamp(image, payload, *, position="bottom-right", module_px=4, margin_px=12):
    """Render a version-1/L QR mask and reject overlap with existing burns."""
    if not isinstance(payload, str) or not payload:
        raise ValueError("QR payload must be non-empty text.")
    if position not in POSITIONS:
        raise ValueError(f"QR position must be one of {POSITIONS}.")
    if type(module_px) is not int or module_px < 2:
        raise ValueError("QR module size must be an integer of at least 2 pixels.")
    if type(margin_px) is not int or margin_px < 0:
        raise ValueError("QR margin must be a nonnegative integer.")

    matrix = _make_matrix(payload)
    side = (QR_SIZE + 8) * module_px
    width, height = image.size
    if side + 2 * margin_px > width or side + 2 * margin_px > height:
        raise ValueError("QR mark and margin do not fit inside the output canvas.")
    x = margin_px if position.endswith("left") else width - margin_px - side
    y = margin_px if position.startswith("top") else height - margin_px - side
    qr = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(qr)
    for row, values in enumerate(matrix):
        for column, value in enumerate(values):
            if value:
                left = x + (column + 4) * module_px
                top = y + (row + 4) * module_px
                draw.rectangle((left, top, left + module_px - 1, top + module_px - 1), fill=0)

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    # Reserve all modules and the four-module quiet zone: white cannot erase
    # artwork in a separately engraved mask, and the code must fit on the blank.
    region = rgba[y:y + side, x:x + side]
    if np.any(region[:, :, 3] < 255):
        qr.close()
        raise ValueError("QR mark and quiet zone extend outside the usable shape; choose another position or margin."
                         + shape_hint(rgba[:, :, 3], position, margin_px, side, side))
    overlap = region[:, :, 0] < 128
    if np.any(overlap):
        qr.close()
        raise ValueError(
            f"QR mark would overlap {int(overlap.sum())} existing burn pixels at {position}; "
            "choose another position, margin, or source layout."
        )
    return qr, {
        "payload": payload,
        "version": 1,
        "error_correction": "L",
        "position": position,
        "module_px": module_px,
        "margin_px": margin_px,
        "bounds_px": [x, y, x + side, y + side],
        "overlap_checked": True,
        "shape_checked": True,
    }
