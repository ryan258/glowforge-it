"""Shape outlines and physical sizing.

Shared by the raster masks and the SVG export so the two cannot drift apart. Discovers
no files and publishes no outputs.
"""

import io
import math
import struct

from PIL import Image

from .settings import DEFAULT_MAX_PIXELS, MACHINE_BEDS_IN


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


def circle_cut_svg(width, height):
    """(cx, cy, r) of the cut circle in continuous SVG coordinates.

    circle_cut_bounds gives inclusive pixel indices and the raster mask covers those whole
    pixel cells, so the vector circle spans [left, right + 1] to register with the mask.
    """
    left, top, right, bottom = circle_cut_bounds(width, height)
    return (left + right + 1) / 2.0, (top + bottom + 1) / 2.0, (right - left + 1) / 2.0


def _png_exif_without_decode(img):
    """Inspect PNG metadata, including chunks after IDAT, without reading pixels.

    Pillow's PNG getexif() loads pixels when EXIF is not already available. Build
    a metadata-only PNG instead, seeking over compressed image data. Preserve the
    caller's stream position and bound the metadata copied into memory.
    """
    if img.fp is None:
        return Image.Image.getexif(img)
    stream = img.fp
    position = stream.tell()
    chunks = bytearray(b'\x89PNG\r\n\x1a\n')
    try:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(8)
        while stream.tell() < size:
            header = stream.read(8)
            if len(header) != 8:
                raise ValueError('Truncated PNG chunk header.')
            length, kind = struct.unpack('>I4s', header)
            if stream.tell() + length + 4 > size:
                raise ValueError('Truncated PNG chunk data.')
            if kind in (b'IHDR', b'eXIf', b'tEXt', b'zTXt', b'iTXt'):
                if len(chunks) + length + 12 > 1024 * 1024:
                    raise ValueError('PNG metadata exceeds the 1 MiB preflight limit.')
                chunks.extend(header)
                chunks.extend(stream.read(length + 4))
            else:
                stream.seek(length + 4, 1)
            if kind == b'IEND':
                break
        # Image.open stops at the IDAT header; no pixel data is needed here.
        chunks.extend(b'\x00\x00\x00\x00IDAT')
        with Image.open(io.BytesIO(chunks)) as metadata:
            return Image.Image.getexif(metadata)
    finally:
        stream.seek(position)


def get_oriented_dimensions(img):
    """Return (width, height) of an image accounting for EXIF orientation without decoding pixels."""
    raw_w, raw_h = img.size
    exif = _png_exif_without_decode(img) if img.format == 'PNG' else img.getexif()
    orientation = exif.get(274, 1)  # 274 is EXIF Orientation tag
    # EXIF orientations 5, 6, 7, 8 swap width and height
    if orientation in (5, 6, 7, 8):
        return raw_h, raw_w
    return raw_w, raw_h


def resolve_target_dimensions(original_width, original_height, width_in=None, height_in=None):
    """Compute target pixel dimensions from physical dimensions and original size."""
    target_width = int(round(width_in * 300)) if width_in is not None else None
    target_height = int(round(height_in * 300)) if height_in is not None else None
    if target_width is not None and target_height is None:
        target_height = max(1, int(round(original_height * (target_width / original_width))))
    elif target_height is not None and target_width is None:
        target_width = max(1, int(round(original_width * (target_height / original_height))))
    elif target_width is None and target_height is None:
        target_width, target_height = original_width, original_height
    return target_width, target_height


def resolve_oriented_geometry(input_path, width_in=None, height_in=None, max_pixels=DEFAULT_MAX_PIXELS, machine=None):
    """Compute original and target dimensions from image header without pixel decoding.

    Returns:
        (original_width, original_height, target_width, target_height, dim_suffix)
    """
    with Image.open(input_path) as img:
        source_pixels = img.width * img.height
        if source_pixels > max_pixels:
            raise ValueError(f"Source image has {source_pixels:,} pixels; configured limit is {max_pixels:,}.")
        original_width, original_height = get_oriented_dimensions(img)

    target_width, target_height = resolve_target_dimensions(
        original_width, original_height, width_in=width_in, height_in=height_in
    )

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

    return original_width, original_height, target_width, target_height, dim_suffix
