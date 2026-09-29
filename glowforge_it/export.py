"""Rendering and publishing one image's output set.

Builds the PNG and the optional SVG sidecar, then hands the whole generation to
`publication` rather than implementing a second recovery path.
"""

import base64
import io
import hashlib
from importlib.metadata import PackageNotFoundError, version
from dataclasses import asdict, replace
from contextlib import ExitStack
import json
import os
import sys
import time

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .geometry import circle_cut_svg, heart_cut_points
from .imaging import transform_image
from .publication import publish_generation, sha256_file, stage_beside
from .settings import __version__, ProcessingSettings
from .workflow import (WorkflowOptions, layout, mask_record, appearance_record,
                       finish_preview, render_operations, intended_operations, digest, PALETTE)
from .proof import write_proof
from .vector import render_centerline_svg
from .personalization import render_text_stamp
from .qr import render_qr_stamp


def _installed_version(name):
    """Version string, or None for an optional package (reportlab) that is not installed."""
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def render_svg_document(final_img, circle_cut=False, heart_cut=False):
    """Generate aligned SVG document string with embedded raster and vector cut stroke."""
    if not (circle_cut or heart_cut):
        raise ValueError("SVG cut output requires --circle-cut or --heart-cut.")

    width, height = final_img.size
    raster = io.BytesIO()
    final_img.save(raster, format='PNG', dpi=(300, 300))
    data_uri = base64.b64encode(raster.getvalue()).decode('ascii')

    if circle_cut:
        cx, cy, radius = circle_cut_svg(width, height)
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


def stage_text(destination, text):
    def write(path):
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
    return stage_beside(destination, write)


def stage_png(destination, image, **options):
    return stage_beside(destination, lambda path: image.save(
        path, format='PNG', dpi=(300, 300), **options))


def build_manifest(
    source_path,
    output_path,
    output_img,
    recipe_dict,
    svg_path=None,
    linework_path=None,
    output_sha256=None,
    svg_sha256=None,
    linework_sha256=None,
    layer_paths=None,
    stamp_path=None,
    stamp_sha256=None,
    qr_path=None,
    qr_sha256=None,
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

    records = [
        (output_path, 'png', None, output_sha256),
        (svg_path, 'svg', None, svg_sha256),
        (linework_path, 'svg', 'centerline-style-linework', linework_sha256),
        *((path, 'png', 'registered-exclusive-tone-layer', sha) for path, sha in (layer_paths or {}).items()),
        (stamp_path, 'png', 'personalization-stamp', stamp_sha256),
        (qr_path, 'png', 'protected-qr-mark', qr_sha256),
    ]
    outputs = {
        os.path.basename(path): {'format': fmt, **({'role': role} if role else {}), 'sha256': sha}
        for path, fmt, role, sha in records if path
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


def prep_for_glowforge(input_path, output_path, settings=None, *, width_in=None, height_in=None,
                       manifest_path=None, preset_name=None, prompt=None, model=None,
                       quiet=False, workflow=None, machine=None):
    settings = settings or ProcessingSettings()
    workflow = workflow or WorkflowOptions()
    workflow.validate(invert=settings.invert, svg_cut=settings.svg_cut, machine=machine)
    settings = replace(settings, manifest=settings.manifest or workflow.active)
    settings.validate()
    if not quiet:
        print(f"Processing {input_path} (render mode: {settings.render_mode}, fit: {settings.fit_mode})...")
    start_time = time.time()
    with ExitStack() as resources:
        with Image.open(input_path) as img:
            final_img = transform_image(
                img, replace(settings, no_border=settings.no_border or settings.svg_cut or workflow.suppress_border),
                width_in=width_in, height_in=height_in, workflow=workflow,
            )
        resources.callback(final_img.close)


        geometry = layout(workflow, final_img.size, machine=machine, circle_cut=settings.circle_cut)
        full_image = final_img
        mask = mask_record(full_image)
        if workflow.trim:
            # A blank job uses an explicit 1px no-burn sentinel; SVG omits the image.
            final_img = full_image.crop(mask['bounds_px']) if mask['bounds_px'] else Image.new('1', (1, 1), 1)
            resources.callback(final_img.close)
        staged_pairs = []
        svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg" if settings.svg_cut else None
        linework_path = f"{os.path.splitext(output_path)[0]}_linework.svg" if settings.svg_linework else None
        layer_paths = {
            index: f"{os.path.splitext(output_path)[0]}_tone{index:02d}of{settings.tone_layers}.png"
            for index in range(1, settings.tone_layers + 1)
        }
        stamp_path = f"{os.path.splitext(output_path)[0]}_stamp.png" if settings.stamp_text is not None else None
        qr_path = f"{os.path.splitext(output_path)[0]}_qr.png" if settings.qr_text is not None else None
        manifest_target = manifest_path or (f"{os.path.splitext(output_path)[0]}_manifest.json" if settings.manifest else None)
        try:
            staged_png = stage_png(output_path, final_img)
            staged_pairs.append((output_path, staged_png))

            staged_svg = None
            if settings.svg_cut:
                svg_doc = render_svg_document(final_img, circle_cut=settings.circle_cut, heart_cut=settings.heart_cut)

                staged_svg = stage_text(svg_path, svg_doc)
                staged_pairs.append((svg_path, staged_svg))

            staged_linework = None
            if settings.svg_linework:
                linework_doc = render_centerline_svg(
                    final_img,
                    source_label=os.path.basename(input_path),
                )

                staged_linework = stage_text(linework_path, linework_doc)
                staged_pairs.append((linework_path, staged_linework))

            staged_layers = {}
            if settings.tone_layers:
                boundaries = [round(256 * index / settings.tone_layers) for index in range(settings.tone_layers + 1)]
                layer_settings = replace(settings, no_border=True, render_mode='silhouette', silhouette_threshold=128)
                with Image.open(input_path) as layer_source:
                    for index in range(1, settings.tone_layers + 1):
                        layer_image = transform_image(
                            layer_source, layer_settings,
                            tone_band=(boundaries[index - 1], boundaries[index]),
                            width_in=width_in, height_in=height_in, workflow=workflow,
                        )
                        resources.callback(layer_image.close)
                        if workflow.trim:
                            layer_image = layer_image.crop(mask['bounds_px']) if mask['bounds_px'] else Image.new('1', (1, 1), 1)
                            resources.callback(layer_image.close)
                        layer_path = layer_paths[index]
                        staged_layer = stage_png(layer_path, layer_image)
                        staged_layers[index] = staged_layer
                        staged_pairs.append((layer_path, staged_layer))

            staged_stamp = None
            stamp_record = None
            if settings.stamp_text is not None:
                stamp_image, stamp_record = render_text_stamp(
                    final_img,
                    settings.stamp_text,
                    position=settings.stamp_position,
                    size_px=settings.stamp_size_px,
                    margin_px=settings.stamp_margin_px,
                )
                resources.callback(stamp_image.close)
                staged_stamp = stage_png(stamp_path, stamp_image)
                staged_pairs.append((stamp_path, staged_stamp))

            staged_qr = None
            qr_record = None
            if settings.qr_text is not None:
                qr_image, qr_record = render_qr_stamp(
                    final_img,
                    settings.qr_text,
                    position=settings.qr_position,
                    module_px=settings.qr_module_px,
                    margin_px=settings.qr_margin_px,
                )
                resources.callback(qr_image.close)
                staged_qr = stage_png(qr_path, qr_image)
                staged_pairs.append((qr_path, staged_qr))

            if settings.manifest or workflow.active:
                recipe_dict = {
                    **asdict(settings),
                    'preset': preset_name, 'width_in': width_in, 'height_in': height_in,
                    'no_border': settings.no_border or settings.svg_cut or workflow.suppress_border,
                }
                if workflow.active:
                    recipe_dict['workflow'] = workflow.record()
                    recipe_dict['machine'] = machine
                    appearance = appearance_record(workflow) if workflow.preview_finish or workflow.proof_sheet else None
                    record = {
                        'schema_version': '1.0', 'tool_version': __version__, 'source_sha256': sha256_file(input_path),
                        'runtime': {name: _installed_version(name) for name in ('numpy', 'pillow', 'reportlab')},
                        'recipe_sha256': digest(recipe_dict), 'engraving_sha256': sha256_file(staged_png),
                        'mask': mask, 'geometry': geometry, 'appearance': appearance,
                        'appearance_sha256': digest(appearance) if appearance else None,
                        'palette': PALETTE if workflow.svg else None,
                        'intended_order': intended_operations(workflow, mask, cut=settings.svg_cut or (workflow.svg and (settings.circle_cut or settings.heart_cut))),
                        'import_status': 'unverified in Glowforge app',
                        'trim': {'enabled': workflow.trim, 'offset_px': mask['bounds_px'][:2] if mask['bounds_px'] and workflow.trim else [0, 0],
                                 'standalone_png_loses_placement': workflow.trim},
                        'customer_approved': False,
                    }
                    preview = finish_preview(full_image, workflow) if appearance else None
                    if preview is not None:
                        resources.callback(preview.close)
                        record['appearance']['pixels_sha256'] = hashlib.sha256(preview.tobytes()).hexdigest()
                        record['appearance_sha256'] = digest(record['appearance'])
                    paths = workflow.paths(output_path)
                    if workflow.svg:
                        document = render_operations(full_image, workflow, geometry, circle_cut=settings.circle_cut, heart_cut=settings.heart_cut)
                        staged_pairs.append((paths['operations'], stage_text(paths['operations'], document)))
                        record['operations_sha256'] = sha256_file(staged_pairs[-1][1])
                    if staged_svg:
                        record['operations_sha256'] = sha256_file(staged_svg)
                    if staged_linework:
                        record['linework_sha256'] = sha256_file(staged_linework)
                    if staged_layers:
                        record['tone_layers'] = [
                            {'index': index, 'count': settings.tone_layers, 'sha256': sha256_file(staged_layers[index])}
                            for index in sorted(staged_layers)
                        ]
                    if staged_stamp:
                        record['stamp'] = {**stamp_record, 'sha256': sha256_file(staged_stamp)}
                    if staged_qr:
                        record['qr'] = {**qr_record, 'sha256': sha256_file(staged_qr)}
                    record['revision'] = digest(record)
                    if appearance:
                        png_info = PngInfo()
                        png_info.add_text('Description', appearance['label'])
                        png_info.add_text('Revision', record['revision'])
                        staged_pairs.append((paths['finish'], stage_png(paths['finish'], preview, pnginfo=png_info)))
                    if workflow.proof_sheet:
                        staged_pairs.append((paths['proof'], stage_beside(paths['proof'], lambda p: write_proof(p, input_path, preview, record, settings.material, settings.material_thickness_in, workflow))))
                    staged_pairs.append((paths['workflow'], stage_text(paths['workflow'], json.dumps(record, indent=2))))

            if settings.manifest:
                manifest_data = build_manifest(
                    source_path=input_path,
                    output_path=output_path,
                    output_img=final_img,
                    recipe_dict=recipe_dict,
                    svg_path=svg_path,
                    linework_path=linework_path,
                    output_sha256=sha256_file(staged_png),
                    svg_sha256=sha256_file(staged_svg) if staged_svg else None,
                    linework_sha256=sha256_file(staged_linework) if staged_linework else None,
                    layer_paths={layer_paths[index]: sha256_file(staged_layers[index]) for index in staged_layers},
                    stamp_path=stamp_path,
                    stamp_sha256=sha256_file(staged_stamp) if staged_stamp else None,
                    qr_path=qr_path,
                    qr_sha256=sha256_file(staged_qr) if staged_qr else None,
                    prompt=prompt,
                    model=model,
                    manifest_path=manifest_target,
                )

                if workflow.active:
                    manifest_data['workflow'] = record
                    for destination, staged in staged_pairs:
                        # setdefault: keep the role build_manifest already recorded.
                        manifest_data['outputs'].setdefault(os.path.basename(destination), {
                            'format': os.path.splitext(destination)[1][1:], 'sha256': sha256_file(staged)})

                staged_pairs.append((manifest_target, stage_text(manifest_target, json.dumps(manifest_data, indent=2))))

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

    elapsed = round(time.time() - start_time, 2)
    svg_note = f" and {svg_path}" if settings.svg_cut else ""
    linework_note = f" and {linework_path}" if settings.svg_linework else ""
    manifest_note = f" and {manifest_target}" if settings.manifest else ""
    if not quiet:
        print(f"Complete. Saved to {output_path}{svg_note}{linework_note}{manifest_note} in {elapsed} seconds.")
    return {
        'output_path': output_path,
        'svg_path': svg_path,
        'linework_path': linework_path,
        'layer_paths': list(layer_paths.values()),
        'stamp_path': stamp_path,
        'qr_path': qr_path,
        'manifest_path': manifest_target,
        'duration_seconds': elapsed,
        'artifacts': {**workflow.paths(output_path), **({'linework': linework_path} if linework_path else {})},
        'workflow_summary': record if workflow.active else None,
    }
