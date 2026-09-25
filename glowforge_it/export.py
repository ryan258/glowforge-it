"""Rendering and publishing one image's output set.

Builds the PNG and the optional SVG sidecar, then hands the whole generation to
`publication` rather than implementing a second recovery path.
"""

import base64
import io
import os
import time

from PIL import Image

from .geometry import circle_cut_bounds, heart_cut_points
from .imaging import transform_image
from .publication import publish_generation, stage_beside

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

    publish_generation([(svg_path, stage_beside(svg_path, write_document))])

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

    staged_pairs = []
    try:
        staged_pairs.append((
            output_path,
            stage_beside(output_path, lambda path: final_img.save(path, format='PNG', dpi=(300, 300))),
        ))
        if svg_cut:
            svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg"
            svg_doc = render_svg_document(final_img, circle_cut=circle_cut, heart_cut=heart_cut)

            def write_svg(path):
                with open(path, 'w', encoding='utf-8') as svg_file:
                    svg_file.write(svg_doc)

            staged_pairs.append((svg_path, stage_beside(svg_path, write_svg)))

        # Publish the whole generation, or leave the previous one intact.
        publish_generation(staged_pairs)
    except BaseException:
        for _, staged in staged_pairs:
            if os.path.lexists(staged):
                os.unlink(staged)
        raise
    finally:
        final_img.close()
    
    svg_note = f" and {os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else ""
    print(f"Complete. Saved to {output_path}{svg_note} in {round(time.time() - start_time, 2)} seconds.")
