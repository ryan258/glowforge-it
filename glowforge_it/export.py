"""Rendering and publishing one image's output set.

Builds the PNG and the optional SVG sidecar, then hands the whole generation to
`publication` rather than implementing a second recovery path.
"""

import base64
import io
import hashlib
from importlib.metadata import version
import json
import os
import sys
import time

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .geometry import circle_cut_bounds, heart_cut_points
from .imaging import transform_image
from .publication import publish_generation, sha256_file, stage_beside
from .settings import __version__, DEFAULT_MATERIAL, DEFAULT_MATERIAL_THICKNESS_IN
from .workflow import (WorkflowOptions, layout, mask_record, appearance_record,
                       finish_preview, render_operations, orientation_advice, intended_operations, digest, PALETTE)
from .proof import write_proof


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


def build_manifest(
    source_path,
    output_path,
    output_img,
    recipe_dict,
    svg_path=None,
    output_sha256=None,
    svg_sha256=None,
    prompt=None,
    model=None,
    manifest_path=None,
):
    """Construct a versioned job manifest dictionary."""
    source_sha = sha256_file(source_path) if os.path.exists(source_path) else None
    src_size = [0, 0]
    src_mode = "unknown"
    try:
        with Image.open(source_path) as src:
            src_size = list(src.size)
            src_mode = src.mode
    except Exception:
        pass

    out_w, out_h = output_img.size
    cut_shape = "circle" if recipe_dict.get('circle_cut') else ("heart" if recipe_dict.get('heart_cut') else "none")

    outputs = {
        os.path.basename(output_path): {
            "format": "png",
            "sha256": output_sha256,
        }
    }
    if svg_path:
        outputs[os.path.basename(svg_path)] = {
            "format": "svg",
            "sha256": svg_sha256,
        }

    return {
        "schema_version": "1.0",
        "tool": {
            "name": "glowforge-it",
            "version": __version__,
            "python": sys.version.split()[0],
        },
        "source": {
            "filename": os.path.basename(source_path),
            "relpath": os.path.relpath(source_path, os.path.dirname(os.path.abspath(manifest_path or output_path))),
            "sha256": source_sha,
            "original_size": src_size,
            "mode": src_mode,
        },
        "geometry": {
            "output_size": [out_w, out_h],
            "dpi": 300,
            "physical_size_in": [round(out_w / 300.0, 4), round(out_h / 300.0, 4)],
            "cut_shape": cut_shape,
        },
        "recipe": recipe_dict,
        "provenance": {
            "prompt": prompt,
            "model": model,
        },
        "outputs": outputs,
    }


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
    svg_cut=False,
    manifest=False,
    manifest_path=None,
    preset_name=None,
    material=None,
    material_thickness_in=None,
    prompt=None,
    model=None,
    quiet=False,
    workflow=None,
    machine=None,
):
    workflow = workflow or WorkflowOptions()
    workflow.validate(invert=invert, svg_cut=svg_cut, machine=machine)
    manifest = manifest or workflow.active
    if workflow.active:
        material = DEFAULT_MATERIAL if material is None else material
        material_thickness_in = DEFAULT_MATERIAL_THICKNESS_IN if material_thickness_in is None else material_thickness_in
    if not quiet:
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
            no_border=(no_border or svg_cut or workflow.suppress_border),
            denoise_radius=denoise_radius,
            contrast=contrast,
            sharpen_radius=sharpen_radius,
            sharpen_percent=sharpen_percent,
            sharpen_threshold=sharpen_threshold,
            circle_cut=circle_cut,
            heart_cut=heart_cut,
            fit_mode=fit_mode,
            workflow=workflow,
        )

    geometry = layout(workflow, final_img.size, machine=machine, circle_cut=circle_cut)
    full_image = final_img
    mask = mask_record(full_image)
    if workflow.trim:
        # A blank job uses an explicit 1px no-burn sentinel; SVG omits the image.
        final_img = full_image.crop(mask['bounds_px']) if mask['bounds_px'] else Image.new('1', (1, 1), 1)
    staged_pairs = []
    svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else None
    manifest_target = manifest_path or (f"{os.path.splitext(output_path)[0]}_manifest.json" if manifest else None)
    try:
        staged_png = stage_beside(output_path, lambda path: final_img.save(path, format='PNG', dpi=(300, 300)))
        staged_pairs.append((output_path, staged_png))

        staged_svg = None
        if svg_cut:
            svg_doc = render_svg_document(final_img, circle_cut=circle_cut, heart_cut=heart_cut)

            def write_svg(path):
                with open(path, 'w', encoding='utf-8') as svg_file:
                    svg_file.write(svg_doc)

            staged_svg = stage_beside(svg_path, write_svg)
            staged_pairs.append((svg_path, staged_svg))

        if manifest or workflow.active:
            recipe_dict = {
                'preset': preset_name,
                'black_thresh': black_thresh,
                'white_thresh': white_thresh,
                'dither_thresh': dither_thresh,
                'clean_solids': clean_solids,
                'clean_solids_black': clean_solids_black,
                'clean_solids_white': clean_solids_white,
                'invert': invert,
                'width_in': width_in,
                'height_in': height_in,
                'fit_mode': fit_mode,
                'no_border': (no_border or svg_cut or workflow.suppress_border),
                'denoise_radius': denoise_radius,
                'contrast': contrast,
                'sharpen_radius': sharpen_radius,
                'sharpen_percent': sharpen_percent,
                'sharpen_threshold': sharpen_threshold,
                'circle_cut': circle_cut,
                'heart_cut': heart_cut,
                'svg_cut': svg_cut,
                'manifest': manifest,
                'material': material,
                'material_thickness_in': material_thickness_in,
            }
            if workflow.active:
                recipe_dict['workflow'] = workflow.record()
                recipe_dict['machine'] = machine
                appearance = appearance_record(workflow) if workflow.preview_finish or workflow.proof_sheet else None
                record = {
                    'schema_version': '1.0', 'tool_version': __version__, 'source_sha256': sha256_file(input_path),
                    'runtime': {name: version(name) for name in ('numpy', 'pillow', 'reportlab')},
                    'recipe_sha256': digest(recipe_dict), 'engraving_sha256': sha256_file(staged_png),
                    'mask': mask, 'geometry': geometry, 'appearance': appearance,
                    'appearance_sha256': digest(appearance) if appearance else None,
                    'palette': PALETTE if workflow.svg else None,
                    'intended_order': intended_operations(workflow, mask, cut=svg_cut or (workflow.svg and (circle_cut or heart_cut))),
                    'import_status': 'unverified in Glowforge app',
                    'trim': {'enabled': workflow.trim, 'offset_px': mask['bounds_px'][:2] if mask['bounds_px'] and workflow.trim else [0, 0],
                             'standalone_png_loses_placement': workflow.trim},
                    'orientation': orientation_advice(workflow, geometry, mask['bounds_px'], machine),
                    'customer_approved': False,
                }
                preview = finish_preview(full_image, workflow) if appearance else None
                if preview is not None:
                    record['appearance']['pixels_sha256'] = hashlib.sha256(preview.tobytes()).hexdigest()
                    record['appearance_sha256'] = digest(record['appearance'])
                paths = workflow.paths(output_path)
                if workflow.svg:
                    document = render_operations(full_image, workflow, geometry, circle_cut=circle_cut, heart_cut=heart_cut)
                    def write_operations(path):
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(document)
                    staged_pairs.append((paths['operations'], stage_beside(paths['operations'], write_operations)))
                    record['operations_sha256'] = sha256_file(staged_pairs[-1][1])
                if staged_svg:
                    record['operations_sha256'] = sha256_file(staged_svg)
                record['revision'] = digest(record)
                if appearance:
                    png_info = PngInfo()
                    png_info.add_text('Description', appearance['label'])
                    png_info.add_text('Revision', record['revision'])
                    staged_pairs.append((paths['finish'], stage_beside(paths['finish'], lambda p: preview.save(p, format='PNG', dpi=(300, 300), pnginfo=png_info))))
                if workflow.proof_sheet:
                    staged_pairs.append((paths['proof'], stage_beside(paths['proof'], lambda p: write_proof(p, input_path, preview, record, material, material_thickness_in, workflow))))
                def write_workflow(path):
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(record, f, indent=2)
                staged_pairs.append((paths['workflow'], stage_beside(paths['workflow'], write_workflow)))

        if manifest:
            manifest_data = build_manifest(
                source_path=input_path,
                output_path=output_path,
                output_img=final_img,
                recipe_dict=recipe_dict,
                svg_path=svg_path,
                output_sha256=sha256_file(staged_png),
                svg_sha256=sha256_file(staged_svg) if staged_svg else None,
                prompt=prompt,
                model=model,
                manifest_path=manifest_target,
            )

            if workflow.active:
                manifest_data['workflow'] = record
                for destination, staged in staged_pairs:
                    manifest_data['outputs'][os.path.basename(destination)] = {
                        'format': os.path.splitext(destination)[1][1:], 'sha256': sha256_file(staged)}

            def write_manifest(path):
                with open(path, 'w', encoding='utf-8') as mf:
                    json.dump(manifest_data, mf, indent=2)

            staged_pairs.append((manifest_target, stage_beside(manifest_target, write_manifest)))

        # Publish the whole generation, or leave the previous one intact.
        publish_generation(staged_pairs)
    except BaseException:
        for _, staged in staged_pairs:
            if os.path.lexists(staged):
                try:
                    os.unlink(staged)
                except OSError:
                    pass
        raise
    finally:
        final_img.close()
        if full_image is not final_img:
            full_image.close()
    
    elapsed = round(time.time() - start_time, 2)
    svg_note = f" and {svg_path}" if svg_cut else ""
    manifest_note = f" and {manifest_target}" if manifest else ""
    if not quiet:
        print(f"Complete. Saved to {output_path}{svg_note}{manifest_note} in {elapsed} seconds.")
    return {
        'output_path': output_path,
        'svg_path': svg_path,
        'manifest_path': manifest_target,
        'duration_seconds': elapsed,
        'artifacts': workflow.paths(output_path),
        'workflow_summary': record if workflow.active else None,
    }
