"""Deterministic binary artwork renderers.

These functions accept a prepared grayscale image where 0 means maximum burn
and 255 means no burn. Every renderer returns a 1-bit image. They do not choose
laser settings or claim that a particular dot, line, or gap will survive a
physical material run.
"""

from array import array
import math

import numpy as np
from PIL import Image, ImageDraw


ORDERED_MATRIX_SIZES = (2, 4, 8)


def _binary_image(values):
    return Image.fromarray(np.asarray(values, dtype=np.uint8), mode="L").convert("1")


def render_atkinson(image, dither_threshold=128, preserve_endpoints=False):
    """Apply the existing Atkinson error-diffusion renderer."""
    gray = image.convert("L")
    h, w = gray.height, gray.width
    stride = w + 3
    arr = np.array(gray, dtype=np.float64)
    padded_arr = np.pad(arr, ((0, 2), (1, 2)), mode="constant", constant_values=0.0)
    padded = array("d", padded_arr.ravel())
    output_pixels = bytearray(w * h)
    for y in range(h):
        row = y * stride
        row_y1 = row + stride
        row_y2 = row + 2 * stride
        for x in range(1, w + 1):
            index = row + x
            old_pixel = padded[index]
            original = arr[y, x - 1]
            if preserve_endpoints and original in (0, 255):
                new_pixel = float(original)
            else:
                new_pixel = 255.0 if old_pixel > dither_threshold else 0.0
            padded[index] = new_pixel
            output_pixels[y * w + x - 1] = int(new_pixel)

            error_eighth = (old_pixel - new_pixel) * 0.125
            padded[index + 1] += error_eighth
            padded[index + 2] += error_eighth
            padded[row_y1 + x - 1] += error_eighth
            padded[row_y1 + x] += error_eighth
            padded[row_y1 + x + 1] += error_eighth
            padded[row_y2 + x] += error_eighth
    return Image.frombytes("L", (w, h), bytes(output_pixels)).convert("1")


def render_silhouette(image, threshold=128):
    """Threshold prepared grayscale into solid burn/no-burn regions."""
    values = np.asarray(image.convert("L"), dtype=np.uint8)
    return _binary_image(np.where(values > threshold, 255, 0))


def _bayer_matrix(size):
    if size == 2:
        return np.array([[0, 2], [3, 1]], dtype=np.float32)
    if size == 4:
        return np.array(
            [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
            dtype=np.float32,
        )
    if size == 8:
        base = _bayer_matrix(4)
        return np.block([[4 * base, 4 * base + 2], [4 * base + 3, 4 * base + 1]])
    raise ValueError(f"Ordered matrix size must be one of {ORDERED_MATRIX_SIZES}.")


def render_ordered(image, matrix_size=4):
    """Apply a tiled Bayer ordered screen with tone represented by pattern density."""
    matrix = _bayer_matrix(matrix_size)
    thresholds = ((matrix + 0.5) / (matrix_size * matrix_size)) * 255.0
    values = np.asarray(image.convert("L"), dtype=np.float32)
    tiled = np.tile(thresholds, (math.ceil(values.shape[0] / matrix_size), math.ceil(values.shape[1] / matrix_size)))
    tiled = tiled[: values.shape[0], : values.shape[1]]
    return _binary_image(np.where(values <= tiled, 0, 255))


def render_halftone(image, cell_px=8, angle=0.0):
    """Render tone as deterministic variable-radius circular screen cells."""
    if type(cell_px) is not int or cell_px < 2:
        raise ValueError("Halftone cell size must be an integer of at least 2 pixels.")
    if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 <= angle < 180:
        raise ValueError("Halftone angle must be finite and in the range 0 <= angle < 180.")

    prepared = image.convert("L")
    if angle:
        rotated = prepared.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
        prepared.close()
        prepared = rotated
    values = np.asarray(prepared, dtype=np.float32)
    height, width = values.shape
    output = Image.new("1", (width, height), 1)
    draw = ImageDraw.Draw(output)
    for top in range(0, height, cell_px):
        bottom = min(height, top + cell_px)
        for left in range(0, width, cell_px):
            right = min(width, left + cell_px)
            tone = float(values[top:bottom, left:right].mean())
            radius = min(right - left, bottom - top) * 0.48 * math.sqrt(max(0.0, 1.0 - tone / 255.0))
            if radius <= 0.25:
                continue
            center_x = (left + right - 1) / 2.0
            center_y = (top + bottom - 1) / 2.0
            draw.ellipse(
                (center_x - radius, center_y - radius, center_x + radius, center_y + radius),
                fill=0,
            )
    prepared.close()
    if angle:
        # Map the original canvas into the expanded screen around their exact
        # centers. This avoids clipping source corners or rounding an odd crop.
        radians = math.radians(angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        cx, cy = image.width / 2, image.height / 2
        restored = output.transform(
            image.size, Image.Transform.AFFINE,
            (cosine, -sine, width / 2 - cosine * cx + sine * cy,
             sine, cosine, height / 2 - sine * cx - cosine * cy),
            resample=Image.Resampling.NEAREST, fillcolor=1,
        )
        output.close()
        output = restored
    return output


def _hatch_family(values, spacing_px, angle):
    """Return one directional hatch family as a boolean burn mask."""
    height, width = values.shape
    y, x = np.indices((height, width), dtype=np.float32)
    radians = math.radians(angle)
    coordinate = x * math.cos(radians) + y * math.sin(radians)
    distance = np.abs(np.mod(coordinate + spacing_px / 2.0, spacing_px) - spacing_px / 2.0)
    line_width = spacing_px * 0.92 * (1.0 - values / 255.0)
    return (line_width > 0) & (distance <= line_width / 2.0)


def render_hatch(image, spacing_px=6, angle=45.0, cross=False):
    """Render tone as directional hatch or crosshatch lines."""
    if type(spacing_px) is not int or spacing_px < 2:
        raise ValueError("Hatch spacing must be an integer of at least 2 pixels.")
    if not isinstance(angle, (int, float)) or not math.isfinite(angle) or not 0 <= angle < 180:
        raise ValueError("Hatch angle must be finite and in the range 0 <= angle < 180.")
    if type(cross) is not bool:
        raise ValueError("Hatch cross must be a boolean.")
    values = np.asarray(image.convert("L"), dtype=np.float32)
    mask = _hatch_family(values, spacing_px, angle)
    if cross:
        mask |= _hatch_family(values, spacing_px, (angle + 90.0) % 180.0)
    return _binary_image(np.where(mask, 0, 255))


def render_edge(image, threshold=32):
    """Render strong luminance transitions as a one-pixel Sobel edge map."""
    if type(threshold) is not int or not 1 <= threshold <= 255:
        raise ValueError("Edge threshold must be an integer between 1 and 255.")
    values = np.asarray(image.convert("L"), dtype=np.float32)
    padded = np.pad(values, 1, mode="edge")
    horizontal = (
        -padded[:-2, :-2] + padded[:-2, 2:]
        - 2.0 * padded[1:-1, :-2] + 2.0 * padded[1:-1, 2:]
        - padded[2:, :-2] + padded[2:, 2:]
    )
    vertical = (
        -padded[:-2, :-2] - 2.0 * padded[:-2, 1:-1] - padded[:-2, 2:]
        + padded[2:, :-2] + 2.0 * padded[2:, 1:-1] + padded[2:, 2:]
    )
    magnitude = np.minimum(255.0, np.hypot(horizontal, vertical) / 4.0)
    return _binary_image(np.where(magnitude >= threshold, 0, 255))


def render_contour(image, levels=8):
    """Render tone-band boundaries as an isoline-style binary map."""
    if type(levels) is not int or not 2 <= levels <= 64:
        raise ValueError("Contour levels must be an integer between 2 and 64.")
    values = np.asarray(image.convert("L"), dtype=np.uint16)
    bands = (values * levels // 256).astype(np.uint16)
    boundaries = np.zeros_like(bands, dtype=bool)
    boundaries[:, 1:] |= bands[:, 1:] != bands[:, :-1]
    boundaries[1:, :] |= bands[1:, :] != bands[:-1, :]
    return _binary_image(np.where(boundaries, 0, 255))


_RENDERERS = {
    "atkinson": lambda image, s, keep: render_atkinson(image, s.dither_thresh, keep),
    "silhouette": lambda image, s, keep: render_silhouette(image, s.silhouette_threshold),
    "ordered": lambda image, s, keep: render_ordered(image, s.ordered_matrix_size),
    "halftone": lambda image, s, keep: render_halftone(image, s.halftone_cell_px, s.halftone_angle),
    "hatch": lambda image, s, keep: render_hatch(image, s.hatch_spacing_px, s.hatch_angle, s.hatch_cross),
    "edge": lambda image, s, keep: render_edge(image, s.edge_threshold),
    "contour": lambda image, s, keep: render_contour(image, s.contour_levels),
}
RENDER_MODES = tuple(_RENDERERS)


def render_mask(image, settings, preserve_endpoints=False):
    """Dispatch settings.render_mode to its binary burn-mask renderer."""
    renderer = _RENDERERS.get(settings.render_mode)
    if renderer is None:
        raise ValueError(f"Unsupported render mode: {settings.render_mode}")
    return renderer(image, settings, preserve_endpoints)
