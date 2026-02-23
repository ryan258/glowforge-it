# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
#     "pillow",
# ]
# ///

import os
import sys
import argparse
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import time
def prep_for_glowforge(input_path, output_path, black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False, invert=False, width_in=None, height_in=None, no_border=False):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids}, Invert: {invert}, W: {width_in}, H: {height_in}, No Border: {no_border})...")
    start_time = time.time()
    
    # 1. Load Image and Convert to Grayscale
    img = Image.open(input_path).convert('L')
    
    # 1.5 Handle Resize if requested (calculated at 300 DPI)
    if width_in or height_in:
        orig_w, orig_h = img.size
        # If float comes in, convert to int pixels
        target_w = int(width_in * 300) if width_in else None
        target_h = int(height_in * 300) if height_in else None
        
        if target_w and not target_h:
            target_h = int(orig_h * (target_w / float(orig_w)))
        elif target_h and not target_w:
            target_w = int(orig_w * (target_h / float(orig_h)))
            
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    if invert:
        img = ImageOps.invert(img)
    
    # 2. Pre-process Thresholds
    # Map near-solids to pure solids based on configuration
    img_array = np.array(img, dtype=float)
    if clean_solids:
        img_array[img_array < 35] = 0
        img_array[img_array > 220] = 255
    
    if black_thresh > 0:
        img_array[img_array <= black_thresh] = 0
    if white_thresh < 255:
        img_array[img_array >= white_thresh] = 255
        
    img = Image.fromarray(np.uint8(img_array))
    
    # 3. High Contrast / Levels
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5) 
    
    # 4. Unsharp Mask
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    
    # 5. Atkinson Dithering Implementation
    # Convert to float array for precise error diffusion math
    img_array = np.array(img, dtype=float)
    h, w = img_array.shape
    
    for y in range(h):
        for x in range(w):
            old_pixel = img_array[y, x]
            
            # Threshold mid-tones
            new_pixel = 255 if old_pixel > dither_thresh else 0
            img_array[y, x] = new_pixel
            
            # Calculate quantization error
            error = old_pixel - new_pixel
            error_eighth = error / 8.0
            
            # Diffuse the error to neighboring pixels (Atkinson Matrix)
            if x + 1 < w: img_array[y, x + 1] += error_eighth
            if x + 2 < w: img_array[y, x + 2] += error_eighth
            if y + 1 < h:
                if x - 1 >= 0: img_array[y + 1, x - 1] += error_eighth
                img_array[y + 1, x] += error_eighth
                if x + 1 < w: img_array[y + 1, x + 1] += error_eighth
            if y + 2 < h: img_array[y + 2, x] += error_eighth

    # 5. Save out as a 1-bit Bitmap with strict DPI mapping
    # Clip values to valid range, convert to 8-bit, then cast to 1-bit ('1')
    final_img = Image.fromarray(np.uint8(np.clip(img_array, 0, 255))).convert('1')
    
    # 6. Add 1px Black Border for Glowforge Cutout (unless disabled)
    if not no_border:
        draw = ImageDraw.Draw(final_img)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
    
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
        # Gracefully handle if they passed a file instead of a directory by wrapping it in a single list
        if input_dir.lower().endswith(supported_extensions):
            input_dir, filename = os.path.split(input_dir)
            files = [filename]
        else:
            print(f"Error: Input path '{input_dir}' is not a directory or supported image file.", file=sys.stderr)
            return False
    else:
        try:
            files = [f for f in os.listdir(input_dir) if f.lower().endswith(supported_extensions)]
        except Exception as e:
            print(f"Error reading input directory '{input_dir}': {e}", file=sys.stderr)
            return False
    
    if not files:
        print(f"No supported images found in '{input_dir}'.")
        # Technically not a failure of processing, just empty
        return True

    success = True
    for filename in files:
        input_path = os.path.join(input_dir, filename) if input_dir else filename
        name, _ = os.path.splitext(filename)
        suffix = "_invert" if invert else "_dithered"
        
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
                
                # Format to remove trailing .0 if it's a whole number for a cleaner filename
                fw = int(final_w_in) if final_w_in == int(final_w_in) else final_w_in
                fh = int(final_h_in) if final_h_in == int(final_h_in) else final_h_in
                    
                dim_suffix = f"--h{fh}w{fw}"
            except Exception as e:
                print(f"Error reading {filename} for dimensions: {e}", file=sys.stderr)
                fw = width_in if width_in else "auto"
                fh = height_in if height_in else "auto"
                dim_suffix = f"--h{fh}w{fw}"

        output_path = os.path.join(output_dir, f"{name}{suffix}{dim_suffix}.png")
        
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
    parser.add_argument('-b', '--black-threshold', type=int, default=0, help="Pixels darker than this are forced to pure black and not dithered.")
    parser.add_argument('-W', '--white-threshold', type=int, default=255, help="Pixels lighter than this are forced to pure white and not dithered.")
    parser.add_argument('-d', '--dither-threshold', type=int, default=128, help="The cutoff point where mid-tones round to black or white.")
    parser.add_argument('-c', '--clean-solids', action='store_true', help="Snap near-blacks and near-whites to pure solids before any processing. Great for AI images.")
    parser.add_argument('-i', '--invert', action='store_true', help="Invert the black and white values of the image.")
    parser.add_argument('-w', '--width', type=float, default=None, help="Target physical width in inches (calculated at 300 DPI).")
    parser.add_argument('-h', '--height', type=float, default=None, help="Target physical height in inches (calculated at 300 DPI).")
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', help="Disable the automatic 1px black border.")
    
    args = parser.parse_args()
    
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
