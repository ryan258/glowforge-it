"""Image-to-image transformation: normalize, tone, dither, mask.

Takes an open image and returns an image. It never chooses a destination path.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from .geometry import circle_cut_bounds, heart_cut_points, resolve_target_dimensions, get_oriented_dimensions, transpose_source_image
from .contracts import working_memory
from .renderers import render_mask
from .settings import DEFAULT_MAX_PIXELS, ProcessingSettings, ValidationError, validate_limits
from .workflow import WorkflowOptions

# --fit contain pads with this value. It is layout, not artwork: it does not invert.
CANVAS_BACKGROUND = 255


def to_8bit(img):
    """Scale high-bit-depth grayscale to 8-bit, retaining color-key alpha as 'LA'.

    Samples within a recognized range use its full scale; other finite, varying
    samples stretch from minimum to maximum. Reject undefined scales and non-finite values.
    """
    if img.mode.startswith('I;16'):
        samples, full = np.asarray(img, dtype=np.float64), 65535.0
    elif img.mode in ('I', 'F'):
        samples = np.asarray(img, dtype=np.float64)
    else:
        return img
    if not np.isfinite(samples).all():
        raise ValidationError('Grayscale source contains NaN or infinity; replace invalid samples in the source artwork.')
    minimum, maximum = samples.min(), samples.max()
    if img.mode in ('I', 'F'):
        full = 1.0 if img.mode == 'F' else next((f for f in (255.0, 65535.0) if maximum <= f), None)
    if full is not None and minimum >= 0 and maximum <= full:
        low, high = 0.0, full
    elif minimum == maximum:
        raise ValidationError('Constant grayscale source is outside the recognized sample range; convert it to an explicit 8-bit or normalized image.')
    else:
        low, high = minimum, maximum
    scaled = np.clip((samples - low) / (high - low), 0.0, 1.0)
    result = Image.fromarray(np.rint(scaled * 255).astype(np.uint8))
    if 'transparency' in img.info:
        # Compare original samples: distinct opaque shades can round to the
        # same 8-bit value as the transparent key.
        with Image.fromarray(np.where(samples == img.info['transparency'], 0, 255).astype(np.uint8)) as alpha:
            result.putalpha(alpha)
    return result


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

def transform_image(img, settings=None, *, width_in=None, height_in=None, tone_band=None, workflow=None,
                    max_pixels=DEFAULT_MAX_PIXELS, max_memory=None):
    s = settings or ProcessingSettings()
    s.validate()
    validate_limits(width_in, height_in, max_pixels, max_memory, None)
    workflow = workflow or WorkflowOptions()
    workflow.validate_tone(invert=s.invert)
    ow, oh = get_oriented_dimensions(img)
    tw, th = resolve_target_dimensions(ow, oh, width_in, height_in)
    if min(tw, th) < 1 or max(ow*oh, tw*th) > max_pixels:
        raise ValidationError('Source and output dimensions must be positive and within --max-pixels.')
    estimate = working_memory(ow, oh, tw, th, s, workflow, max_pixels=max_pixels)
    if max_memory is not None and estimate > max_memory:
        raise ValidationError('Estimated memory exceeds budget; reduce dimensions or increase --max-memory.')
    if tone_band is not None:
        if (not isinstance(tone_band, (tuple, list)) or len(tone_band) != 2
                or any(type(value) is not int for value in tone_band)
                or not 0 <= tone_band[0] < tone_band[1] <= 256):
            raise ValueError("Tone band must be an increasing pair of integer bounds from 0 through 256.")
    # 1. Apply EXIF orientation
    img = to_8bit(transpose_source_image(img))

    alpha = None
    # 2. Composite alpha/transparency onto the source-space no-burn endpoint.
    #    Covers RGBA/LA/PA alpha channels and colour-key tRNS on RGB, L and P sources.
    if img.mode in ('RGBA', 'LA', 'PA') or 'transparency' in img.info:
        img = img.convert('RGBA')
        alpha = img.getchannel('A')
        background_value = 0 if workflow.material_mode == 'lightening' or s.invert else 255
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
        # tw/th were resolved and bounds-checked above; settings.validate() covers fit_mode.
        img, canvas_plan = _resize_to_canvas(img, (tw, th), s.fit_mode)
        if alpha is not None:
            alpha, _ = _resize_to_canvas(alpha, (tw, th), s.fit_mode)

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
    transparent_pixels = alpha.point(lambda a: 255 if a == 0 else 0) if alpha is not None else None
    if transparent_pixels is not None:
        # Fully transparent pixels cannot become burn content after filtering.
        img.paste(255, mask=transparent_pixels)

    if tone_band is not None:
        lower, upper = tone_band
        values = np.asarray(img, dtype=np.uint8)
        # White is no burn, including in the lightest alternative tone layer.
        in_band = (values >= lower) & (values < upper) & (values < 255)
        img = Image.fromarray(np.where(in_band, 0, 255).astype(np.uint8), mode='L')

    # 8. Render the binary burn mask.  All renderer modes share the same
    # machine-artifact contract; only the mark-making algorithm changes.
    final_img = render_mask(img, s, preserve_endpoints=workflow.material_mode != 'legacy', max_pixels=max_pixels)

    if transparent_pixels is not None:
        final_img.paste(255, mask=transparent_pixels)

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
