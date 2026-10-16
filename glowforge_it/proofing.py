"""Mode-agnostic visual proofing and preset audition.

Audition artifacts are review aids, not machine artwork.  The renderer produces
one contact sheet from the same full-resolution transform used by production
jobs and a JSON record containing each candidate's resolved recipe and burn-mask
metrics.  It deliberately does not emit SVG operations, machine settings, or
material-result claims.
"""

import json
import hashlib
import math
import os
import sys
import time
from dataclasses import asdict, dataclass

from PIL import Image, ImageDraw, ImageFont

from .geometry import resolve_oriented_geometry
from .imaging import transform_image
from .planning import BatchResult, DestinationNamespace, JobOutcome
from .publication import publish_generation, sha256_file, stage_beside
from .settings import DEFAULT_MAX_PIXELS, ProcessingSettings, ValidationError, __version__, validate_limits
from .workflow import WorkflowOptions, burn_mask, PROFILE_VERSION
from .contracts import snapshot_source, working_memory, runtime_identity


AUDITION_SCHEMA_VERSION = "1.0"
AUDITION_TILE_MAX_PX = (480, 360)
AUDITION_MARGIN_PX = 24
AUDITION_LABEL_HEIGHT_PX = 64
AUDITION_HEADER_HEIGHT_PX = 72


@dataclass(frozen=True)
class AuditionJob:
    """One source and the proof artifacts planned for it."""

    input_path: str
    sheet_path: str
    metadata_path: str
    output_size: tuple
    estimated_memory_bytes: int = 0
    is_skipped: bool = False
    skip_reason: str = None
    source_sha256: str = None

    @property
    def destinations(self):
        return (self.sheet_path, self.metadata_path)


@dataclass(frozen=True)
class AuditionSelection:
    """A checked recipe and exact render identity from a published audition."""

    name: str
    source_path: str
    source_sha256: str
    settings: ProcessingSettings
    workflow: WorkflowOptions
    width_in: float
    height_in: float
    pixels_sha256: str
    record_path: str
    sheet_path: str


def load_audition_candidate(record_path, candidate, *, source_path=None,
                            max_pixels=DEFAULT_MAX_PIXELS, max_memory=None, machine=None):
    """Read a numbered/named candidate without mutating its audition record."""
    try:
        record_path = os.path.abspath(os.fsdecode(record_path))
        directory = os.path.realpath(os.path.dirname(record_path))
        with open(record_path, encoding='utf-8') as handle:
            data = json.load(handle)
        if data['schema_version'] != AUDITION_SCHEMA_VERSION:
            raise ValidationError('Unsupported audition schema version.')
        audition = data['audition']
        if audition.get('export_version') != 1:
            raise ValidationError('This audition lacks exact export data; regenerate the audition before selecting a candidate.')
        if data['tool']['identity'] != runtime_identity():
            raise ValidationError('Audition engine/runtime differs; regenerate the audition with the current engine.')
        entries = data['candidates']
        recipe_keys = set(asdict(ProcessingSettings()))
        if any(set(entry['recipe']) != recipe_keys for entry in entries):
            raise ValidationError('Audition candidates must contain complete resolved recipes.')
        candidates = [(entry['preset'], ProcessingSettings(**entry['recipe'])) for entry in entries]
        workflow_values = audition['workflow']
        if workflow_values is not None:
            workflow_values = dict(workflow_values)
            if workflow_values.pop('version') != PROFILE_VERSION:
                raise ValidationError('Unsupported audition workflow version.')
        workflow = WorkflowOptions(**(workflow_values or {}))
        dimensions = audition['dimensions']
        if set(dimensions) != {'width_in', 'height_in'}:
            raise ValidationError('Audition must record the original width and height arguments.')
        width_in, height_in = dimensions['width_in'], dimensions['height_in']
        _validate_audition_inputs(candidates, workflow, width_in=width_in, height_in=height_in,
                                 max_pixels=max_pixels, max_memory=max_memory, machine=machine)
        names = _candidate_names(candidates)
        if audition['candidate_presets'] != names:
            raise ValidationError('Audition candidate order is inconsistent.')
        selector = str(candidate)
        if selector in names:
            index = names.index(selector)
        elif selector.isascii() and selector.isdecimal() and 1 <= int(selector) <= len(names):
            index = int(selector) - 1
        else:
            choices = ', '.join(f'{i + 1}: {name}' for i, name in enumerate(names))
            raise ValidationError(f'Unknown audition candidate {selector!r}. Choose {choices}.')

        def valid_hash(value):
            return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)

        outputs = data['outputs']
        if not isinstance(outputs, dict) or len(outputs) != 1:
            raise ValidationError('Audition must record exactly one contact sheet.')
        sheet_name, sheet_info = next(iter(outputs.items()))
        if (not sheet_name or sheet_name in ('.', '..') or '/' in sheet_name
                or '\\' in sheet_name or '\x00' in sheet_name):
            raise ValidationError('Invalid audition contact-sheet filename.')
        sheet_path = os.path.join(directory, sheet_name)
        if os.path.commonpath((directory, os.path.realpath(sheet_path))) != os.path.realpath(directory):
            raise ValidationError('Audition contact sheet resolves outside its record directory.')
        if not valid_hash(sheet_info['sha256']) or sha256_file(sheet_path) != sheet_info['sha256']:
            raise ValidationError('Audition contact-sheet hash mismatch; regenerate the audition.')
        source = data['source']
        if source_path is None:
            relpath = source['relpath']
            if not isinstance(relpath, str) or not relpath or '\x00' in relpath or os.path.isabs(relpath):
                raise ValidationError('Audition source relpath must be a non-empty relative path.')
            source_path = os.path.join(directory, relpath)
        source_path = os.path.abspath(os.fsdecode(source_path))
        if not valid_hash(source['sha256']) or sha256_file(source_path) != source['sha256']:
            raise ValidationError('Audition source hash mismatch; use the original source or regenerate the audition.')
        output = entries[index]['output']
        if not valid_hash(output['pixels_sha256']):
            raise ValidationError('Audition candidate has no valid pixel hash.')
        _, _, width, height, _ = resolve_oriented_geometry(source_path, width_in, height_in, max_pixels, machine)
        if output['size_px'] != [width, height] or output['dpi'] != 300:
            raise ValidationError('Audition candidate dimensions do not match the recorded render arguments.')
        return AuditionSelection(names[index], source_path, source['sha256'], candidates[index][1],
                                 workflow, width_in, height_in, output['pixels_sha256'], record_path, sheet_path)
    except ValidationError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValidationError(f'Cannot load audition candidate: {exc}') from exc


def _candidate_names(candidates):
    names = [name for name, _ in candidates]
    if not names:
        raise ValidationError("Audition requires at least one candidate preset.")
    if any(not isinstance(name, str) or not name for name in names):
        raise ValidationError("Audition candidate names must be non-empty strings.")
    if len(set(names)) != len(names):
        raise ValidationError("Audition candidate presets must be unique.")
    return names


def _validate_audition_inputs(
    candidates,
    workflow,
    *,
    width_in,
    height_in,
    max_pixels,
    max_memory,
    machine,
):
    """Apply direct-API validation shared by CLI and callers."""
    _candidate_names(candidates)
    if len(candidates) > 16:
        raise ValidationError('Audition is limited to 16 candidates per source.')
    if not isinstance(workflow, WorkflowOptions):
        raise ValidationError("workflow must be a WorkflowOptions instance.")
    validate_limits(width_in, height_in, max_pixels, max_memory, machine)
    if workflow.svg_operations or workflow.score_marks or workflow.preview_finish or workflow.proof_sheet:
        raise ValidationError(
            "Audition produces a mode-agnostic proof; SVG operations, finish previews, "
            "and approval proofs belong to a selected production job."
        )
    if workflow.jig is not None or workflow.trim:
        raise ValidationError(
            "Audition cannot combine with jig or trim options."
        )
    for name, settings in candidates:
        if not isinstance(settings, ProcessingSettings):
            raise ValidationError(f"Audition settings for '{name}' are invalid.")
        settings.validate()
        if settings.svg_cut or settings.manifest or settings.svg_linework or settings.tone_layers or settings.stamp_text is not None or settings.qr_text is not None:
            raise ValidationError(
                f"Audition candidate '{name}' cannot enable production sidecars (--svg-cut, --manifest, --svg-linework, --tone-layers, --stamp-text, --qr-text)."
            )
        workflow.validate(invert=settings.invert, svg_cut=False, machine=machine)


def plan_audition(
    input_paths,
    output_dir,
    *,
    width_in=None,
    height_in=None,
    max_pixels=DEFAULT_MAX_PIXELS,
    max_memory=None,
    machine=None,
    existing="overwrite",
    dry_run=False,
    candidates=None,
    workflow=None,
):
    """Resolve source and proof destinations before rendering any candidate."""
    namespace, errors = DestinationNamespace.open(
        input_paths, os.path.abspath(output_dir), existing, dry_run)
    if namespace is None:
        return [], errors

    jobs = []
    for input_path, source in namespace.sources:
        try:
            source_sha256 = sha256_file(source)
            orig_w, orig_h, target_w, target_h, _ = resolve_oriented_geometry(
                source,
                width_in=width_in,
                height_in=height_in,
                max_pixels=max_pixels,
                machine=machine,
            )
            candidate_settings = [settings for _, settings in candidates] if candidates else [ProcessingSettings()]
            estimated_memory = max(working_memory(orig_w, orig_h, target_w, target_h, settings, workflow,
                                                 max_pixels=max_pixels) for settings in candidate_settings)
            names = [name for name, _ in candidates] if candidates else ['default']
            sheet_layout = _audition_layout(source, names, (target_w, target_h))
            estimated_memory += _sheet_memory(len(candidate_settings), sheet_layout)

        except Exception as exc:
            errors.append(f"{source}: {exc}")
            continue

        if max_memory is not None and estimated_memory > max_memory:
            errors.append(
                f"{source}: estimated memory ({estimated_memory / 1024 / 1024:.1f} MB) "
                f"exceeds budget ({max_memory / 1024 / 1024:.1f} MB). "
                "Reduce target dimensions or increase --max-memory."
            )
            continue

        target_dir, error = namespace.target_dir(input_path, source)
        if error:
            errors.append(error)
            continue
        stem = os.path.splitext(os.path.basename(source))[0]
        sheet_path = os.path.join(target_dir, f"{stem}_audition.png")
        metadata_path = os.path.join(target_dir, f"{stem}_audition.json")
        error, reusable = namespace.claim(source, (sheet_path, metadata_path))
        if error:
            errors.append(error)
            continue

        if reusable and candidates is not None:
            try:
                with open(metadata_path, encoding='utf-8') as handle:
                    previous = json.load(handle)
                expected = [(name, asdict(settings)) for name, settings in candidates]
                actual = [(entry['preset'], entry['recipe']) for entry in previous['candidates']]
                same = (previous['schema_version'] == AUDITION_SCHEMA_VERSION
                        and previous['source']['sha256'] == source_sha256
                        and previous['tool']['identity'] == runtime_identity()
                        and previous['audition']['workflow'] == (workflow.record() if workflow and workflow.active else None)
                        and expected == actual
                        and all(entry['output']['size_px'] == [target_w, target_h] for entry in previous['candidates'])
                        and previous['outputs'][os.path.basename(sheet_path)]['sha256'] == sha256_file(sheet_path))
                if not same:
                    raise ValueError('source, recipe, runtime or proof differs')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append(f'{source}: cannot reuse existing audition: {exc}')
                continue

        jobs.append(
            AuditionJob(
                input_path=source,
                sheet_path=sheet_path,
                metadata_path=metadata_path,
                output_size=(target_w, target_h),
                estimated_memory_bytes=estimated_memory,
                is_skipped=reusable,
                skip_reason="existing audition output complete" if reusable else None,
                source_sha256=source_sha256,
            )
        )

    errors.extend(namespace.conflicts())
    return jobs, errors


def _fit_size(source_size, maximum):
    source_w, source_h = source_size
    max_w, max_h = maximum
    scale = min(max_w / max(1, source_w), max_h / max(1, source_h))
    return max(1, round(source_w * scale)), max(1, round(source_h * scale))


def _composite_for_display(image):
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, "white")
        return Image.alpha_composite(background, image.convert("RGBA")).convert("RGB")
    return image.convert("L").convert("RGB")


def _wrap_sheet_text(text, font, width):
    """Wrap measured text, including long filenames and unbroken candidate names."""
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for character in paragraph:
            line += character
            if font.getlength(line) > width:
                space = line.rfind(' ', 0, len(line) - 1)
                if space > 0:
                    lines.append(line[:space])
                    line = line[space + 1:]
                else:
                    lines.append(line[:-1])
                    line = character
        lines.append(line)
    return '\n'.join(lines)


def _audition_label(name, size, coverage=1.0):
    width, height = size
    return (f'{name}\n{width}x{height} px | {width/300:g}x{height/300:g} in\n'
            f'burn coverage {coverage*100:.1f}% | binary mask')


def _audition_layout(source_path, names, size):
    """Resolve text and canvas bounds before allocating full-resolution candidates."""
    font = ImageFont.load_default()
    margin = AUDITION_MARGIN_PX
    content_w, image_h = AUDITION_TILE_MAX_PX
    columns = min(2, len(names))
    rows = math.ceil(len(names) / columns)
    tile_w = content_w + 2 * margin
    width = columns * tile_w + (columns + 1) * margin
    header = _wrap_sheet_text(
        f'Audition: {os.path.basename(source_path)} | 300 DPI proof | '
        'display preview only; candidate PNGs are not emitted', font, width - 2 * margin)
    probe = ImageDraw.Draw(Image.new('1', (1, 1)))

    def height(text):
        return probe.multiline_textbbox((0, 0), text, font=font, spacing=3)[3] + 4

    header_h = max(AUDITION_HEADER_HEIGHT_PX, height(header) + 2 * margin)
    labels = [_wrap_sheet_text(_audition_label(f'{index + 1}. {name}', size), font, content_w)
              for index, name in enumerate(names)]
    label_h = max(AUDITION_LABEL_HEIGHT_PX, *(height(label) for label in labels))
    tile_h = image_h + label_h + 2 * margin
    return {'size': (width, header_h + rows * tile_h + (rows + 1) * margin),
            'font': font, 'header': header, 'header_h': header_h,
            'columns': columns, 'tile_w': tile_w, 'tile_h': tile_h,
            'content_w': content_w, 'image_h': image_h}


def _sheet_memory(count, layout):
    """Retained RGB tiles and two sheets at the measured, wrapped layout size."""
    width, height = layout['size']
    tile_w, tile_h = AUDITION_TILE_MAX_PX
    return count * tile_w * tile_h * 3 + 2 * width * height * 3


def render_audition_sheet(
    source_path,
    candidates,
    *,
    width_in=None,
    height_in=None,
    workflow=None,
    max_pixels=DEFAULT_MAX_PIXELS,
    max_memory=None,
    expected_source_sha256=None,
):
    """Render a contact sheet and metadata from full-resolution candidates.

    ``candidates`` is an iterable of ``(preset_name, ProcessingSettings)``.
    Candidate transforms are full-resolution; only the review tiles are resized.
    """
    workflow = workflow or WorkflowOptions()
    candidates = list(candidates)
    _validate_audition_inputs(candidates, workflow, width_in=width_in, height_in=height_in,
                             max_pixels=max_pixels, max_memory=max_memory, machine=None)
    names = _candidate_names(candidates)
    rendered = []
    with snapshot_source(source_path, expected_source_sha256) as snapshot, Image.open(snapshot.path) as source:
        ow, oh, tw, th, _ = resolve_oriented_geometry(snapshot.path, width_in, height_in, max_pixels)
        sheet_layout = _audition_layout(source_path, names, (tw, th))
        estimated = max(working_memory(ow, oh, tw, th, settings, workflow, max_pixels=max_pixels)
                        for _, settings in candidates) + _sheet_memory(len(candidates), sheet_layout)
        if max_memory is not None and estimated > max_memory:
            raise ValidationError('Audition estimated memory exceeds budget, including the contact sheet.')
        source_sha256 = snapshot.sha256
        source_size = list(source.size)
        source_mode = source.mode
        for name, settings in candidates:
            processed = transform_image(
                source,
                settings,
                width_in=width_in,
                height_in=height_in,
                workflow=workflow, max_pixels=max_pixels, max_memory=max_memory,
            )
            try:
                mask = burn_mask(processed)
                histogram = mask.histogram()
                burn_pixels = histogram[255] if len(histogram) > 255 else 0
                # Coverage of the usable shape, not of the transparent canvas around a circle/heart.
                total_pixels = mask.width * mask.height
                if processed.mode == "RGBA":
                    total_pixels = sum(processed.getchannel("A").histogram()[1:])
                total_pixels = max(1, total_pixels)
                bounds = mask.getbbox()
                output_size = list(processed.size)
                tile_size = _fit_size(processed.size, AUDITION_TILE_MAX_PX)
                display = _composite_for_display(processed)
                display = display.resize(tile_size, Image.Resampling.LANCZOS)
                candidate_record = {
                    "preset": name,
                    "recipe": asdict(settings),
                    "output": {
                        "size_px": output_size,
                        "pixels_sha256": hashlib.sha256(processed.tobytes()).hexdigest(),
                        "physical_size_in": [
                            round(output_size[0] / 300.0, 4),
                            round(output_size[1] / 300.0, 4),
                        ],
                        "dpi": 300,
                    },
                    "burn": {
                        "coverage": round(burn_pixels / total_pixels, 8),
                        "bounds_px": list(bounds) if bounds else None,
                        "no_engrave": bounds is None,
                    },
                    "display": {
                        "tile_size_px": list(tile_size),
                        "resampling": "LANCZOS",
                        "machine_artifact": False,
                    },
                }
                rendered.append((candidate_record, display))
            finally:
                processed.close()
        snapshot.require_unchanged(source_path)

    font = sheet_layout['font']
    columns = sheet_layout['columns']
    tile_w, tile_h = sheet_layout['tile_w'], sheet_layout['tile_h']
    sheet = Image.new('RGB', sheet_layout['size'], '#e9e9e9')
    draw = ImageDraw.Draw(sheet)
    draw.multiline_text((AUDITION_MARGIN_PX, AUDITION_MARGIN_PX), sheet_layout['header'],
                        fill='black', font=font, spacing=3)

    for index, (record, display) in enumerate(rendered):
        row, column = divmod(index, columns)
        left = AUDITION_MARGIN_PX + column * (tile_w + AUDITION_MARGIN_PX)
        top = sheet_layout['header_h'] + AUDITION_MARGIN_PX + row * (tile_h + AUDITION_MARGIN_PX)
        tile = Image.new('RGB', (sheet_layout['content_w'], sheet_layout['image_h']), 'white')
        offset = ((tile.width - display.width) // 2, (tile.height - display.height) // 2)
        tile.paste(display, offset)
        sheet.paste(tile, (left + AUDITION_MARGIN_PX, top + AUDITION_MARGIN_PX))
        label = _wrap_sheet_text(_audition_label(f"{index + 1}. {record['preset']}", record['output']['size_px'],
                                                record['burn']['coverage']), font, sheet_layout['content_w'])
        draw.multiline_text(
            (left + AUDITION_MARGIN_PX, top + tile.height + AUDITION_MARGIN_PX + 4),
            label,
            fill="black",
            font=font,
            spacing=3,
        )
        tile.close()
        display.close()

    metadata = {
        "schema_version": AUDITION_SCHEMA_VERSION,
        "tool": {
            "name": "glowforge-it",
            "version": __version__,
            "identity": runtime_identity(),
            "runtime": runtime_identity()["libraries"],
        },
        "source": {
            "filename": os.path.basename(source_path),
            "sha256": source_sha256,
            "original_size": source_size,
            "mode": source_mode,
        },
        "audition": {
            "export_version": 1,
            "dimensions": {"width_in": width_in, "height_in": height_in},
            "candidate_presets": names,
            "selected_preset": None,
            "workflow": workflow.record() if workflow.active else None,
            "display": {
                "contact_sheet_dpi": 96,
                "machine_artifact": False,
                "note": "Review aid only. Use a selected candidate recipe for a production export.",
            },
        },
        "candidates": [record for record, _ in rendered],
    }
    return sheet, metadata


def _write_json(path, metadata):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


def run_audition(
    input_paths,
    output_dir,
    candidates,
    *,
    width_in=None,
    height_in=None,
    max_pixels=DEFAULT_MAX_PIXELS,
    max_memory=None,
    machine=None,
    existing="overwrite",
    dry_run=False,
    json_output=False,
    quiet=False,
    workflow=None,
):
    """Create one contact-sheet proof and recipe record per source image."""
    start = time.time()
    workflow = workflow or WorkflowOptions()
    candidates = list(candidates)

    def finish(items, errors, code):
        result = BatchResult.from_items(items, errors, code, start, dry_run)
        if json_output:
            print(result.to_json())
        return result

    try:
        _validate_audition_inputs(
            candidates,
            workflow,
            width_in=width_in,
            height_in=height_in,
            max_pixels=max_pixels,
            max_memory=max_memory,
            machine=machine,
        )
    except ValidationError as exc:
        if not json_output:
            print(f"Validation error: {exc}", file=sys.stderr)
        return finish([], [str(exc)], 2)

    jobs, errors = plan_audition(
        input_paths,
        output_dir,
        width_in=width_in,
        height_in=height_in,
        max_pixels=max_pixels,
        max_memory=max_memory,
        machine=machine,
        existing=existing,
        dry_run=dry_run, candidates=candidates, workflow=workflow,
    )
    if errors:
        if not json_output:
            for message in errors:
                print(f"Error: {message}", file=sys.stderr)
        return finish([], errors, 1)

    def outcome(job, status, error=None, cleanup_warnings=None):
        return JobOutcome(
            input_path=job.input_path,
            output_path=job.sheet_path,
            manifest_path=job.metadata_path,
            status=status,
            error_category='publication_error' if isinstance(error, OSError) else 'transform_error' if error else None,
            error_message=str(error) if error else None,
            output_size=job.output_size,
            estimated_memory_bytes=job.estimated_memory_bytes,
            cleanup_warnings=cleanup_warnings or None,
        )

    if dry_run:
        if not quiet and not json_output:
            print(f"Audition plan complete: {len(jobs)} source(s), no proof artifacts written.")
        return finish([outcome(job, "skipped" if job.is_skipped else "planned") for job in jobs], [], 0)

    outcomes = []
    for job in jobs:
        if job.is_skipped:
            outcomes.append(outcome(job, "skipped"))
            continue

        staged = []
        sheet = None
        try:
            sheet, metadata = render_audition_sheet(
                job.input_path,
                candidates,
                width_in=width_in,
                height_in=height_in,
                workflow=workflow, max_pixels=max_pixels, max_memory=max_memory,
                expected_source_sha256=job.source_sha256,
            )
            staged_sheet = stage_beside(
                job.sheet_path,
                lambda path: sheet.save(path, format="PNG", dpi=(96, 96)),
            )
            staged.append((job.sheet_path, staged_sheet))
            metadata["outputs"] = {
                os.path.basename(job.sheet_path): {
                    "format": "png",
                    "sha256": sha256_file(staged_sheet),
                }
            }
            metadata['source']['relpath'] = os.path.relpath(job.input_path, os.path.dirname(job.metadata_path))
            staged_metadata = stage_beside(
                job.metadata_path,
                lambda path: _write_json(path, metadata),
            )
            staged.append((job.metadata_path, staged_metadata))
            if sha256_file(job.input_path) != metadata['source']['sha256']:
                raise ValidationError('Source changed during audition; no proof was published.')
            cleanup = publish_generation(staged) or []
            outcomes.append(outcome(job, "written", cleanup_warnings=cleanup))
            if not quiet and not json_output:
                for warning in cleanup:
                    print(f"Warning: published successfully; retained backup {warning['backup']}: {warning['message']}", file=sys.stderr)
        except Exception as exc:
            for _, temporary in staged:
                if os.path.lexists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
            outcomes.append(outcome(job, "failed", exc))
            if not json_output:
                print(f"Error processing audition for {job.input_path}: {exc}", file=sys.stderr)
        finally:
            if sheet is not None:
                sheet.close()

    failures = sum(item.status == "failed" for item in outcomes)
    if not quiet and not json_output:
        written = sum(item.status == "written" for item in outcomes)
        skipped = sum(item.status == "skipped" for item in outcomes)
        print(f"Audition summary: {written} written, {skipped} skipped, {failures} failed.")
    return finish(outcomes, [], 0 if failures == 0 else 1)
