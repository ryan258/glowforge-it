"""Image-to-image transformation: normalize, tone, dither, mask.

Takes an open image and returns an image. It never chooses a destination path.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from array import array

from .geometry import circle_cut_bounds, heart_cut_points, resolve_target_dimensions

# --fit contain pads with this value. It is layout, not artwork: it does not invert.
CANVAS_BACKGROUND = 255

def _resize_to_canvas(image, target_size, fit_mode):
    """Resize for the requested fit.

    Returns (image, canvas_plan). For 'contain' the image comes back at its own
    proportional size with a canvas_plan of (canvas_size, paste_offset): the padding is
    laid down after dithering, so contrast, thresholds, sharpening and error diffusion
    never turn layout background into engraving pixels or bleed across the seam.
    """
    target_w, target_h = target_size
    if fit_mode == 'stretch':
        return image.resize(target_size, Image.Resampling.LANCZOS), None

    if fit_mode == 'cover':
        # Resample directly from the source crop that maps onto the canvas. Scaling the
        # whole image first would allocate width*scale x height*scale pixels, which is
        # unbounded for extreme aspect ratios (a 20000x1 source into 300x300).
        scale = max(target_w / image.width, target_h / image.height)
        crop_w = min(image.width, target_w / scale)
        crop_h = min(image.height, target_h / scale)
        left = (image.width - crop_w) / 2
        top = (image.height - crop_h) / 2
        box = (left, top, left + crop_w, top + crop_h)
        return image.resize(target_size, Image.Resampling.LANCZOS, box=box), None

    # contain: the scaled image never exceeds the canvas, so it is already bounded.
    scale = min(target_w / image.width, target_h / image.height)
    resized_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(resized_size, Image.Resampling.LANCZOS)
    offset = ((target_w - resized_size[0]) // 2, (target_h - resized_size[1]) // 2)
    return resized, (target_size, offset)

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
    
    # 2. Composite alpha/transparency onto white background.
    #    Covers RGBA/LA/PA alpha channels and colour-key tRNS on RGB, L and P sources.
    if img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info:
        img = img.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(background, img)
        
    # 3. Convert to Grayscale
    img = img.convert('L')
    
    # 3.5 Apply Denoising (Median Filter) if requested (great for AI artifacts)
    if denoise_radius > 0:
        img = img.filter(ImageFilter.MedianFilter(size=denoise_radius))
        
    canvas_plan = None

    # 3.6 Invert before layout. Padding added by --fit contain is the layout background,
    #     not artwork, so it must not flip with the artwork's tonal polarity.
    if invert:
        img = ImageOps.invert(img)

    # 4. Handle Resize if requested (calculated at 300 DPI)
    if width_in is not None or height_in is not None:
        orig_w, orig_h = img.size
        target_w, target_h = resolve_target_dimensions(
            orig_w, orig_h, width_in=width_in, height_in=height_in
        )
            
        if target_w <= 0 or target_h <= 0:
            raise ValueError("Requested physical size is too small to produce at least one pixel at 300 DPI.")
        if fit_mode not in ('stretch', 'contain', 'cover'):
            raise ValueError(f"Unsupported fit mode: {fit_mode}")
        img, canvas_plan = _resize_to_canvas(img, (target_w, target_h), fit_mode)

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
    
    # 7. Unsharp Mask (0 radius or 0 percent means "off")
    if sharpen_radius > 0 and sharpen_percent > 0:
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

    # 8.5 Lay the processed artwork onto the layout canvas. --fit contain padding is
    #     background, so it is added after dithering and is always CANVAS_BACKGROUND.
    if canvas_plan is not None:
        canvas_size, offset = canvas_plan
        canvas = Image.new('1', canvas_size, 1 if CANVAS_BACKGROUND else 0)
        canvas.paste(final_img, offset)
        final_img = canvas

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
