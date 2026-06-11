# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy==2.4.2",
#     "pillow==12.1.1",
# ]
# ///

import os
import sys
import argparse
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import time

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
    'circle_cut': False
}

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
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(f"Dimension '{value}' must be greater than 0.")
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
    circle_cut=False
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
    if width_in or height_in:
        orig_w, orig_h = img.size
        target_w = int(width_in * 300) if width_in else None
        target_h = int(height_in * 300) if height_in else None
        
        if target_w and not target_h:
            target_h = int(orig_h * (target_w / float(orig_w)))
        elif target_h and not target_w:
            target_w = int(orig_w * (target_h / float(orig_h)))
            
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        
    if invert:
        img = ImageOps.invert(img)
        
    # 5. Pre-process Thresholds
    img_array = np.array(img, dtype=float)
    if clean_solids:
        img_array[img_array < clean_solids_black] = 0
        img_array[img_array > clean_solids_white] = 255
        
    if black_thresh > 0:
        img_array[img_array <= black_thresh] = 0
    if white_thresh < 255:
        img_array[img_array >= white_thresh] = 255
        
    img = Image.fromarray(np.uint8(img_array))
    
    # 6. High Contrast / Levels
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)
    
    # 7. Unsharp Mask
    img = img.filter(ImageFilter.UnsharpMask(radius=sharpen_radius, percent=sharpen_percent, threshold=sharpen_threshold))
    
    # 8. Atkinson Dithering Implementation
    img_array = np.array(img, dtype=float)
    h, w = img_array.shape
    
    # Pad array: 1 column left, 2 columns right, 2 rows bottom to avoid boundary checks
    padded = np.pad(img_array, ((0, 2), (1, 2)), mode='constant', constant_values=0.0)
    
    # Convert to nested list to avoid NumPy 2D indexing overhead in the loop
    lst = padded.tolist()
    
    for y in range(h):
        row_y = lst[y]
        row_y1 = lst[y + 1]
        row_y2 = lst[y + 2]
        for x in range(1, w + 1):
            old_pixel = row_y[x]
            new_pixel = 255.0 if old_pixel > dither_thresh else 0.0
            row_y[x] = new_pixel
            
            error = old_pixel - new_pixel
            error_eighth = error * 0.125
            
            row_y[x + 1] += error_eighth
            row_y[x + 2] += error_eighth
            row_y1[x - 1] += error_eighth
            row_y1[x] += error_eighth
            row_y1[x + 1] += error_eighth
            row_y2[x] += error_eighth
            
    final_arr = np.array(lst, dtype=float)[0:h, 1:w + 1]
    final_img = Image.fromarray(np.uint8(np.clip(final_arr, 0, 255))).convert('1')
    
    # 9. Add 1px Black Border / Circular Coaster Cutout (unless disabled)
    w, h = final_img.size
    if circle_cut:
        rgba_img = final_img.convert('RGBA')
        
        # Create alpha mask (0 = transparent outside circle)
        mask = Image.new('L', (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        diameter = min(w, h)
        left = (w - diameter) // 2
        top = (h - diameter) // 2
        right = left + diameter - 1
        bottom = top + diameter - 1
        
        # Draw opaque circle
        draw_mask.ellipse([left, top, right, bottom], fill=255)
        rgba_img.putalpha(mask)
        
        # Draw the black circular outline for Glowforge cut path
        if not no_border:
            draw_rgba = ImageDraw.Draw(rgba_img)
            draw_rgba.ellipse([left, top, right, bottom], outline=(0, 0, 0, 255), width=1)
            
        final_img = rgba_img
    elif not no_border:
        draw = ImageDraw.Draw(final_img)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
        
    return final_img

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
    circle_cut=False
):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids}, Invert: {invert}, W: {width_in}, H: {height_in}, No Border: {no_border}, Denoise: {denoise_radius}, Contrast: {contrast}, Sharpen Radius: {sharpen_radius}, Circle Cut: {circle_cut})...")
    start_time = time.time()
    
    img = Image.open(input_path)
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
        no_border=no_border,
        denoise_radius=denoise_radius,
        contrast=contrast,
        sharpen_radius=sharpen_radius,
        sharpen_percent=sharpen_percent,
        sharpen_threshold=sharpen_threshold,
        circle_cut=circle_cut
    )
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_img.save(output_path, dpi=(300, 300))
    
    print(f"Complete. Saved to {output_path} in {round(time.time() - start_time, 2)} seconds.")

# --- Execution ---
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
    preset_name
):
    print(f"Starting batch process for '{input_dir}'...")
    os.makedirs(output_dir, exist_ok=True)
    
    supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
    
    if not os.path.exists(input_dir):
        print(f"Error: Input path '{input_dir}' does not exist.", file=sys.stderr)
        return False
        
    if not os.path.isdir(input_dir):
        if input_dir.lower().endswith(supported_extensions):
            input_files = [input_dir]
        else:
            print(f"Error: Input path '{input_dir}' is not a directory or supported image file.", file=sys.stderr)
            return False
    else:
        input_files = []
        for root, _, filenames in os.walk(input_dir):
            for f in filenames:
                if f.lower().endswith(supported_extensions):
                    input_files.append(os.path.join(root, f))
    
    if not input_files:
        print(f"No supported images found in '{input_dir}'.")
        return True

    success = True
    for input_path in input_files:
        filename = os.path.basename(input_path)
        name, ext = os.path.splitext(filename)
        ext_clean = ext.lstrip('.').lower()
        
        # Build settings tags for collision-resistance
        settings = []
        if preset_name:
            settings.append(f"pr{preset_name}")
            preset_dict = PRESETS[preset_name]
            if black_thresh != preset_dict.get('black_thresh', DEFAULTS['black_threshold']):
                settings.append(f"b{black_thresh}")
            if white_thresh != preset_dict.get('white_thresh', DEFAULTS['white_threshold']):
                settings.append(f"W{white_thresh}")
            if dither_thresh != preset_dict.get('dither_thresh', DEFAULTS['dither_threshold']):
                settings.append(f"d{dither_thresh}")
            if clean_solids != preset_dict.get('clean_solids', DEFAULTS['clean_solids']):
                settings.append("clean" if clean_solids else "noclean")
            if clean_solids and (clean_solids_black != preset_dict.get('clean_solids_black', DEFAULTS['clean_solids_black']) or clean_solids_white != preset_dict.get('clean_solids_white', DEFAULTS['clean_solids_white'])):
                settings.append(f"csb{clean_solids_black}w{clean_solids_white}")
            if invert != preset_dict.get('invert', DEFAULTS['invert']):
                settings.append("inv" if invert else "noinv")
            if no_border != preset_dict.get('no_border', DEFAULTS['no_border']):
                settings.append("nb" if no_border else "border")
            if denoise_radius != preset_dict.get('denoise_radius', DEFAULTS['denoise']):
                settings.append(f"dn{denoise_radius}")
            if contrast != preset_dict.get('contrast', DEFAULTS['contrast']):
                settings.append(f"c{contrast}")
            if sharpen_radius != preset_dict.get('sharpen_radius', DEFAULTS['sharpen_radius']) or sharpen_percent != preset_dict.get('sharpen_percent', DEFAULTS['sharpen_percent']) or sharpen_threshold != preset_dict.get('sharpen_threshold', DEFAULTS['sharpen_threshold']):
                settings.append(f"sh{sharpen_radius}p{sharpen_percent}t{sharpen_threshold}")
            if circle_cut != preset_dict.get('circle_cut', DEFAULTS['circle_cut']):
                settings.append("cc" if circle_cut else "nocc")
        else:
            if black_thresh != DEFAULTS['black_threshold']:
                settings.append(f"b{black_thresh}")
            if white_thresh != DEFAULTS['white_threshold']:
                settings.append(f"W{white_thresh}")
            if dither_thresh != DEFAULTS['dither_threshold']:
                settings.append(f"d{dither_thresh}")
            if clean_solids != DEFAULTS['clean_solids']:
                settings.append("clean")
                if clean_solids_black != DEFAULTS['clean_solids_black'] or clean_solids_white != DEFAULTS['clean_solids_white']:
                    settings.append(f"csb{clean_solids_black}w{clean_solids_white}")
            if invert != DEFAULTS['invert']:
                settings.append("inv")
            if no_border != DEFAULTS['no_border']:
                settings.append("nb")
            if denoise_radius != DEFAULTS['denoise']:
                settings.append(f"dn{denoise_radius}")
            if contrast != DEFAULTS['contrast']:
                settings.append(f"c{contrast}")
            if sharpen_radius != DEFAULTS['sharpen_radius'] or sharpen_percent != DEFAULTS['sharpen_percent'] or sharpen_threshold != DEFAULTS['sharpen_threshold']:
                settings.append(f"sh{sharpen_radius}p{sharpen_percent}t{sharpen_threshold}")
            if circle_cut != DEFAULTS['circle_cut']:
                settings.append("cc")
                
        if not settings:
            settings_str = "dithered"
        else:
            settings_str = "_".join(settings)
        
        dim_suffix = ""
        if width_in or height_in:
            try:
                with Image.open(input_path) as img:
                    orig_w, orig_h = img.size
                
                final_w_in = width_in
                final_h_in = height_in
                
                if final_w_in and not final_h_in:
                    final_h_in = round((orig_h / orig_w) * final_w_in, 2)
                elif final_h_in and not final_w_in:
                    final_w_in = round((orig_w / orig_h) * final_h_in, 2)
                
                fw = int(final_w_in) if final_w_in == int(final_w_in) else final_w_in
                fh = int(final_h_in) if final_h_in == int(final_h_in) else final_h_in
                    
                dim_suffix = f"_w{fw}h{fh}"
            except Exception as e:
                print(f"Error reading {filename} for dimensions: {e}", file=sys.stderr)
                fw = width_in if width_in else "auto"
                fh = height_in if height_in else "auto"
                dim_suffix = f"_w{fw}h{fh}"

        output_filename = f"{name}_{ext_clean}_{settings_str}{dim_suffix}.png"
        
        # Reconstruct directory structure under output_dir
        cwd = os.getcwd()
        try:
            rel_path = os.path.relpath(input_path, start=cwd)
        except ValueError:
            rel_path = None
            
        if rel_path and not rel_path.startswith("..") and not os.path.isabs(rel_path):
            if os.path.isdir(input_dir):
                rel_dir = os.path.dirname(os.path.relpath(input_path, start=input_dir))
                target_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
            else:
                target_dir = output_dir
        else:
            if os.path.isdir(input_dir):
                rel_dir = os.path.dirname(os.path.relpath(input_path, start=input_dir))
                target_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
            else:
                target_dir = output_dir
                
        output_path = os.path.join(target_dir, output_filename)
        
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
                circle_cut=circle_cut
            )
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            success = False
            
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process images for Glowforge 1-bit engraving.", add_help=False)
    parser.add_argument('--help', action='help', help="Show this help message and exit.")
    parser.add_argument('--input', nargs='+', default=['input'], help="Directory or files containing input images.")
    parser.add_argument('-o', '--output', type=str, default='output', help="Directory to save output images.")
    parser.add_argument('-p', '--preset', type=str, choices=list(PRESETS.keys()), default=None, help="Use a preconfigured preset for engraving.")
    parser.add_argument('-b', '--black-threshold', type=threshold_type, default=None, help="Pixels darker than this are forced to pure black and not dithered.")
    parser.add_argument('-W', '--white-threshold', type=threshold_type, default=None, help="Pixels lighter than this are forced to pure white and not dithered.")
    parser.add_argument('-d', '--dither-threshold', type=threshold_type, default=None, help="The cutoff point where mid-tones round to black or white.")
    parser.add_argument('-c', '--clean-solids', action='store_true', default=None, help="Snap near-blacks and near-whites to pure solids before any processing. Great for AI images.")
    parser.add_argument('--clean-solids-black', type=threshold_type, default=None, help="Black cutoff limit for snapping near-solids when using --clean-solids (default: 35).")
    parser.add_argument('--clean-solids-white', type=threshold_type, default=None, help="White cutoff limit for snapping near-solids when using --clean-solids (default: 220).")
    parser.add_argument('-i', '--invert', action='store_true', default=None, help="Invert the black and white values of the image.")
    parser.add_argument('-w', '--width', type=positive_float_type, default=None, help="Target physical width in inches (calculated at 300 DPI).")
    parser.add_argument('-h', '--height', type=positive_float_type, default=None, help="Target physical height in inches (calculated at 300 DPI).")
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', default=None, help="Disable the automatic 1px black border.")
    parser.add_argument('--denoise', type=odd_int_type, default=None, help="Denoise image using median filter of specified size (must be odd integer >= 3).")
    parser.add_argument('--contrast', type=positive_float_type, default=None, help="Contrast enhancement factor (default: 1.5).")
    parser.add_argument('--sharpen-radius', type=positive_float_type, default=None, help="Sharpening radius for unsharp mask (default: 2.0).")
    parser.add_argument('--sharpen-percent', type=positive_int_type, default=None, help="Sharpening percentage for unsharp mask (default: 150).")
    parser.add_argument('--sharpen-threshold', type=non_negative_int_type, default=None, help="Sharpening threshold for unsharp mask (default: 3).")
    parser.add_argument('--circle-cut', action='store_true', default=None, help="Apply circular cutout mask and border (useful for coasters).")
    
    args = parser.parse_args()
    
    # Resolve preset and overrides
    preset_dict = PRESETS.get(args.preset, {}) if args.preset else {}
    
    black_thresh = args.black_threshold if args.black_threshold is not None else preset_dict.get('black_thresh', DEFAULTS['black_threshold'])
    white_thresh = args.white_threshold if args.white_threshold is not None else preset_dict.get('white_thresh', DEFAULTS['white_threshold'])
    dither_thresh = args.dither_threshold if args.dither_threshold is not None else preset_dict.get('dither_thresh', DEFAULTS['dither_threshold'])
    clean_solids = args.clean_solids if args.clean_solids is not None else preset_dict.get('clean_solids', DEFAULTS['clean_solids'])
    clean_solids_black = args.clean_solids_black if args.clean_solids_black is not None else preset_dict.get('clean_solids_black', DEFAULTS['clean_solids_black'])
    clean_solids_white = args.clean_solids_white if args.clean_solids_white is not None else preset_dict.get('clean_solids_white', DEFAULTS['clean_solids_white'])
    invert = args.invert if args.invert is not None else preset_dict.get('invert', DEFAULTS['invert'])
    no_border = args.no_border if args.no_border is not None else preset_dict.get('no_border', DEFAULTS['no_border'])
    denoise_radius = args.denoise if args.denoise is not None else preset_dict.get('denoise_radius', DEFAULTS['denoise'])
    contrast = args.contrast if args.contrast is not None else preset_dict.get('contrast', DEFAULTS['contrast'])
    sharpen_radius = args.sharpen_radius if args.sharpen_radius is not None else preset_dict.get('sharpen_radius', DEFAULTS['sharpen_radius'])
    sharpen_percent = args.sharpen_percent if args.sharpen_percent is not None else preset_dict.get('sharpen_percent', DEFAULTS['sharpen_percent'])
    sharpen_threshold = args.sharpen_threshold if args.sharpen_threshold is not None else preset_dict.get('sharpen_threshold', DEFAULTS['sharpen_threshold'])
    circle_cut = args.circle_cut if args.circle_cut is not None else preset_dict.get('circle_cut', DEFAULTS['circle_cut'])
    
    if black_thresh > white_thresh:
        parser.error(f"Resolved Black threshold ({black_thresh}) cannot be greater than white threshold ({white_thresh}).")
    if clean_solids_black > clean_solids_white:
        parser.error(f"Resolved Clean solids black limit ({clean_solids_black}) cannot be greater than white limit ({clean_solids_white}).")
    
    all_success = True
    for input_path in args.input:
        if not process_directory(
            input_path, 
            args.output, 
            black_thresh, 
            white_thresh, 
            dither_thresh,
            clean_solids,
            clean_solids_black,
            clean_solids_white,
            invert,
            args.width,
            args.height,
            no_border,
            denoise_radius,
            contrast,
            sharpen_radius,
            sharpen_percent,
            sharpen_threshold,
            circle_cut,
            args.preset
        ):
            all_success = False
            
    if not all_success:
        sys.exit(1)
