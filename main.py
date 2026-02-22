# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
#     "pillow",
# ]
# ///

import os
import argparse
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import time
def prep_for_glowforge(input_path, output_path, black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False):
    print(f"Processing {input_path} (Black: {black_thresh}, White: {white_thresh}, Dither: {dither_thresh}, Clean Solids: {clean_solids})...")
    start_time = time.time()
    
    # 1. Load Image and Convert to Grayscale
    img = Image.open(input_path).convert('L')
    
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
    final_img.save(output_path, dpi=(300, 300))
    
    print(f"Complete. Saved to {output_path} in {round(time.time() - start_time, 2)} seconds.")

# --- Execution ---
def process_directory(input_dir, output_dir, black_thresh, white_thresh, dither_thresh, clean_solids):
    print(f"Starting batch process in '{input_dir}'...")
    os.makedirs(output_dir, exist_ok=True)
    
    supported_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
    
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(supported_extensions)]
    
    if not files:
        print(f"No supported images found in '{input_dir}'.")
        return

    for filename in files:
        input_path = os.path.join(input_dir, filename)
        name, _ = os.path.splitext(filename)
        output_path = os.path.join(output_dir, f"{name}_dithered.png")
        
        try:
            prep_for_glowforge(input_path, output_path, black_thresh, white_thresh, dither_thresh, clean_solids)
        except Exception as e:
            print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process images for Glowforge 1-bit engraving.")
    parser.add_argument('--input', type=str, default='input', help="Directory containing input images.")
    parser.add_argument('--output', type=str, default='output', help="Directory to save output images.")
    parser.add_argument('--black-threshold', type=int, default=0, help="Pixels darker than this are forced to pure black and not dithered.")
    parser.add_argument('--white-threshold', type=int, default=255, help="Pixels lighter than this are forced to pure white and not dithered.")
    parser.add_argument('--dither-threshold', type=int, default=128, help="The cutoff point where mid-tones round to black or white.")
    parser.add_argument('--clean-solids', action='store_true', help="Snap near-blacks and near-whites to pure solids before any processing. Great for AI images.")
    
    args = parser.parse_args()
    
    process_directory(
        args.input, 
        args.output, 
        args.black_threshold, 
        args.white_threshold, 
        args.dither_threshold,
        args.clean_solids
    )
