"""Shape outlines and physical sizing.

Shared by the raster masks and the SVG export so the two cannot drift apart. Discovers
no files and publishes no outputs.
"""

import math

from PIL import Image, ImageOps

from .settings import MACHINE_BEDS_IN

def heart_cut_points(width, height):
    """Return the shared heart outline used by raster masking and SVG export."""
    cx = width / 2.0
    cy = height * 0.46
    size = min(width, height)
    scale_x = (size * 0.9) / 32.0
    scale_y = (size * 0.9) / 29.5
    points = []
    for i in range(150):
        t = (2.0 * math.pi * i) / 150
        x = 16.0 * (math.sin(t) ** 3)
        y = -(13.0 * math.cos(t) - 5.0 * math.cos(2*t) - 2.0 * math.cos(3*t) - math.cos(4*t))
        points.append((cx + x * scale_x, cy + y * scale_y))
    return points

def circle_cut_bounds(width, height):
    diameter = min(width, height)
    left = (width - diameter) // 2
    top = (height - diameter) // 2
    return left, top, left + diameter - 1, top + diameter - 1

# --- Execution ---
def output_geometry(input_path, width_in, height_in, max_pixels, machine):
    with Image.open(input_path) as img:
        source_pixels = img.width * img.height
        if source_pixels > max_pixels:
            raise ValueError(f"Source image has {source_pixels:,} pixels; configured limit is {max_pixels:,}.")
        original_width, original_height = ImageOps.exif_transpose(img).size

    target_width = int(width_in * 300) if width_in is not None else None
    target_height = int(height_in * 300) if height_in is not None else None
    if target_width is not None and target_height is None:
        target_height = int(original_height * (target_width / original_width))
    elif target_height is not None and target_width is None:
        target_width = int(original_width * (target_height / original_height))
    elif target_width is None and target_height is None:
        target_width, target_height = original_width, original_height

    if target_width <= 0 or target_height <= 0:
        raise ValueError("Requested size is too small to produce at least one pixel at 300 DPI.")
    output_pixels = target_width * target_height
    if output_pixels > max_pixels:
        raise ValueError(f"Requested output has {output_pixels:,} pixels; configured limit is {max_pixels:,}.")

    if machine:
        bed_width, bed_height = MACHINE_BEDS_IN[machine]
        physical_width, physical_height = target_width / 300, target_height / 300
        fits = (
            (physical_width <= bed_width and physical_height <= bed_height)
            or (physical_width <= bed_height and physical_height <= bed_width)
        )
        if not fits:
            raise ValueError(
                f"Output is about {physical_width:.2f} x {physical_height:.2f} in and exceeds the "
                f"nominal {machine} area ({bed_width:g} x {bed_height:g} in), even when rotated. "
                "Choose a smaller size or review the design in the Glowforge app."
            )

    if width_in is None and height_in is None:
        dim_suffix = ""
    else:
        labels = []
        for pixels in (target_width, target_height):
            inches = pixels / 300
            label = f"{inches:.3f}".rstrip('0').rstrip('.')
            labels.append(label)
        dim_suffix = f"_w{labels[0]}h{labels[1]}"
    return dim_suffix
