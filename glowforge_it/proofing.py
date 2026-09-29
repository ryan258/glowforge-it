"""Mode-agnostic visual proofing and preset audition.

Audition artifacts are review aids, not machine artwork.  The renderer produces
one contact sheet from the same full-resolution transform used by production
jobs and a JSON record containing each candidate's resolved recipe and burn-mask
metrics.  It deliberately does not emit SVG operations, machine settings, or
material-result claims.
"""

import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from importlib.metadata import version

from PIL import Image, ImageDraw, ImageFont

from .geometry import resolve_oriented_geometry
from .imaging import transform_image
from .planning import BatchResult, DestinationNamespace, JobOutcome, estimate_image_memory
from .publication import publish_generation, sha256_file, stage_beside
from .settings import DEFAULT_MAX_PIXELS, ProcessingSettings, ValidationError, __version__, validate_limits
from .workflow import WorkflowOptions, burn_mask


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

    @property
    def destinations(self):
        return (self.sheet_path, self.metadata_path)


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
        if settings.svg_cut or settings.manifest:
            raise ValidationError(
                f"Audition candidate '{name}' cannot enable --svg-cut or --manifest."
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
):
    """Resolve source and proof destinations before rendering any candidate."""
    namespace, errors = DestinationNamespace.open(
        input_paths, os.path.abspath(output_dir), existing, dry_run)
    if namespace is None:
        return [], errors

    jobs = []
    for input_path, source in namespace.sources:
        try:
            _, _, target_w, target_h, _ = resolve_oriented_geometry(
                source,
                width_in=width_in,
                height_in=height_in,
                max_pixels=max_pixels,
                machine=machine,
            )
            estimated_memory = estimate_image_memory(
                source, width_in=width_in, height_in=height_in, max_pixels=max_pixels
            )
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

        jobs.append(
            AuditionJob(
                input_path=source,
                sheet_path=sheet_path,
                metadata_path=metadata_path,
                output_size=(target_w, target_h),
                estimated_memory_bytes=estimated_memory,
                is_skipped=reusable,
                skip_reason="existing audition output complete" if reusable else None,
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


def render_audition_sheet(
    source_path,
    candidates,
    *,
    width_in=None,
    height_in=None,
    workflow=None,
):
    """Render a contact sheet and metadata from full-resolution candidates.

    ``candidates`` is an iterable of ``(preset_name, ProcessingSettings)``.
    Candidate transforms are full-resolution; only the review tiles are resized.
    """
    workflow = workflow or WorkflowOptions()
    names = _candidate_names(candidates)
    rendered = []
    source_sha256 = sha256_file(source_path)

    with Image.open(source_path) as source:
        source_size = list(source.size)
        source_mode = source.mode
        for name, settings in candidates:
            processed = transform_image(
                source,
                settings,
                width_in=width_in,
                height_in=height_in,
                workflow=workflow,
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

    font = ImageFont.load_default()
    columns = min(2, len(rendered))
    rows = math.ceil(len(rendered) / columns)
    tile_w = max(display.width for _, display in rendered) + 2 * AUDITION_MARGIN_PX
    tile_h = max(display.height for _, display in rendered) + AUDITION_LABEL_HEIGHT_PX + 2 * AUDITION_MARGIN_PX
    sheet = Image.new(
        "RGB",
        (
            columns * tile_w + (columns + 1) * AUDITION_MARGIN_PX,
            AUDITION_HEADER_HEIGHT_PX + rows * tile_h + (rows + 1) * AUDITION_MARGIN_PX,
        ),
        "#e9e9e9",
    )
    draw = ImageDraw.Draw(sheet)
    header = (
        f"Audition: {os.path.basename(source_path)} | 300 DPI proof | "
        "display preview only; candidate PNGs are not emitted"
    )
    draw.text((AUDITION_MARGIN_PX, AUDITION_MARGIN_PX), header, fill="black", font=font)

    for index, (record, display) in enumerate(rendered):
        row, column = divmod(index, columns)
        left = AUDITION_MARGIN_PX + column * tile_w
        top = AUDITION_HEADER_HEIGHT_PX + AUDITION_MARGIN_PX + row * tile_h
        tile = Image.new("RGB", (tile_w - 2 * AUDITION_MARGIN_PX, tile_h - AUDITION_LABEL_HEIGHT_PX - 2 * AUDITION_MARGIN_PX), "white")
        offset = ((tile.width - display.width) // 2, (tile.height - display.height) // 2)
        tile.paste(display, offset)
        sheet.paste(tile, (left + AUDITION_MARGIN_PX, top + AUDITION_MARGIN_PX))
        physical_w, physical_h = record["output"]["physical_size_in"]
        coverage = record["burn"]["coverage"] * 100
        label = (
            f"{record['preset']} | {record['output']['size_px'][0]}x{record['output']['size_px'][1]} px | "
            f"{physical_w:g}x{physical_h:g} in\n"
            f"burn coverage {coverage:.1f}% | binary mask"
        )
        draw.multiline_text(
            (left + AUDITION_MARGIN_PX, top + tile.height + AUDITION_MARGIN_PX + 4),
            label,
            fill="black",
            font=font,
            spacing=3,
        )
        display.close()

    metadata = {
        "schema_version": AUDITION_SCHEMA_VERSION,
        "tool": {
            "name": "glowforge-it",
            "version": __version__,
            "runtime": {name: version(name) for name in ("numpy", "pillow")},
        },
        "source": {
            "filename": os.path.basename(source_path),
            "sha256": source_sha256,
            "original_size": source_size,
            "mode": source_mode,
        },
        "audition": {
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
        if not quiet and not json_output:
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
        dry_run=dry_run,
    )
    if errors:
        if not quiet and not json_output:
            for message in errors:
                print(f"Error: {message}", file=sys.stderr)
        return finish([], errors, 1)

    def outcome(job, status, error=None):
        return JobOutcome(
            input_path=job.input_path,
            output_path=job.sheet_path,
            manifest_path=job.metadata_path,
            status=status,
            error_category='publication_error' if isinstance(error, OSError) else 'transform_error' if error else None,
            error_message=str(error) if error else None,
            output_size=job.output_size,
            estimated_memory_bytes=job.estimated_memory_bytes,
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
                workflow=workflow,
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
            staged_metadata = stage_beside(
                job.metadata_path,
                lambda path: _write_json(path, metadata),
            )
            staged.append((job.metadata_path, staged_metadata))
            publish_generation(staged)
            outcomes.append(outcome(job, "written"))
        except Exception as exc:
            for _, temporary in staged:
                if os.path.lexists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError:
                        pass
            outcomes.append(outcome(job, "failed", exc))
            if not quiet and not json_output:
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
