"""Coordinating a plan and its execution, and reporting the batch outcome.

Parses no command-line arguments. Produces structured BatchResult objects with
backwards-compatible boolean evaluation.
"""

import json
import math
import sys
import time
from dataclasses import asdict, dataclass

from .export import prep_for_glowforge
from .planning import plan_batch
from .settings import (
    DEFAULT_MATERIAL,
    DEFAULT_MATERIAL_THICKNESS_IN,
    DEFAULT_MAX_PIXELS,
    MACHINE_BEDS_IN,
    ProcessingSettings,
    ValidationError,
)


@dataclass(frozen=True)
class JobOutcome:
    """Outcome for a single input item in a batch."""

    input_path: str
    output_path: str
    svg_path: str = None
    manifest_path: str = None
    status: str = 'written'  # 'written', 'skipped', 'failed', 'planned'
    error_category: str = None  # 'planning_error', 'validation_error', 'transform_error', 'publication_error'
    error_message: str = None
    duration_seconds: float = 0.0
    output_size: tuple = None
    estimated_memory_bytes: int = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class BatchResult:
    """Structured result of planning and executing a batch."""

    items: list
    written_count: int
    skipped_count: int
    failed_count: int
    total_planned: int
    exit_code: int
    errors: list
    duration_seconds: float = 0.0
    is_dry_run: bool = False

    def __bool__(self):
        """Preserves backwards compatibility with `if run_batch(...):` boolean callers."""
        return self.exit_code == 0

    def to_dict(self):
        return {
            'success': self.exit_code == 0,
            'exit_code': self.exit_code,
            'is_dry_run': self.is_dry_run,
            'summary': {
                'written': self.written_count,
                'skipped': self.skipped_count,
                'failed': self.failed_count,
                'total_planned': self.total_planned,
            },
            'duration_seconds': self.duration_seconds,
            'errors': self.errors,
            'items': [item.to_dict() if hasattr(item, 'to_dict') else item for item in self.items],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent)


def run_batch(
    input_paths,
    output_dir,
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
    preset_name=None,
    fit_mode='stretch',
    svg_cut=False,
    max_pixels=DEFAULT_MAX_PIXELS,
    machine=None,
    existing='overwrite',
    material=DEFAULT_MATERIAL,
    material_thickness_in=DEFAULT_MATERIAL_THICKNESS_IN,
    dry_run=False,
    manifest=False,
    max_memory=None,
    prompt=None,
    model=None,
    json_output=False,
    quiet=False,
):
    """Plan the complete job, then publish it. Returns a structured BatchResult."""
    start_time = time.time()
    values = {
        'black_thresh': black_thresh,
        'white_thresh': white_thresh,
        'dither_thresh': dither_thresh,
        'clean_solids': clean_solids,
        'clean_solids_black': clean_solids_black,
        'clean_solids_white': clean_solids_white,
        'invert': invert,
        'no_border': no_border,
        'denoise_radius': denoise_radius,
        'contrast': contrast,
        'sharpen_radius': sharpen_radius,
        'sharpen_percent': sharpen_percent,
        'sharpen_threshold': sharpen_threshold,
        'circle_cut': circle_cut,
        'heart_cut': heart_cut,
        'fit_mode': fit_mode,
    }

    # Shared typed validation
    try:
        settings_obj = ProcessingSettings(
            black_threshold=black_thresh,
            white_threshold=white_thresh,
            dither_threshold=dither_thresh,
            clean_solids=clean_solids,
            clean_solids_black=clean_solids_black,
            clean_solids_white=clean_solids_white,
            invert=invert,
            no_border=no_border,
            denoise=denoise_radius,
            contrast=contrast,
            sharpen_radius=sharpen_radius,
            sharpen_percent=sharpen_percent,
            sharpen_threshold=sharpen_threshold,
            circle_cut=circle_cut,
            heart_cut=heart_cut,
            fit_mode=fit_mode,
            svg_cut=svg_cut,
            manifest=manifest,
            material=material,
            material_thickness_in=material_thickness_in,
        )
        settings_obj.validate()
        for name, value in (('width_in', width_in), ('height_in', height_in)):
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
                raise ValidationError(f'{name} must be a finite positive number.')
        for name, value in (('max_pixels', max_pixels), ('max_memory', max_memory)):
            if (value is not None or name == 'max_pixels') and (type(value) is not int or value <= 0):
                raise ValidationError(f'{name} must be a positive integer.')
        if machine is not None and (not isinstance(machine, str) or machine not in MACHINE_BEDS_IN):
            raise ValidationError(f'Unknown machine: {machine!r}.')
    except ValidationError as val_err:
        err_msg = str(val_err)
        if not json_output and not quiet:
            print(f"Validation error: {err_msg}", file=sys.stderr)
        res = BatchResult(
            items=[],
            written_count=0,
            skipped_count=0,
            failed_count=0,
            total_planned=0,
            exit_code=2,
            errors=[err_msg],
            duration_seconds=round(time.time() - start_time, 2),
            is_dry_run=dry_run,
        )
        if json_output:
            print(res.to_json())
        return res

    if not json_output and not quiet:
        mode_note = " (DRY-RUN)" if dry_run else ""
        print(
            f"Starting batch process{mode_note} for {list(input_paths)} "
            f"(material context: {material}, thickness: {material_thickness_in:g} in)."
        )

    jobs, errors = plan_batch(
        input_paths,
        output_dir,
        values,
        preset_name=preset_name,
        width_in=width_in,
        height_in=height_in,
        svg_cut=svg_cut,
        max_pixels=max_pixels,
        machine=machine,
        existing=existing,
        dry_run=dry_run,
        manifest=manifest,
        max_memory=max_memory,
        expected_recipe={
            **values,
            'width_in': width_in,
            'height_in': height_in,
            'no_border': no_border or svg_cut,
            'svg_cut': svg_cut,
            'manifest': manifest,
            'material': material,
            'material_thickness_in': material_thickness_in,
        },
    )
    if errors:
        if not json_output and not quiet:
            for message in errors:
                print(f"Error: {message}", file=sys.stderr)
            print(
                f"Planning failed: {len(errors)} problem(s); no image outputs were published. "
                "(Planning does create the output directory and a temporary probe file inside it.)"
                if not dry_run else f"Planning failed: {len(errors)} problem(s); no outputs planned.",
                file=sys.stderr,
            )
        res = BatchResult(
            items=[],
            written_count=0,
            skipped_count=0,
            failed_count=0,
            total_planned=0,
            exit_code=1,
            errors=errors,
            duration_seconds=round(time.time() - start_time, 2),
            is_dry_run=dry_run,
        )
        if json_output:
            print(res.to_json())
        return res

    if dry_run:
        items = []
        skipped = 0
        for job in jobs:
            status = 'skipped' if job.is_skipped else 'planned'
            if job.is_skipped:
                skipped += 1
            items.append(JobOutcome(
                input_path=job.input_path,
                output_path=job.output_path,
                svg_path=job.svg_path,
                manifest_path=job.manifest_path,
                status=status,
                output_size=job.output_size,
                estimated_memory_bytes=job.estimated_memory_bytes,
            ))
            if not json_output and not quiet:
                status_str = f" [SKIPPED: {job.skip_reason}]" if job.is_skipped else ""
                w, h = job.output_size
                print(f"Plan: {job.input_path} -> {job.output_path}{status_str}; "
                      f"{w} x {h} px ({w / 300:g} x {h / 300:g} in at 300 DPI); "
                      f"estimated working memory {job.estimated_memory_bytes:,} bytes")

        res = BatchResult(
            items=items,
            written_count=0,
            skipped_count=skipped,
            failed_count=0,
            total_planned=len(jobs),
            exit_code=0,
            errors=[],
            duration_seconds=round(time.time() - start_time, 2),
            is_dry_run=True,
        )
        if not json_output and not quiet:
            print(f"Plan preview complete: {len(jobs)} item(s) planned, {skipped} skipped (0 written in dry-run).")
        if json_output:
            print(res.to_json())
        return res

    item_outcomes = []
    written = 0
    skipped = 0
    failures = 0
    for job in jobs:
        if job.is_skipped:
            if not json_output and not quiet:
                print(f"Skipping existing output: {job.output_path}")
            item_outcomes.append(JobOutcome(
                input_path=job.input_path,
                output_path=job.output_path,
                svg_path=job.svg_path,
                manifest_path=job.manifest_path,
                status='skipped',
            ))
            skipped += 1
            continue

        try:
            job_values = job.values if job.values is not None else values
            prep_res = prep_for_glowforge(
                job.input_path,
                job.output_path,
                width_in=width_in,
                height_in=height_in,
                svg_cut=svg_cut,
                manifest=manifest,
                manifest_path=job.manifest_path,
                preset_name=job.preset_name,
                material=material,
                material_thickness_in=material_thickness_in,
                prompt=prompt,
                model=model,
                quiet=(quiet or json_output),
                **job_values,
            )
            item_outcomes.append(JobOutcome(
                input_path=job.input_path,
                output_path=job.output_path,
                svg_path=job.svg_path,
                manifest_path=job.manifest_path,
                status='written',
                duration_seconds=prep_res.get('duration_seconds', 0.0),
            ))
            written += 1
        except Exception as exc:
            if not json_output and not quiet:
                print(f"Error processing {job.input_path}: {exc}", file=sys.stderr)
            cat = 'publication_error' if isinstance(exc, OSError) else 'transform_error'
            item_outcomes.append(JobOutcome(
                input_path=job.input_path,
                output_path=job.output_path,
                svg_path=job.svg_path,
                manifest_path=job.manifest_path,
                status='failed',
                error_category=cat,
                error_message=str(exc),
            ))
            failures += 1

    exit_code = 0 if failures == 0 else 1
    res = BatchResult(
        items=item_outcomes,
        written_count=written,
        skipped_count=skipped,
        failed_count=failures,
        total_planned=len(jobs),
        exit_code=exit_code,
        errors=[],
        duration_seconds=round(time.time() - start_time, 2),
        is_dry_run=False,
    )

    if not json_output and not quiet:
        skip_msg = f", {skipped} skipped" if skipped else ""
        print(f"Batch summary: {written} written{skip_msg}, {failures} failed, {len(jobs)} planned.")
    if json_output:
        print(res.to_json())

    return res


def process_directory(input_dir, output_dir, **kwargs):
    """Compatibility entry point for a single input path."""
    return run_batch([input_dir], output_dir, **kwargs)
