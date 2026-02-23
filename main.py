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
def prep_for_glowforge(input_path, output_path, black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False, invert=False):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids}, Invert: {invert})...")
    start_time = time.time()
    
    # 1. Load Image and Convert to Grayscale
    img = Image.open(input_path).convert('L')
    
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
    
    # 6. Add 1px Black Border for Glowforge Cutout
    draw = ImageDraw.Draw(final_img)
    draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
    
    final_img.save(output_path, dpi=(300, 300))
    
    print(f"Complete. Saved to {output_path} in {round(time.time() - start_time, 2)} seconds.")

# --- Execution ---
def process_directory(input_dir, output_dir, black_thresh, white_thresh, dither_thresh, clean_solids, invert):
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
        output_path = os.path.join(output_dir, f"{name}_dithered.png")
        
        try:
            prep_for_glowforge(input_path, output_path, black_thresh, white_thresh, dither_thresh, clean_solids, invert)
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            success = False
            
    return success

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process images for Glowforge 1-bit engraving.")
    parser.add_argument('--input', nargs='+', default=['input'], help="Directory or files containing input images.")
    parser.add_argument('--output', type=str, default='output', help="Directory to save output images.")
    parser.add_argument('--black-threshold', type=int, default=0, help="Pixels darker than this are forced to pure black and not dithered.")
    parser.add_argument('--white-threshold', type=int, default=255, help="Pixels lighter than this are forced to pure white and not dithered.")
    parser.add_argument('--dither-threshold', type=int, default=128, help="The cutoff point where mid-tones round to black or white.")
    parser.add_argument('--clean-solids', action='store_true', help="Snap near-blacks and near-whites to pure solids before any processing. Great for AI images.")
    parser.add_argument('--invert', action='store_true', help="Invert the black and white values of the image.")
    
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
            args.invert
        ):
            all_success = False
            
    if not all_success:
        sys.exit(1)
