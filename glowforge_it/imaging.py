"""Image-to-image transformation: normalize, tone, dither, mask.

Takes an open image and returns an image. It never chooses a destination path.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .geometry import circle_cut_bounds, heart_cut_points, resolve_target_dimensions
from .renderers import render_mask, RENDER_MODES
from .settings import ProcessingSettings

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

def transform_image(img, settings=None, *, width_in=None, height_in=None, tone_band=None, workflow=None):
    s = settings or ProcessingSettings()
    from .workflow import WorkflowOptions
    workflow = workflow or WorkflowOptions()
    workflow.validate_tone(invert=s.invert)
    if s.render_mode not in RENDER_MODES:
        raise ValueError(f"Unsupported render mode: {s.render_mode}")
    if type(s.silhouette_threshold) is not int or not 0 <= s.silhouette_threshold <= 255:
        raise ValueError("Silhouette threshold must be an integer between 0 and 255.")
    if s.ordered_matrix_size not in (2, 4, 8):
        raise ValueError("Ordered matrix size must be 2, 4, or 8.")
    if type(s.halftone_cell_px) is not int or s.halftone_cell_px < 2:
        raise ValueError("Halftone cell size must be an integer of at least 2 pixels.")
    if not isinstance(s.halftone_angle, (int, float)) or not np.isfinite(s.halftone_angle) or not 0 <= s.halftone_angle < 180:
        raise ValueError("Halftone angle must be finite and in the range 0 <= angle < 180.")
    if type(s.hatch_spacing_px) is not int or s.hatch_spacing_px < 2:
        raise ValueError("Hatch line spacing must be an integer of at least 2 pixels.")
    if not isinstance(s.hatch_angle, (int, float)) or not np.isfinite(s.hatch_angle) or not 0 <= s.hatch_angle < 180:
        raise ValueError("Hatch angle must be finite and in the range 0 <= angle < 180.")
    if type(s.hatch_cross) is not bool:
        raise ValueError("Hatch cross must be a boolean.")
    if type(s.edge_threshold) is not int or not 1 <= s.edge_threshold <= 255:
        raise ValueError("Edge threshold must be an integer between 1 and 255.")
    if type(s.contour_levels) is not int or not 2 <= s.contour_levels <= 64:
        raise ValueError("Contour levels must be an integer between 2 and 64.")
    if tone_band is not None:
        if (not isinstance(tone_band, (tuple, list)) or len(tone_band) != 2
                or any(type(value) is not int for value in tone_band)
                or not 0 <= tone_band[0] < tone_band[1] <= 256):
            raise ValueError("Tone band must be an increasing pair of integer bounds from 0 through 256.")
    # 1. Apply EXIF orientation
    img = ImageOps.exif_transpose(img)
    
    alpha = None
    # 2. Composite alpha/transparency onto white background.
    #    Covers RGBA/LA/PA alpha channels and colour-key tRNS on RGB, L and P sources.
    if img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info:
        img = img.convert('RGBA')
        alpha = img.getchannel('A') if workflow.material_mode != 'legacy' else None
        background_value = 0 if workflow.material_mode == 'lightening' else 255
        background = Image.new('RGBA', img.size, (background_value,) * 3 + (255,))
        img = Image.alpha_composite(background, img)
        
    # 3. Convert to Grayscale
    img = img.convert('L')
    
    # 3.5 Apply Denoising (Median Filter) if requested (great for AI artifacts)
    if s.denoise_radius > 0:
        img = img.filter(ImageFilter.MedianFilter(size=s.denoise_radius))
        
    canvas_plan = None

    # 3.6 Invert before layout. Padding added by --fit contain is the layout background,
    #     not artwork, so it must not flip with the artwork's tonal polarity.
    if s.invert:
        img = ImageOps.invert(img)

    # 4. Handle Resize if requested (calculated at 300 DPI)
    if width_in is not None or height_in is not None:
        orig_w, orig_h = img.size
        target_w, target_h = resolve_target_dimensions(
            orig_w, orig_h, width_in=width_in, height_in=height_in
        )
            
        if target_w <= 0 or target_h <= 0:
            raise ValueError("Requested physical size is too small to produce at least one pixel at 300 DPI.")
        if s.fit_mode not in ('stretch', 'contain', 'cover'):
            raise ValueError(f"Unsupported fit mode: {s.fit_mode}")
        img, canvas_plan = _resize_to_canvas(img, (target_w, target_h), s.fit_mode)
        if alpha is not None:
            alpha, _ = _resize_to_canvas(alpha, (target_w, target_h), s.fit_mode)

    # 5. Pre-process Thresholds
    img_array = np.array(img, dtype=np.uint8)
    if s.clean_solids:
        img_array[img_array < s.clean_solids_black] = 0
        img_array[img_array > s.clean_solids_white] = 255
        
    if s.black_thresh > 0:
        img_array[img_array <= s.black_thresh] = 0
    if s.white_thresh < 255:
        img_array[img_array >= s.white_thresh] = 255
        
    img = Image.fromarray(img_array)
    
    # 6. High Contrast / Levels
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(s.contrast)
    
    # 7. Unsharp Mask (0 radius or 0 percent means "off")
    if s.sharpen_radius > 0 and s.sharpen_percent > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=s.sharpen_radius, percent=s.sharpen_percent, threshold=s.sharpen_threshold))
    
    # Explicit tone curve maps source luminance to laser burn encoding.
    # L = clip((luminance-black)/(white-black)) ** (1/gamma).
    # Darkening emits L; lightening emits 1-L. Black always means burn.
    if workflow.material_mode != 'legacy':
        lut = []
        for value in range(256):
            level = min(1.0, max(0.0, (value - workflow.tone_black) / (workflow.tone_white - workflow.tone_black))) ** (1 / workflow.tone_gamma)
            lut.append(round(255 * (1 - level if workflow.material_mode == 'lightening' else level)))
        img = img.point(lut)
        if alpha is not None:
            # Fully transparent pixels cannot become burn content after filtering.
            img.paste(255, mask=alpha.point(lambda a: 255 if a == 0 else 0))

    if tone_band is not None:
        lower, upper = tone_band
        values = np.asarray(img, dtype=np.uint8)
        in_band = (values >= lower) & (values < upper)
        img = Image.fromarray(np.where(in_band, 0, 255).astype(np.uint8), mode='L')

    # 8. Render the binary burn mask.  All renderer modes share the same
    # machine-artifact contract; only the mark-making algorithm changes.
    final_img = render_mask(img, s, preserve_endpoints=workflow.material_mode != 'legacy')

    if alpha is not None:
        final_img.paste(255, mask=alpha.point(lambda a: 255 if a == 0 else 0))

    # 8.5 Lay the processed artwork onto the layout canvas. --fit contain padding is
    #     background, so it is added after dithering and is always CANVAS_BACKGROUND.
    if canvas_plan is not None:
        canvas_size, offset = canvas_plan
        canvas = Image.new('1', canvas_size, 1 if CANVAS_BACKGROUND else 0)
        canvas.paste(final_img, offset)
        final_img = canvas

    # 9. Add 1px Black Border / Coaster Cutout (unless disabled)
    w, h = final_img.size
    if s.circle_cut:
        rgba_img = final_img.convert('RGBA')
        
        # Create alpha mask (0 = transparent outside circle)
        mask = Image.new('L', (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        left, top, right, bottom = circle_cut_bounds(w, h)
        
        # Draw opaque circle
        draw_mask.ellipse([left, top, right, bottom], fill=255)
        rgba_img.putalpha(mask)
        
        # This optional bitmap outline is for registration; it engraves.
        if not s.no_border:
            draw_rgba = ImageDraw.Draw(rgba_img)
            draw_rgba.ellipse([left, top, right, bottom], outline=(0, 0, 0, 255), width=1)
            
        final_img = rgba_img
    elif s.heart_cut:
        rgba_img = final_img.convert('RGBA')
        
        # Create alpha mask (0 = transparent outside heart)
        mask = Image.new('L', (w, h), 0)
        draw_mask = ImageDraw.Draw(mask)
        
        points = heart_cut_points(w, h)
            
        # Draw opaque heart on mask
        draw_mask.polygon(points, fill=255)
        rgba_img.putalpha(mask)
        
        # This optional bitmap outline is for registration; it engraves.
        if not s.no_border:
            draw_rgba = ImageDraw.Draw(rgba_img)
            draw_rgba.polygon(points, outline=(0, 0, 0, 255), width=1)
            
        final_img = rgba_img
    elif not s.no_border:
        draw = ImageDraw.Draw(final_img)
        draw.rectangle([0, 0, w - 1, h - 1], outline=0, width=1)
        
    return final_img
