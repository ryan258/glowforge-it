"""Rendering and publishing one image's output set.

Builds the PNG and the optional SVG sidecar, then hands the whole generation to
`publication` rather than implementing a second recovery path.
"""

import base64
import io
import hashlib
from dataclasses import asdict, replace
from contextlib import ExitStack
import json
import os
import sys
import time

from PIL import Image, ImageChops
from PIL.PngImagePlugin import PngInfo

from .geometry import circle_cut_svg, heart_cut_points
from .imaging import transform_image
from .publication import (check_pending_publication, format_cleanup_warning, publish_generation,
                          sha256_file, stage_beside, validate_publication_destinations)
from .settings import __version__, ProcessingSettings, DEFAULT_MAX_PIXELS
from .contracts import (artifact_paths, artifact_settings, guard_unmanifested_output, preflight_source,
                        protect_source, runtime_identity, snapshot_source, source_relpath)
from .workflow import (WorkflowOptions, mask_record, appearance_record,
                       finish_preview, render_operations, intended_operations, digest, PALETTE)
from .proof import write_proof
from .vector import render_centerline_svg
from .personalization import render_text_stamp
from .qr import render_qr_stamp


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
    source_snapshot=None,
):
    """Construct a versioned job manifest dictionary."""
    if source_snapshot is not None:
        source_sha = source_snapshot.sha256
        src_size, src_mode = source_snapshot.original_size, source_snapshot.mode
    else:
        source_sha = sha256_file(source_path) if os.path.exists(source_path) else None
        src_size, src_mode = [0, 0], "unknown"
        try:
            with Image.open(source_path) as src:
                src_size, src_mode = list(src.size), src.mode
        except OSError:
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
            "runtime": runtime_identity(),
        },
        "source": {
            "filename": os.path.basename(source_path),
            "relpath": source_relpath(source_path, manifest_path or output_path),
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


def _combine_masks(primary, additions):
    """Review/occupancy union on the original canvas, preserving shape alpha."""
    result = primary.convert('RGBA')
    for addition in additions:
        with addition.convert('L') as gray:
            with result.convert('L') as existing:
                combined = ImageChops.darker(existing, gray)
            result.paste(combined.convert('RGB'), (0, 0))
            combined.close()
    if primary.mode == 'RGBA':
        result.putalpha(primary.getchannel('A'))
    return result


def _render_images(resources, source, settings, workflow, render_settings, *, width_in, height_in, max_pixels, max_memory):
    """Render the primary mask, tone layers and personalization marks.

    Each mark is placed against everything drawn before it. Returns (images, occupancy,
    mark_records); `occupancy` is the union used for review, trim and finish previews.
    """
    limits = dict(width_in=width_in, height_in=height_in, workflow=workflow, max_pixels=max_pixels, max_memory=max_memory)
    full_image = transform_image(source, render_settings, **limits)
    resources.callback(full_image.close)
    images = {'primary': full_image}
    if settings.tone_layers:
        boundaries = [round(256*i/settings.tone_layers) for i in range(settings.tone_layers+1)]
        for i in range(1, settings.tone_layers+1):
            layer = transform_image(source, replace(settings, no_border=True, render_mode='silhouette', silhouette_threshold=128),
                                    tone_band=(boundaries[i-1], boundaries[i]), **limits)
            resources.callback(layer.close)
            images[f'tone_layer_{i}'] = layer
    occupancy = _combine_masks(full_image, [im for role, im in images.items() if role != 'primary'])
    resources.callback(occupancy.close)
    marks = []
    if settings.stamp_text is not None:
        marks.append(('stamp', lambda image: render_text_stamp(image, settings.stamp_text,
            position=settings.stamp_position, size_px=settings.stamp_size_px, margin_px=settings.stamp_margin_px)))
    if settings.qr_text is not None:
        marks.append(('qr', lambda image: render_qr_stamp(image, settings.qr_text,
            position=settings.qr_position, module_px=settings.qr_module_px, margin_px=settings.qr_margin_px)))
    mark_records = {}
    for role, render in marks:
        mark, mark_records[role] = render(occupancy)
        resources.callback(mark.close)
        images[role] = mark
        occupancy = _combine_masks(occupancy, [mark])
        resources.callback(occupancy.close)
    return images, occupancy, mark_records


def _crop_to_shared_bounds(resources, images, occupancy, mark_records, trim):
    """Bounds and canvas offset shared by every standalone mask; crops `images` in place when trimming.

    Pixel placement is decided before any personalization is added.
    """
    mask = mask_record(occupancy)
    bounds = mask['bounds_px']
    if 'qr' in mark_records:
        # White QR modules and the quiet zone are protected layout, even
        # though they are not burns. Keep them inside the shared crop.
        qx0, qy0, qx1, qy1 = mark_records['qr']['bounds_px']
        bounds = [min(bounds[0], qx0), min(bounds[1], qy0),
                  max(bounds[2], qx1), max(bounds[3], qy1)]
    offset = bounds[:2] if trim and bounds else [0, 0]
    if trim:
        for role, image in list(images.items()):
            cropped = image.crop(bounds) if bounds else Image.new('1', (1, 1), 1)
            resources.callback(cropped.close)
            images[role] = cropped
    return mask, bounds, offset


def _stage_artifacts(staged_pairs, paths, images, settings, *, full_image, source_label):
    """Stage every PNG plus the optional cut and linework SVGs; returns their SHA-256 by role."""
    hashes = {}
    for role, image in images.items():
        staged = stage_png(paths[role], image)
        staged_pairs.append((paths[role], staged))
        hashes[role] = sha256_file(staged)
    if settings.svg_cut:
        staged = stage_text(paths['cut'], render_svg_document(full_image, settings.circle_cut, settings.heart_cut))
        staged_pairs.append((paths['cut'], staged))
        hashes['cut'] = sha256_file(staged)
    if settings.svg_linework:
        staged = stage_text(paths['linework'], render_centerline_svg(images['primary'], source_label=source_label))
        staged_pairs.append((paths['linework'], staged))
        hashes['linework'] = sha256_file(staged)
    return hashes


def _stage_workflow(resources, staged_pairs, paths, hashes, *, settings, workflow, snapshot, geometry, recipe_dict,
                    full_image, images, occupancy, mark_records, mask, bounds, offset):
    """Build the revision-bound workflow record and stage the operations SVG, preview, proof and record."""
    identity = runtime_identity()
    appearance = appearance_record(workflow) if workflow.preview_finish or workflow.proof_sheet else None
    record = {
        'schema_version': '1.0', 'tool_version': __version__, 'source_sha256': snapshot.sha256,
        'engine_identity': identity,
        'runtime': dict(identity['libraries']),
        'recipe_sha256': digest(recipe_dict), 'engraving_sha256': hashes['primary'],
        'mask': mask, 'primary_mask': mask_record(full_image), 'geometry': geometry, 'appearance': appearance,
        'appearance_sha256': digest(appearance) if appearance else None,
        'palette': PALETTE if workflow.svg else None,
        'intended_order': intended_operations(workflow, mask, cut=settings.svg_cut or (workflow.svg and (settings.circle_cut or settings.heart_cut))),
        'import_status': 'unverified in Glowforge app',
        'trim': {'enabled': workflow.trim, 'offset_px': offset, 'bounds_px': bounds,
                 'standalone_png_loses_placement': workflow.trim},
        'artifact_registration': {role: {'canvas_px': list(full_image.size), 'offset_px': offset,
                                        'size_px': list(image.size)} for role, image in images.items()},
        'review_includes': list(images),
        'separate_engraving_sidecars': [role for role in images if role != 'primary'],
        'customer_approved': False,
    }
    preview = finish_preview(occupancy, workflow) if appearance else None
    if preview is not None:
        resources.callback(preview.close)
        record['appearance']['pixels_sha256'] = hashlib.sha256(preview.tobytes()).hexdigest()
        record['appearance_sha256'] = digest(record['appearance'])
    if workflow.svg:
        document = render_operations(full_image, workflow, geometry, circle_cut=settings.circle_cut, heart_cut=settings.heart_cut)
        staged = stage_text(paths['operations'], document)
        staged_pairs.append((paths['operations'], staged))
        record['operations_sha256'] = sha256_file(staged)
    if 'cut' in hashes:
        record['operations_sha256'] = hashes['cut']
    if 'linework' in hashes:
        record['linework_sha256'] = hashes['linework']
    if settings.tone_layers:
        record['tone_layers'] = [{'index': i, 'count': settings.tone_layers, 'sha256': hashes[f'tone_layer_{i}']}
                                 for i in range(1, settings.tone_layers+1)]
    for role, metadata in mark_records.items():
        record[role] = {**metadata, 'sha256': hashes[role]}
    record['revision'] = digest(record)
    if appearance:
        info = PngInfo()
        info.add_text('Description', appearance['label'])
        info.add_text('Revision', record['revision'])
        staged_pairs.append((paths['finish'], stage_png(paths['finish'], preview, pnginfo=info)))
    if workflow.proof_sheet:
        staged_pairs.append((paths['proof'], stage_beside(paths['proof'], lambda p: write_proof(
            p, snapshot.path, preview, record, settings.material, settings.material_thickness_in, workflow))))
    staged_pairs.append((paths['workflow'], stage_text(paths['workflow'], json.dumps(record, indent=2))))
    return record


def _stage_manifest(staged_pairs, paths, hashes, *, input_path, output_path, recipe_dict, settings, workflow,
                    snapshot, record, images, full_image, offset, prompt, model):
    manifest_data = build_manifest(input_path, output_path, images['primary'], recipe_dict,
        svg_path=paths.get('cut'), linework_path=paths.get('linework'), output_sha256=hashes['primary'],
        svg_sha256=hashes.get('cut'), linework_sha256=hashes.get('linework'),
        layer_paths={paths[f'tone_layer_{i}']: hashes[f'tone_layer_{i}'] for i in range(1, settings.tone_layers+1)},
        stamp_path=paths.get('stamp'), stamp_sha256=hashes.get('stamp'),
        qr_path=paths.get('qr'), qr_sha256=hashes.get('qr'), prompt=prompt, model=model,
        manifest_path=paths['manifest'], source_snapshot=snapshot)
    if workflow.active:
        manifest_data['workflow'] = record
    manifest_data['registration'] = {'canvas_px': list(full_image.size), 'offset_px': offset}
    for destination, staged in staged_pairs:
        manifest_data['outputs'].setdefault(os.path.basename(destination), {
            'format': os.path.splitext(destination)[1][1:], 'sha256': sha256_file(staged)})
    staged_pairs.append((paths['manifest'], stage_text(paths['manifest'], json.dumps(manifest_data, indent=2))))


def prep_for_glowforge(input_path, output_path, settings=None, *, width_in=None, height_in=None,
                       manifest_path=None, preset_name=None, prompt=None, model=None,
                       quiet=False, workflow=None, machine=None, max_pixels=DEFAULT_MAX_PIXELS,
                       max_memory=None, expected_source_sha256=None, expected_pixels_sha256=None,
                       require_absent=False):
    input_path, output_path = os.fspath(input_path), os.fspath(output_path)
    settings = settings or ProcessingSettings()
    workflow = workflow or WorkflowOptions()
    settings = artifact_settings(settings, workflow)
    paths = artifact_paths(output_path, settings, workflow, manifest_path)
    protect_source(input_path, paths.values())
    validate_publication_destinations(paths.values())
    check_pending_publication(os.path.dirname(os.path.abspath(output_path)))
    absent_paths = tuple(guard_unmanifested_output(paths, manifest_path))
    if require_absent:
        absent_paths += tuple(paths.values())
    # Validate the live header, then repeat against the bytes actually rendered.
    preflight_source(input_path, settings, workflow, width_in=width_in, height_in=height_in,
                     max_pixels=max_pixels, max_memory=max_memory, machine=machine)
    if not quiet:
        print(f"Processing {input_path} (render mode: {settings.render_mode}, fit: {settings.fit_mode})...")
    start_time = time.time()
    staged_pairs, cleanup_warnings = [], []
    record = None
    with ExitStack() as resources:
        snapshot = resources.enter_context(snapshot_source(input_path, expected_source_sha256))
        _, geometry, _ = preflight_source(snapshot.path, settings, workflow, width_in=width_in, height_in=height_in,
                                          max_pixels=max_pixels, max_memory=max_memory, machine=machine)
        source = resources.enter_context(Image.open(snapshot.path))
        render_settings = replace(settings, no_border=settings.no_border or settings.svg_cut or workflow.suppress_border)
        images, occupancy, mark_records = _render_images(
            resources, source, settings, workflow, render_settings,
            width_in=width_in, height_in=height_in, max_pixels=max_pixels, max_memory=max_memory)
        full_image = images['primary']  # the untrimmed canvas; trimming replaces images['primary']
        if expected_pixels_sha256 is not None and hashlib.sha256(full_image.tobytes()).hexdigest() != expected_pixels_sha256:
            raise ValueError('Rendered pixels differ from the selected audition candidate; no generation was published. Regenerate the audition.')
        mask, bounds, offset = _crop_to_shared_bounds(resources, images, occupancy, mark_records, workflow.trim)
        recipe_dict = {**asdict(settings), 'preset': preset_name, 'width_in': width_in, 'height_in': height_in,
                       'no_border': render_settings.no_border}
        if workflow.active:
            recipe_dict.update(workflow=workflow.record(), machine=machine)
        if expected_pixels_sha256 is not None:
            recipe_dict['audition_pixels_sha256'] = expected_pixels_sha256
        try:
            hashes = _stage_artifacts(staged_pairs, paths, images, settings,
                                      full_image=full_image, source_label=os.path.basename(input_path))
            if workflow.active:
                record = _stage_workflow(
                    resources, staged_pairs, paths, hashes, settings=settings, workflow=workflow, snapshot=snapshot,
                    geometry=geometry, recipe_dict=recipe_dict, full_image=full_image, images=images,
                    occupancy=occupancy, mark_records=mark_records, mask=mask, bounds=bounds, offset=offset)
            if settings.manifest:
                _stage_manifest(staged_pairs, paths, hashes, input_path=input_path, output_path=output_path,
                                recipe_dict=recipe_dict, settings=settings, workflow=workflow, snapshot=snapshot,
                                record=record, images=images, full_image=full_image, offset=offset,
                                prompt=prompt, model=model)
            # Revalidate the live source and destination aliases just before publication.
            snapshot.require_unchanged(input_path)
            protect_source(input_path, paths.values())
            cleanup_warnings = publish_generation(staged_pairs, must_be_absent=absent_paths) or []
        except BaseException:
            for _, staged in staged_pairs:
                if os.path.lexists(staged):
                    try:
                        os.unlink(staged)
                    except OSError:
                        pass
            raise
    elapsed = round(time.time() - start_time, 2)
    if not quiet:
        print(f'Complete. Saved {len(paths)} artifact(s) in {elapsed} seconds.')
        for warning in cleanup_warnings:
            print(format_cleanup_warning(warning), file=sys.stderr)
    return {'output_path': output_path, 'svg_path': paths.get('cut'), 'linework_path': paths.get('linework'),
            'layer_paths': [paths[f'tone_layer_{i}'] for i in range(1, settings.tone_layers+1)],
            'stamp_path': paths.get('stamp'), 'qr_path': paths.get('qr'), 'manifest_path': paths.get('manifest'),
            'duration_seconds': elapsed, 'cleanup_warnings': cleanup_warnings,
            'artifacts': {role: path for role, path in paths.items() if role not in ('primary', 'cut', 'manifest')},
            'workflow_summary': record}
