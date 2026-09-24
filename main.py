# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.4.2",
#     "pillow==12.1.1",
# ]
# ///

import argparse
import base64
import io
import math
import os
import sys
import tempfile
import time
from array import array
from dataclasses import asdict, dataclass
from fractions import Fraction

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


DEFAULT_MAX_PIXELS = 20_000_000
DEFAULT_MATERIAL = 'medium maple plywood'
DEFAULT_MATERIAL_THICKNESS_IN = 0.125
MACHINE_BEDS_IN = {
    # Nominal printable areas; leave additional margin in the Glowforge app.
    'performance': (19.5, 11.0),
    'aura': (12.0, 12.0),
    'spark': (8.5, 11.0),
}

# --- Presets and Defaults ---
PRESETS = {
    'photo-high-detail': {
        'denoise_radius': 3,
        'contrast': 1.8,
        'sharpen_radius': 1.5,
        'sharpen_percent': 200
    },
    'photo-soft': {
        'contrast': 1.2,
        'sharpen_radius': 1.0,
        'sharpen_percent': 100
    },
    'vector-graphic': {
        'clean_solids': True,
        'clean_solids_black': 50,
        'clean_solids_white': 200,
        'contrast': 2.0
    },
    'ai-art': {
        'denoise_radius': 3,
        'clean_solids': True,
        'contrast': 1.6,
        'sharpen_radius': 2.0,
        'sharpen_percent': 150
    },
    'ai-art-detailed': {
        'denoise_radius': 5,
        'clean_solids': True,
        'contrast': 1.8,
        'sharpen_radius': 2.5,
        'sharpen_percent': 200
    },
    'line-art': {
        'clean_solids': True,
        'contrast': 2.5,
        'black_thresh': 20
    },
    'sketch': {
        'contrast': 1.3,
        'sharpen_radius': 1.0,
        'sharpen_percent': 250,
        'sharpen_threshold': 1
    },
    'wood-hard': {
        'contrast': 1.7,
        'black_thresh': 10,
        'sharpen_radius': 2.0
    },
    'wood-soft': {
        'contrast': 1.4,
        'white_thresh': 245,
        'denoise_radius': 3
    },
    'acrylic': {
        'clean_solids': True,
        'contrast': 2.0,
        'sharpen_radius': 1.5,
        'sharpen_percent': 180
    },
    'leather': {
        'contrast': 1.3,
        'denoise_radius': 3,
        'sharpen_radius': 1.0,
        'sharpen_percent': 120
    },
    'glass': {
        'contrast': 1.9,
        'sharpen_radius': 2.0,
        'sharpen_percent': 170
    },
    'stamp': {
        'clean_solids': True,
        'clean_solids_black': 60,
        'clean_solids_white': 190,
        'contrast': 3.0
    },
    'high-contrast': {
        'clean_solids': True,
        'black_thresh': 15,
        'white_thresh': 240,
        'contrast': 2.5
    },
    'low-res-enhance': {
        'denoise_radius': 3,
        'contrast': 1.6,
        'sharpen_radius': 1.5,
        'sharpen_percent': 220
    },
    'coaster': {
        'circle_cut': True
    },
    'coaster-heart': {
        'heart_cut': True
    }
}

DEFAULTS = {
    'black_threshold': 0,
    'white_threshold': 255,
    'dither_threshold': 128,
    'clean_solids': False,
    'clean_solids_black': 35,
    'clean_solids_white': 220,
    'invert': False,
    'no_border': False,
    'denoise': 0,
    'contrast': 1.5,
    'sharpen_radius': 2.0,
    'sharpen_percent': 150,
    'sharpen_threshold': 3,
    'circle_cut': False,
    'heart_cut': False,
    'fit_mode': 'stretch'
}


@dataclass(frozen=True)
class ProcessingSettings:
    """Resolved image-processing options for one batch run."""

    black_threshold: int = DEFAULTS['black_threshold']
    white_threshold: int = DEFAULTS['white_threshold']
    dither_threshold: int = DEFAULTS['dither_threshold']
    clean_solids: bool = DEFAULTS['clean_solids']
    clean_solids_black: int = DEFAULTS['clean_solids_black']
    clean_solids_white: int = DEFAULTS['clean_solids_white']
    invert: bool = DEFAULTS['invert']
    no_border: bool = DEFAULTS['no_border']
    denoise: int = DEFAULTS['denoise']
    contrast: float = DEFAULTS['contrast']
    sharpen_radius: float = DEFAULTS['sharpen_radius']
    sharpen_percent: int = DEFAULTS['sharpen_percent']
    sharpen_threshold: int = DEFAULTS['sharpen_threshold']
    circle_cut: bool = DEFAULTS['circle_cut']
    heart_cut: bool = DEFAULTS['heart_cut']
    fit_mode: str = DEFAULTS['fit_mode']

    def transform_kwargs(self):
        """Translate stable CLI names to the image function's legacy API."""
        values = asdict(self)
        values['black_thresh'] = values.pop('black_threshold')
        values['white_thresh'] = values.pop('white_threshold')
        values['dither_thresh'] = values.pop('dither_threshold')
        values['denoise_radius'] = values.pop('denoise')
        return values

def threshold_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue < 0 or ivalue > 255:
        raise argparse.ArgumentTypeError(f"Threshold '{value}' must be between 0 and 255.")
    return ivalue

def positive_float_type(value):
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number.")
    if not math.isfinite(fvalue) or fvalue <= 0:
        raise argparse.ArgumentTypeError(f"Dimension '{value}' must be greater than 0.")
    return fvalue


def positive_inches_type(value):
    """Parse a positive inch value as a decimal or fraction such as 1/8."""
    try:
        fvalue = float(Fraction(value.strip()))
    except (ValueError, ZeroDivisionError, AttributeError):
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid inch measurement.")
    if not math.isfinite(fvalue) or fvalue <= 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than 0 inches.")
    return fvalue


def odd_int_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue < 3 or ivalue % 2 == 0:
        raise argparse.ArgumentTypeError(f"Denoise size '{value}' must be an odd integer >= 3.")
    return ivalue

def positive_int_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than 0.")
    return ivalue

def non_negative_int_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than or equal to 0.")
    return ivalue


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


def _resize_to_canvas(image, target_size, fit_mode):
    target_w, target_h = target_size
    if fit_mode == 'stretch':
        return image.resize(target_size, Image.Resampling.LANCZOS)

    scale_x = target_w / image.width
    scale_y = target_h / image.height
    scale = min(scale_x, scale_y) if fit_mode == 'contain' else max(scale_x, scale_y)
    resized_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)

    if fit_mode == 'contain':
        canvas = Image.new('L', target_size, 255)
        offset = ((target_w - resized.width) // 2, (target_h - resized.height) // 2)
        canvas.paste(resized, offset)
        return canvas

    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))

def transform_image(
    img, 
    black_thresh=0, 
    white_thresh=255, 
    dither_thresh=128, 
    clean_solids=False, 
    clean_solids_black=35,
    clean_solids_white=220,
    invert=False, 
    width_in=None, 
    height_in=None, 
    no_border=False,
    denoise_radius=0,
    contrast=1.5,
    sharpen_radius=2.0,
    sharpen_percent=150,
    sharpen_threshold=3,
    circle_cut=False,
    heart_cut=False,
    fit_mode='stretch'
):
    # 1. Apply EXIF orientation
    img = ImageOps.exif_transpose(img)
    
    # 2. Composite alpha/transparency onto white background
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)
        
    # 3. Convert to Grayscale
    img = img.convert('L')
    
    # 3.5 Apply Denoising (Median Filter) if requested (great for AI artifacts)
    if denoise_radius > 0:
        img = img.filter(ImageFilter.MedianFilter(size=denoise_radius))
        
    # 4. Handle Resize if requested (calculated at 300 DPI)
    if width_in is not None or height_in is not None:
        orig_w, orig_h = img.size
        target_w = int(width_in * 300) if width_in is not None else None
        target_h = int(height_in * 300) if height_in is not None else None
        
        if target_w and not target_h:
            target_h = int(orig_h * (target_w / float(orig_w)))
        elif target_h and not target_w:
            target_w = int(orig_w * (target_h / float(orig_h)))
            
        if target_w <= 0 or target_h <= 0:
            raise ValueError("Requested physical size is too small to produce at least one pixel at 300 DPI.")
        if fit_mode not in ('stretch', 'contain', 'cover'):
            raise ValueError(f"Unsupported fit mode: {fit_mode}")
        img = _resize_to_canvas(img, (target_w, target_h), fit_mode)
        
    if invert:
        img = ImageOps.invert(img)
        
    # 5. Pre-process Thresholds
    img_array = np.array(img, dtype=np.uint8)
    if clean_solids:
        img_array[img_array < clean_solids_black] = 0
        img_array[img_array > clean_solids_white] = 255
        
    if black_thresh > 0:
        img_array[img_array <= black_thresh] = 0
    if white_thresh < 255:
        img_array[img_array >= white_thresh] = 255
        
    img = Image.fromarray(img_array)
    
    # 6. High Contrast / Levels
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    
    # 7. Unsharp Mask
    img = img.filter(ImageFilter.UnsharpMask(radius=sharpen_radius, percent=sharpen_percent, threshold=sharpen_threshold))
    
    # 8. Atkinson Dithering Implementation
    h, w = img.height, img.width
    stride = w + 3

    # Fast buffer creation using contiguous C memory via NumPy padding.
    # Pad layout: 1 col left, 2 cols right (stride = w + 3), 2 rows bottom (height = h + 2).
    arr = np.array(img, dtype=np.float64)
    padded_arr = np.pad(arr, ((0, 2), (1, 2)), mode='constant', constant_values=0.0)
    padded = array('d', padded_arr.ravel())
    output_pixels = bytearray(w * h)
    for y in range(h):
        row = y * stride
        row_y1 = row + stride
        row_y2 = row + 2 * stride
        for x in range(1, w + 1):
            index = row + x
            old_pixel = padded[index]
            new_pixel = 255.0 if old_pixel > dither_thresh else 0.0
            padded[index] = new_pixel
            output_pixels[y * w + x - 1] = int(new_pixel)
            
            error = old_pixel - new_pixel
            error_eighth = error * 0.125
            
            padded[index + 1] += error_eighth
            padded[index + 2] += error_eighth
            padded[row_y1 + x - 1] += error_eighth
            padded[row_y1 + x] += error_eighth
            padded[row_y1 + x + 1] += error_eighth
            padded[row_y2 + x] += error_eighth
            
    final_img = Image.frombytes('L', (w, h), bytes(output_pixels)).convert('1')
    
    # 9. Add 1px Black Border / Coaster Cutout (unless disabled)
    w, h = final_img.size
    if circle_cut:
        rgba_img = final_img.convert('RGBA')
        
        # Create alpha mask (0 = transparent outside circle)
        mask = Image.new('L', (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        left, top, right, bottom = circle_cut_bounds(w, h)
        
        # Draw opaque circle
        draw_mask.ellipse([left, top, right, bottom], fill=255)
        rgba_img.putalpha(mask)
        
        # This optional bitmap outline is for registration; it engraves.
        if not no_border:
            draw_rgba = ImageDraw.Draw(rgba_img)
            draw_rgba.ellipse([left, top, right, bottom], outline=(0, 0, 0, 255), width=1)
            
        final_img = rgba_img
    elif heart_cut:
        rgba_img = final_img.convert('RGBA')
        
        # Create alpha mask (0 = transparent outside heart)
        mask = Image.new('L', (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        points = heart_cut_points(w, h)
            
        # Draw opaque heart on mask
        draw_mask.polygon(points, fill=255)
        rgba_img.putalpha(mask)
        
        # This optional bitmap outline is for registration; it engraves.
        if not no_border:
            draw_rgba = ImageDraw.Draw(rgba_img)
            draw_rgba.polygon(points, outline=(0, 0, 0, 255), width=1)
            
        final_img = rgba_img
    elif not no_border:
        draw = ImageDraw.Draw(final_img)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
        
    return final_img


def _atomic_write(path, write_callback):
    """Write a file beside its destination, then replace the destination."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(prefix='.gf-', suffix=os.path.splitext(path)[1], dir=directory)
    os.close(fd)
    try:
        write_callback(temporary_path)
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def render_svg_document(final_img, circle_cut=False, heart_cut=False):
    """Generate aligned SVG document string with embedded raster and vector cut stroke."""
    if not (circle_cut or heart_cut):
        raise ValueError("SVG cut output requires --circle-cut or --heart-cut.")

    width, height = final_img.size
    raster = io.BytesIO()
    final_img.save(raster, format='PNG', dpi=(300, 300))
    data_uri = base64.b64encode(raster.getvalue()).decode('ascii')

    if circle_cut:
        left, top, right, bottom = circle_cut_bounds(width, height)
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        radius = min(right - left, bottom - top) / 2.0
        vector = (
            f'<circle cx="{cx:.3f}" cy="{cy:.3f}" r="{radius:.3f}" '
            'fill="none" stroke="#0000ff" stroke-width="1" />'
        )
    else:
        points = ' '.join(f'{x:.3f},{y:.3f}' for x, y in heart_cut_points(width, height))
        vector = (
            f'<polygon points="{points}" fill="none" '
            'stroke="#0000ff" stroke-width="1" />'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width / 300:.6f}in" height="{height / 300:.6f}in" '
        f'viewBox="0 0 {width} {height}">\n'
        f'  <image x="0" y="0" width="{width}" height="{height}" '
        f'href="data:image/png;base64,{data_uri}" '
        f'xlink:href="data:image/png;base64,{data_uri}" />\n'
        f'  {vector}\n'
        '</svg>\n'
    )


def write_svg_cut(final_img, svg_path, circle_cut=False, heart_cut=False):
    """Write an aligned SVG containing an embedded raster and a vector cut stroke."""
    document = render_svg_document(final_img, circle_cut=circle_cut, heart_cut=heart_cut)

    def write_document(temporary_path):
        with open(temporary_path, 'w', encoding='utf-8') as svg_file:
            svg_file.write(document)

    _atomic_write(svg_path, write_document)

def prep_for_glowforge(
    input_path, 
    output_path, 
    black_thresh=0, 
    white_thresh=255, 
    dither_thresh=128, 
    clean_solids=False, 
    clean_solids_black=35,
    clean_solids_white=220,
    invert=False, 
    width_in=None, 
    height_in=None, 
    no_border=False,
    denoise_radius=0,
    contrast=1.5,
    sharpen_radius=2.0,
    sharpen_percent=150,
    sharpen_threshold=3,
    circle_cut=False,
    heart_cut=False,
    fit_mode='stretch',
    svg_cut=False
):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids}, Invert: {invert}, W: {width_in}, H: {height_in}, Fit: {fit_mode}, No Border: {no_border}, Denoise: {denoise_radius}, Contrast: {contrast}, Sharpen Radius: {sharpen_radius}, Circle Cut: {circle_cut}, Heart Cut: {heart_cut})...")
    start_time = time.time()
    
    with Image.open(input_path) as img:
        final_img = transform_image(
            img,
            black_thresh=black_thresh,
            white_thresh=white_thresh,
            dither_thresh=dither_thresh,
            clean_solids=clean_solids,
            clean_solids_black=clean_solids_black,
            clean_solids_white=clean_solids_white,
            invert=invert,
            width_in=width_in,
            height_in=height_in,
            no_border=(no_border or svg_cut),
            denoise_radius=denoise_radius,
            contrast=contrast,
            sharpen_radius=sharpen_radius,
            sharpen_percent=sharpen_percent,
            sharpen_threshold=sharpen_threshold,
            circle_cut=circle_cut,
            heart_cut=heart_cut,
            fit_mode=fit_mode
        )

    directory = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(directory, exist_ok=True)
    temp_files = []
    try:
        fd_png, temp_png = tempfile.mkstemp(prefix='.gf-', suffix='.png', dir=directory)
        os.close(fd_png)
        temp_files.append(temp_png)
        final_img.save(temp_png, format='PNG', dpi=(300, 300))

        if svg_cut:
            svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg"
            svg_doc = render_svg_document(final_img, circle_cut=circle_cut, heart_cut=heart_cut)
            fd_svg, temp_svg = tempfile.mkstemp(prefix='.gf-', suffix='.svg', dir=directory)
            os.close(fd_svg)
            temp_files.append(temp_svg)
            with open(temp_svg, 'w', encoding='utf-8') as f:
                f.write(svg_doc)

        # Commit output files atomically only after all renders succeed
        os.replace(temp_png, output_path)
        temp_files.remove(temp_png)
        if svg_cut:
            os.replace(temp_svg, svg_path)
            temp_files.remove(temp_svg)
    finally:
        for temp_path in temp_files:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        final_img.close()
    
    svg_note = f" and {os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else ""
    print(f"Complete. Saved to {output_path}{svg_note} in {round(time.time() - start_time, 2)} seconds.")

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


def process_directory(
    input_dir,
    output_dir,
    black_thresh,
    white_thresh,
    dither_thresh,
    clean_solids,
    clean_solids_black,
    clean_solids_white,
    invert,
    width_in,
    height_in,
    no_border,
    denoise_radius,
    contrast,
    sharpen_radius,
    sharpen_percent,
    sharpen_threshold,
    circle_cut,
    heart_cut,
    preset_name,
    fit_mode='stretch',
    svg_cut=False,
    max_pixels=DEFAULT_MAX_PIXELS,
    machine=None,
    existing='overwrite',
    claimed_outputs=None,
    material=DEFAULT_MATERIAL,
    material_thickness_in=DEFAULT_MATERIAL_THICKNESS_IN,
):
    if existing not in ('overwrite', 'skip', 'error'):
        print(f"Error: unsupported existing-output policy '{existing}'.", file=sys.stderr)
        return False

    print(
        f"Starting batch process for '{input_dir}' "
        f"(material context: {material}, thickness: {material_thickness_in:g} in)."
    )
    supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff', '.gif')

    if not os.path.exists(input_dir):
        print(f"Error: Input path '{input_dir}' does not exist.", file=sys.stderr)
        return False

    if os.path.isdir(input_dir):
        input_root = os.path.realpath(input_dir)
        output_root = os.path.realpath(output_dir)
        try:
            output_is_inside_input = os.path.commonpath((input_root, output_root)) == input_root
        except ValueError:
            output_is_inside_input = False
        if output_is_inside_input:
            print(
                f"Error: output directory '{output_dir}' is inside input directory '{input_dir}'. "
                "Choose a separate output directory to avoid reprocessing generated images.",
                file=sys.stderr,
            )
            return False
        input_files = []
        for root, dirs, filenames in os.walk(input_dir):
            dirs.sort()
            input_files.extend(
                os.path.join(root, filename)
                for filename in sorted(filenames)
                if filename.lower().endswith(supported_extensions)
            )
    elif input_dir.lower().endswith(supported_extensions):
        input_files = [input_dir]
    else:
        print(f"Error: Input path '{input_dir}' is not a directory or supported image file.", file=sys.stderr)
        return False

    if not input_files:
        print(f"Error: no supported images found in '{input_dir}'.", file=sys.stderr)
        return False

    os.makedirs(output_dir, exist_ok=True)
    if claimed_outputs is None:
        claimed_outputs = set()

    success = True
    preset_dict = PRESETS.get(preset_name, {}) if preset_name else {}
    for input_path in input_files:
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        ext_clean = ext.lstrip('.').lower()

        try:
            dim_suffix = output_geometry(input_path, width_in, height_in, max_pixels, machine)
        except Exception as exc:
            print(f"Error preparing {filename}: {exc}", file=sys.stderr)
            success = False
            continue

        # Compare resolved options against the preset (or defaults) in one place.
        baseline = {
            'black_thresh': DEFAULTS['black_threshold'],
            'white_thresh': DEFAULTS['white_threshold'],
            'dither_thresh': DEFAULTS['dither_threshold'],
            'clean_solids': DEFAULTS['clean_solids'],
            'clean_solids_black': DEFAULTS['clean_solids_black'],
            'clean_solids_white': DEFAULTS['clean_solids_white'],
            'invert': DEFAULTS['invert'],
            'no_border': DEFAULTS['no_border'],
            'denoise_radius': DEFAULTS['denoise'],
            'contrast': DEFAULTS['contrast'],
            'sharpen_radius': DEFAULTS['sharpen_radius'],
            'sharpen_percent': DEFAULTS['sharpen_percent'],
            'sharpen_threshold': DEFAULTS['sharpen_threshold'],
            'circle_cut': DEFAULTS['circle_cut'],
            'heart_cut': DEFAULTS['heart_cut'],
            'fit_mode': DEFAULTS['fit_mode'],
        }
        baseline.update(preset_dict)
        values = {
            'black_thresh': black_thresh,
            'white_thresh': white_thresh,
            'dither_thresh': dither_thresh,
            'clean_solids': clean_solids,
            'clean_solids_black': clean_solids_black,
            'clean_solids_white': clean_solids_white,
            'invert': invert,
            'no_border': no_border,
            'denoise_radius': denoise_radius,
            'contrast': contrast,
            'sharpen_radius': sharpen_radius,
            'sharpen_percent': sharpen_percent,
            'sharpen_threshold': sharpen_threshold,
            'circle_cut': circle_cut,
            'heart_cut': heart_cut,
            'fit_mode': fit_mode,
        }
        tags = []
        if preset_name:
            tags.append(f"pr{preset_name}")
        tag_formats = {
            'black_thresh': lambda value: f"b{value}",
            'white_thresh': lambda value: f"W{value}",
            'dither_thresh': lambda value: f"d{value}",
            'invert': lambda value: 'inv' if value else 'noinv',
            'no_border': lambda value: 'nb' if value else 'border',
            'denoise_radius': lambda value: f"dn{value}",
            'contrast': lambda value: f"c{value:g}",
            'fit_mode': lambda value: f"fit{value}",
        }
        for key, formatter in tag_formats.items():
            if values[key] != baseline[key]:
                tags.append(formatter(values[key]))
        if clean_solids != baseline['clean_solids']:
            tags.append('clean' if clean_solids else 'noclean')
        if clean_solids and (
            clean_solids_black != baseline['clean_solids_black']
            or clean_solids_white != baseline['clean_solids_white']
        ):
            tags.append(f"csb{clean_solids_black}w{clean_solids_white}")
        if any(values[key] != baseline[key] for key in ('sharpen_radius', 'sharpen_percent', 'sharpen_threshold')):
            tags.append(f"sh{sharpen_radius:g}p{sharpen_percent}t{sharpen_threshold}")
        if circle_cut != baseline['circle_cut']:
            tags.append('cc' if circle_cut else 'nocc')
        if heart_cut != baseline['heart_cut']:
            tags.append('hc' if heart_cut else 'nohc')
        if svg_cut:
            tags.append('svg')

        settings_str = '_'.join(tags) if tags else 'dithered'
        output_filename = f"{name}_{ext_clean}_{settings_str}{dim_suffix}.png"
        if os.path.isdir(input_dir):
            rel_dir = os.path.dirname(os.path.relpath(input_path, start=input_dir))
            target_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
        else:
            target_dir = output_dir
        output_path = os.path.join(target_dir, output_filename)

        svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else None
        expected_outputs = [output_path] + ([svg_path] if svg_path else [])
        output_claims = [os.path.normcase(os.path.realpath(path)) for path in expected_outputs]
        if any(claim in claimed_outputs for claim in output_claims):
            print(f"Error: multiple input files map to one or more of {expected_outputs}. Rename or separate the inputs.", file=sys.stderr)
            success = False
            continue
        claimed_outputs.update(output_claims)

        existing_outputs = [path for path in expected_outputs if os.path.exists(path)]
        if existing_outputs:
            if existing == 'skip':
                if len(existing_outputs) != len(expected_outputs):
                    print(
                        f"Error: incomplete existing output set for '{output_path}'; found {existing_outputs}. "
                        "Repair or remove the partial set, or rerun with --existing overwrite.",
                        file=sys.stderr,
                    )
                    success = False
                    continue
                print(f"Skipping existing output set: {expected_outputs}")
                continue
            if existing == 'error':
                print(f"Error: output already exists: {existing_outputs}", file=sys.stderr)
                success = False
                continue

        try:
            prep_for_glowforge(
                input_path,
                output_path,
                black_thresh=black_thresh,
                white_thresh=white_thresh,
                dither_thresh=dither_thresh,
                clean_solids=clean_solids,
                clean_solids_black=clean_solids_black,
                clean_solids_white=clean_solids_white,
                invert=invert,
                width_in=width_in,
                height_in=height_in,
                no_border=no_border,
                denoise_radius=denoise_radius,
                contrast=contrast,
                sharpen_radius=sharpen_radius,
                sharpen_percent=sharpen_percent,
                sharpen_threshold=sharpen_threshold,
                circle_cut=circle_cut,
                heart_cut=heart_cut,
                fit_mode=fit_mode,
                svg_cut=svg_cut,
            )
        except Exception as exc:
            print(f"Error processing {filename}: {exc}", file=sys.stderr)
            success = False

    return success

def resolve_settings(args):
    """Resolve defaults, preset values, then explicit CLI overrides."""
    preset = PRESETS.get(args.preset, {}) if args.preset else {}
    fields = (
        ('black_threshold', 'black_threshold', 'black_thresh', 'black_threshold'),
        ('white_threshold', 'white_threshold', 'white_thresh', 'white_threshold'),
        ('dither_threshold', 'dither_threshold', 'dither_thresh', 'dither_threshold'),
        ('clean_solids', 'clean_solids', 'clean_solids', 'clean_solids'),
        ('clean_solids_black', 'clean_solids_black', 'clean_solids_black', 'clean_solids_black'),
        ('clean_solids_white', 'clean_solids_white', 'clean_solids_white', 'clean_solids_white'),
        ('invert', 'invert', 'invert', 'invert'),
        ('no_border', 'no_border', 'no_border', 'no_border'),
        ('denoise', 'denoise', 'denoise_radius', 'denoise'),
        ('contrast', 'contrast', 'contrast', 'contrast'),
        ('sharpen_radius', 'sharpen_radius', 'sharpen_radius', 'sharpen_radius'),
        ('sharpen_percent', 'sharpen_percent', 'sharpen_percent', 'sharpen_percent'),
        ('sharpen_threshold', 'sharpen_threshold', 'sharpen_threshold', 'sharpen_threshold'),
        ('circle_cut', 'circle_cut', 'circle_cut', 'circle_cut'),
        ('heart_cut', 'heart_cut', 'heart_cut', 'heart_cut'),
        ('fit_mode', 'fit_mode', None, 'fit_mode'),
    )
    resolved = {}
    for field, argument, preset_key, default_key in fields:
        explicit = getattr(args, argument)
        if explicit is not None:
            resolved[field] = explicit
        elif preset_key is not None and preset_key in preset:
            resolved[field] = preset[preset_key]
        else:
            resolved[field] = DEFAULTS[default_key]
    return ProcessingSettings(**resolved)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Prepare raster artwork for Glowforge. Project material context: "
            f"{DEFAULT_MATERIAL} at {DEFAULT_MATERIAL_THICKNESS_IN:g} in. "
            "This tool does not set laser power, speed, or passes."
        ),
        add_help=False,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--help', action='help', help='Show this help message and exit.')
    parser.add_argument('--input', nargs='+', default=['input'], help='One or more image files or folders.')
    parser.add_argument('-o', '--output', default='output', help='Folder where processed files are saved.')
    parser.add_argument('-p', '--preset', choices=sorted(PRESETS), help='Image-preparation preset; does not select machine settings.')
    parser.add_argument('--material', default=DEFAULT_MATERIAL, help='Descriptive stock label for this run; it does not change processing or machine settings.')
    parser.add_argument('--material-thickness', type=positive_inches_type, default=DEFAULT_MATERIAL_THICKNESS_IN, metavar='IN', help='Descriptive stock thickness in inches; accepts decimals or fractions such as 0.125 or 1/8.')
    parser.add_argument('-b', '--black-threshold', type=threshold_type, default=None, help='Force pixels at or below this grayscale value to black.')
    parser.add_argument('-W', '--white-threshold', type=threshold_type, default=None, help='Force pixels at or above this grayscale value to white.')
    parser.add_argument('-d', '--dither-threshold', type=threshold_type, default=None, help='Atkinson decision threshold for midtones.')
    parser.add_argument('-c', '--clean-solids', action=argparse.BooleanOptionalAction, default=None, help='Snap near-black and near-white pixels to solid values.')
    parser.add_argument('--clean-solids-black', type=threshold_type, default=None, help='Near-black snapping threshold.')
    parser.add_argument('--clean-solids-white', type=threshold_type, default=None, help='Near-white snapping threshold.')
    parser.add_argument('-i', '--invert', action=argparse.BooleanOptionalAction, default=None, help='Invert grayscale values before thresholding and dithering.')
    parser.add_argument('-w', '--width', type=positive_float_type, default=None, help='Target physical width in inches at 300 DPI.')
    parser.add_argument('-h', '--height', type=positive_float_type, default=None, help='Target physical height in inches at 300 DPI.')
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', default=None, help='Disable the 1-pixel bitmap border.')
    parser.add_argument('--denoise', type=odd_int_type, default=None, help='Median filter size; must be an odd integer of at least 3.')
    parser.add_argument('--contrast', type=positive_float_type, default=None, help='Contrast enhancement factor.')
    parser.add_argument('--sharpen-radius', type=positive_float_type, default=None, help='Unsharp-mask radius.')
    parser.add_argument('--sharpen-percent', type=positive_int_type, default=None, help='Unsharp-mask strength percentage.')
    parser.add_argument('--sharpen-threshold', type=non_negative_int_type, default=None, help='Unsharp-mask minimum brightness difference.')
    parser.add_argument('--circle-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a circular transparent raster mask.')
    parser.add_argument('--heart-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a heart-shaped transparent raster mask.')
    parser.add_argument('--fit', '--fit-mode', dest='fit_mode', choices=('stretch', 'contain', 'cover'), default=None, help='When both target dimensions are given: stretch, fit inside with white padding, or fill and crop.')
    parser.add_argument('--svg-cut', action='store_true', help='Write an SVG sidecar with an embedded engraving image and vector cut outline. Requires a circle or heart shape.')
    parser.add_argument('--machine', choices=sorted(MACHINE_BEDS_IN), help='Check approximate nominal printable area for a Glowforge model.')
    parser.add_argument('--max-pixels', type=positive_int_type, default=DEFAULT_MAX_PIXELS, help='Maximum source and output pixels per image.')
    parser.add_argument('--existing', choices=('overwrite', 'skip', 'error'), default='overwrite', help='Policy for an existing PNG and its optional SVG sidecar.')
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = resolve_settings(args)

    if not args.material.strip():
        parser.error('--material must contain a descriptive label.')
    if settings.circle_cut and settings.heart_cut:
        parser.error('Cannot apply both --circle-cut and --heart-cut.')
    if settings.black_threshold > settings.white_threshold:
        parser.error('Resolved black threshold cannot be greater than the white threshold.')
    if settings.clean_solids_black > settings.clean_solids_white:
        parser.error('Resolved clean-solids black threshold cannot be greater than the white threshold.')
    if args.svg_cut and not (settings.circle_cut or settings.heart_cut):
        parser.error('--svg-cut requires --circle-cut, --heart-cut, or a coaster preset.')

    all_success = True
    claimed_outputs = set()
    for input_path in args.input:
        succeeded = process_directory(
            input_path,
            args.output,
            preset_name=args.preset,
            width_in=args.width,
            height_in=args.height,
            svg_cut=args.svg_cut,
            max_pixels=args.max_pixels,
            machine=args.machine,
            existing=args.existing,
            claimed_outputs=claimed_outputs,
            material=args.material.strip(),
            material_thickness_in=args.material_thickness,
            **settings.transform_kwargs(),
        )
        all_success = all_success and succeeded
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
