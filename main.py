import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import time

def prep_for_glowforge(input_path, output_path):
    print(f"Processing {input_path}...")
    start_time = time.time()
    
    # 1. Load Image and Convert to Grayscale
    img = Image.open(input_path).convert('L')
    
    # 2. High Contrast / Levels
    # Pushes the background to pure white to prevent laser misfires in negative space
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5) 
    
    # 3. Unsharp Mask
    # Creates "halos" around lines to compensate for the 0.2mm laser kerf bleed
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    
    # 4. Atkinson Dithering Implementation
    # Convert to float array for precise error diffusion math
    img_array = np.array(img, dtype=float)
    h, w = img_array.shape
    
    for y in range(h):
        for x in range(w):
            old_pixel = img_array[y, x]
            # Threshold at 128 (mid-gray)
            new_pixel = 255 if old_pixel > 128 else 0
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
# Replace with your actual file paths
if __name__ == "__main__":
    prep_for_glowforge('zombie_geese.jpg', 'zombie_geese_dithered.png')
