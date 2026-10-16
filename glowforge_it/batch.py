"""Coordinating a plan and its execution, and reporting the batch outcome.

Parses no command-line arguments. Produces structured BatchResult objects.
"""

import sys
import time
from dataclasses import asdict, replace

from .export import prep_for_glowforge
from .contracts import artifact_settings, protect_source, validate_combination
from .planning import BatchResult, JobOutcome, plan_batch
from .proofing import load_audition_candidate
from .workflow import WorkflowOptions
from .settings import (
    DEFAULT_MAX_PIXELS,
    ProcessingSettings,
    ValidationError,
    validate_limits,
)


def _job_paths(job):
    return {**{name: getattr(job, name) for name in
               ('input_path', 'output_path', 'svg_path', 'manifest_path', 'artifacts')},
            'warnings': list(job.warnings) or None}


def run_batch(input_paths, output_dir, settings=None, *, width_in=None, height_in=None,
              max_pixels=DEFAULT_MAX_PIXELS, machine=None, existing='overwrite', dry_run=False,
              max_memory=None, preset_name=None, prompt=None, model=None, json_output=False,
              quiet=False, workflow=None, explicit_keys=frozenset(), expected_source_sha256=None,
              expected_pixels_sha256=None, protected_paths=()):
    settings = settings or ProcessingSettings()
    workflow = workflow or WorkflowOptions()
    start_time = time.time()
    def finish(items, errors, code):
        result = BatchResult.from_items(items, errors, code, start_time, dry_run)
        if json_output:
            print(result.to_json())
        return result

    try:
        settings = artifact_settings(settings, workflow)
        validate_combination(settings, workflow)
        workflow.validate(invert=settings.invert, svg_cut=settings.svg_cut, machine=machine)
        validate_limits(width_in, height_in, max_pixels, max_memory, machine)
    except ValidationError as val_err:
        err_msg = str(val_err)
        if not json_output:
            print(f"Validation error: {err_msg}", file=sys.stderr)
        return finish([], [err_msg], 2)

    values = {key: value for key, value in asdict(settings).items()
              if key not in {'svg_cut', 'svg_linework', 'manifest', 'material', 'material_thickness_in'}}
    jobs, errors = plan_batch(
        input_paths,
        output_dir,
        values,
        preset_name=preset_name,
        width_in=width_in,
        height_in=height_in,
        svg_cut=settings.svg_cut,
        svg_linework=settings.svg_linework,
        max_pixels=max_pixels,
        machine=machine,
        existing=existing,
        dry_run=dry_run,
        manifest=settings.manifest,
        max_memory=max_memory,
        workflow=workflow,
        explicit_keys=explicit_keys,
        expected_provenance={'prompt': prompt, 'model': model},
        expected_recipe={
            **asdict(settings),
            **({"workflow": workflow.record(), "machine": machine} if workflow.active else {}),
            'width_in': width_in, 'height_in': height_in,
            'no_border': settings.no_border or settings.svg_cut or workflow.suppress_border,
            **({'audition_pixels_sha256': expected_pixels_sha256} if expected_pixels_sha256 is not None else {}),
        },
    )
    if not errors:
        if expected_source_sha256 is not None and (len(jobs) != 1 or jobs[0].source_sha256 != expected_source_sha256):
            errors.append('Source changed since the audition was checked; regenerate the audition or restore the original source.')
        try:
            for job in jobs:
                for path in protected_paths:
                    protect_source(path, job.destinations)
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    if errors:
        if not json_output:
            for message in errors:
                print(f"Error: {message}", file=sys.stderr)
            print(
                f"Planning failed: {len(errors)} problem(s); no image outputs were published. "
                "(Planning does create the output directory and a temporary probe file inside it.)"
                if not dry_run else f"Planning failed: {len(errors)} problem(s); no outputs planned.",
                file=sys.stderr,
            )
        return finish([], errors, 1)

    if not json_output and not quiet:
        mode_note = " (DRY-RUN)" if dry_run else ""
        print(
            f"Starting batch process{mode_note} for {len(jobs)} image(s) "
            f"(material context: {settings.material}, thickness: {settings.material_thickness_in:g} in)."
        )
        for job in jobs:
            for message in job.warnings:
                print(f"Warning: {message}", file=sys.stderr)

    if dry_run:
        items = []
        skipped = 0
        for job in jobs:
            status = 'skipped' if job.is_skipped else 'planned'
            if job.is_skipped:
                skipped += 1
            items.append(JobOutcome(
                **_job_paths(job),
                status=status,
                output_size=job.output_size,
                estimated_memory_bytes=job.estimated_memory_bytes,
                workflow_summary={"geometry": job.workflow_geometry, "trim_bounds": "resolved after rendering"} if workflow.active else None,
            ))
            if not json_output and not quiet:
                status_str = f" [SKIPPED: {job.skip_reason}]" if job.is_skipped else ""
                w, h = job.output_size
                if job.artifacts:
                    print("Artifacts: " + ", ".join(job.artifacts.values()))
                print(f"Plan: {job.input_path} -> {job.output_path}{status_str}; "
                      f"{w} x {h} px ({w / 300:g} x {h / 300:g} in at 300 DPI); "
                      f"estimated working memory {job.estimated_memory_bytes:,} bytes")

        if not json_output and not quiet:
            print(f"Plan preview complete: {len(jobs)} item(s) planned, {skipped} skipped (0 written in dry-run).")
        return finish(items, [], 0)

    item_outcomes = []
    written = 0
    skipped = 0
    failures = 0
    for job in jobs:
        if job.is_skipped:
            if not json_output and not quiet:
                print(f"Skipping existing output: {job.output_path}")
            item_outcomes.append(JobOutcome(
                **_job_paths(job),
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
                settings=replace(settings, **job_values),
                manifest_path=job.manifest_path,
                preset_name=job.preset_name,
                prompt=prompt,
                model=model,
                quiet=(quiet or json_output),
                workflow=workflow,
                machine=machine, max_pixels=max_pixels, max_memory=max_memory,
                expected_source_sha256=job.source_sha256,
                expected_pixels_sha256=expected_pixels_sha256,
            )
            item_outcomes.append(JobOutcome(
                **_job_paths(job),
                status='written',
                duration_seconds=prep_res.get('duration_seconds', 0.0),
                workflow_summary=prep_res.get('workflow_summary'),
                cleanup_warnings=prep_res.get('cleanup_warnings') or None,
            ))
            if workflow.active and not json_output and not quiet:
                summary = prep_res['workflow_summary']
                print('Revision: ' + summary['revision'])
                print('Artifacts: ' + ', '.join(job.artifacts.values()))
                if summary['mask']['no_engrave']:
                    print('NO ENGRAVE: final mask is empty.')
                if workflow.trim:
                    print('Trim offset (px): ' + str(summary['trim']['offset_px']) + '; SVG preserves placement, standalone PNG does not.')
            written += 1
        except Exception as exc:
            if not json_output:
                print(f"Error processing {job.input_path}: {exc}", file=sys.stderr)
            cat = 'publication_error' if isinstance(exc, OSError) else 'transform_error'
            item_outcomes.append(JobOutcome(
                **_job_paths(job),
                status='failed',
                error_category=cat,
                error_message=str(exc),
            ))
            failures += 1

    exit_code = 0 if failures == 0 else 1

    if not json_output and not quiet:
        skip_msg = f", {skipped} skipped" if skipped else ""
        print(f"Batch summary: {written} written{skip_msg}, {failures} failed, {len(jobs)} planned.")
    return finish(item_outcomes, [], exit_code)


def export_audition_candidate(record_path, candidate, output_dir, *, source_path=None,
                              max_pixels=DEFAULT_MAX_PIXELS, max_memory=None, machine=None,
                              existing='overwrite', dry_run=False, json_output=False,
                              quiet=False, prompt=None, model=None):
    """Export an audition's numbered/named candidate with its exact render settings."""
    started = time.time()
    try:
        selection = load_audition_candidate(record_path, candidate, source_path=source_path,
            max_pixels=max_pixels, max_memory=max_memory, machine=machine)
    except ValidationError as exc:
        result = BatchResult.from_items([], [str(exc)], 2, started, dry_run)
        if json_output:
            print(result.to_json())
        else:
            print(f'Validation error: {exc}', file=sys.stderr)
        return result
    return run_batch([selection.source_path], output_dir, replace(selection.settings, manifest=True),
        preset_name=selection.name, width_in=selection.width_in, height_in=selection.height_in,
        workflow=selection.workflow, max_pixels=max_pixels, max_memory=max_memory, machine=machine,
        existing=existing, dry_run=dry_run, json_output=json_output, quiet=quiet, prompt=prompt, model=model,
        expected_source_sha256=selection.source_sha256, expected_pixels_sha256=selection.pixels_sha256,
        protected_paths=(selection.record_path, selection.sheet_path))
