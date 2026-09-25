"""Coordinating a plan and its execution, and reporting the batch outcome.

Parses no command-line arguments. `run_batch` still returns a boolean and prints a
summary; a structured per-item result is E14 and is not done.
"""

import sys

from .export import prep_for_glowforge
from .planning import plan_batch
from .settings import DEFAULT_MATERIAL, DEFAULT_MATERIAL_THICKNESS_IN, DEFAULT_MAX_PIXELS

def run_batch(
    input_paths,
    output_dir,
    black_thresh,
    white_thresh,
    dither_thresh,
    clean_solids,
    clean_solids_black,
    clean_solids_white,
    invert,
    width_in,
    height_in,
    no_border,
    denoise_radius,
    contrast,
    sharpen_radius,
    sharpen_percent,
    sharpen_threshold,
    circle_cut,
    heart_cut,
    preset_name,
    fit_mode='stretch',
    svg_cut=False,
    max_pixels=DEFAULT_MAX_PIXELS,
    machine=None,
    existing='overwrite',
    material=DEFAULT_MATERIAL,
    material_thickness_in=DEFAULT_MATERIAL_THICKNESS_IN,
):
    """Plan the complete job, then publish it. Nothing is written if planning fails."""
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

    print(
        f"Starting batch process for {list(input_paths)} "
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
    )
    if errors:
        for message in errors:
            print(f"Error: {message}", file=sys.stderr)
        print(
            f"Planning failed: {len(errors)} problem(s); no image outputs were published. "
            "(Planning does create the output directory and a temporary probe file inside it.)",
            file=sys.stderr,
        )
        return False

    failures = 0
    for job in jobs:
        try:
            prep_for_glowforge(
                job.input_path,
                job.output_path,
                width_in=width_in,
                height_in=height_in,
                svg_cut=svg_cut,
                **values,
            )
        except Exception as exc:
            print(f"Error processing {job.input_path}: {exc}", file=sys.stderr)
            failures += 1

    print(f"Batch summary: {len(jobs) - failures} written, {failures} failed, {len(jobs)} planned.")
    return failures == 0

def process_directory(input_dir, output_dir, **kwargs):
    """Compatibility entry point for a single input path."""
    return run_batch([input_dir], output_dir, **kwargs)
