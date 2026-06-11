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

def transform_image(img, black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False, invert=False, width_in=None, height_in=None, no_border=False):
    # 1. Apply EXIF orientation
    img = ImageOps.exif_transpose(img)
    
    # 2. Composite alpha/transparency onto white background
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)
        
    # 3. Convert to Grayscale
    img = img.convert('L')
    
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
        img_array[img_array < 35] = 0
        img_array[img_array > 220] = 255
        
    if black_thresh > 0:
        img_array[img_array <= black_thresh] = 0
    if white_thresh < 255:
        img_array[img_array >= white_thresh] = 255
        
    img = Image.fromarray(np.uint8(img_array))
    
    # 6. High Contrast / Levels
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    
    # 7. Unsharp Mask
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    
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
    
    # 9. Add 1px Black Border for Glowforge Cutout (unless disabled)
    if not no_border:
        w, h = final_img.size
        draw = ImageDraw.Draw(final_img)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
        
    return final_img

def prep_for_glowforge(input_path, output_path, black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False, invert=False, width_in=None, height_in=None, no_border=False):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids}, Invert: {invert}, W: {width_in}, H: {height_in}, No Border: {no_border})...")
    start_time = time.time()
    
    img = Image.open(input_path)
    final_img = transform_image(
        img,
        black_thresh=black_thresh,
        white_thresh=white_thresh,
        dither_thresh=dither_thresh,
        clean_solids=clean_solids,
        invert=invert,
        width_in=width_in,
        height_in=height_in,
        no_border=no_border
    )
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_img.save(output_path, dpi=(300, 300))
    
    print(f"Complete. Saved to {output_path} in {round(time.time() - start_time, 2)} seconds.")

# --- Execution ---
def process_directory(input_dir, output_dir, black_thresh, white_thresh, dither_thresh, clean_solids, invert, width_in, height_in, no_border):
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
        settings.append(f"b{black_thresh}")
        settings.append(f"W{white_thresh}")
        settings.append(f"d{dither_thresh}")
        if clean_solids:
            settings.append("clean")
        if invert:
            settings.append("inv")
        if no_border:
            settings.append("nb")
            
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
            prep_for_glowforge(input_path, output_path, black_thresh, white_thresh, dither_thresh, clean_solids, invert, width_in, height_in, no_border)
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            success = False
            
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process images for Glowforge 1-bit engraving.", add_help=False)
    parser.add_argument('--help', action='help', help="Show this help message and exit.")
    parser.add_argument('--input', nargs='+', default=['input'], help="Directory or files containing input images.")
    parser.add_argument('-o', '--output', type=str, default='output', help="Directory to save output images.")
    parser.add_argument('-b', '--black-threshold', type=threshold_type, default=0, help="Pixels darker than this are forced to pure black and not dithered.")
    parser.add_argument('-W', '--white-threshold', type=threshold_type, default=255, help="Pixels lighter than this are forced to pure white and not dithered.")
    parser.add_argument('-d', '--dither-threshold', type=threshold_type, default=128, help="The cutoff point where mid-tones round to black or white.")
    parser.add_argument('-c', '--clean-solids', action='store_true', help="Snap near-blacks and near-whites to pure solids before any processing. Great for AI images.")
    parser.add_argument('-i', '--invert', action='store_true', help="Invert the black and white values of the image.")
    parser.add_argument('-w', '--width', type=positive_float_type, default=None, help="Target physical width in inches (calculated at 300 DPI).")
    parser.add_argument('-h', '--height', type=positive_float_type, default=None, help="Target physical height in inches (calculated at 300 DPI).")
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', help="Disable the automatic 1px black border.")
    
    args = parser.parse_args()
    
    if args.black_threshold > args.white_threshold:
        parser.error(f"Black threshold ({args.black_threshold}) cannot be greater than white threshold ({args.white_threshold}).")
    
    all_success = True
    for input_path in args.input:
        if not process_directory(
            input_path, 
            args.output, 
            args.black_threshold, 
            args.white_threshold, 
            args.dither_threshold,
            args.clean_solids,
            args.invert,
            args.width,
            args.height,
            args.no_border
        ):
            all_success = False
            
    if not all_success:
        sys.exit(1)
