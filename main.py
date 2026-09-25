# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.4.2",
#     "pillow==12.1.1",
# ]
# ///

"""Compatibility launcher for the `glowforge_it` package.

The implementation lives in `glowforge_it/`; this file stays because `gf` runs it by
absolute path and because its inline script metadata above is what tells `uv` which
dependencies to install. It also re-exports the names that existing tests and review
probes import from `main`.

New code should import from `glowforge_it` directly.
"""

import os  # noqa: F401  (review probes reach os.replace through this module)
import sys

from glowforge_it import __version__
from glowforge_it.batch import BatchResult, JobOutcome, process_directory, run_batch
from glowforge_it.cli import (
    build_parser,
    main,
    memory_size_type,
    non_negative_float_type,
    non_negative_int_type,
    odd_int_type,
    positive_float_type,
    positive_inches_type,
    positive_int_type,
    threshold_type,
)
from glowforge_it.export import build_manifest, prep_for_glowforge, render_svg_document, write_svg_cut
from glowforge_it.geometry import circle_cut_bounds, heart_cut_points, output_geometry, resolve_oriented_geometry
from glowforge_it.imaging import CANVAS_BACKGROUND, transform_image
from glowforge_it.planning import (
    PlannedJob,
    SUPPORTED_EXTENSIONS,
    discover_sources,
    estimate_image_memory,
    plan_batch,
    settings_suffix,
    verify_job_manifest,
)
from glowforge_it.publication import RecoveryError, publish_generation, sha256_file, stage_beside
from glowforge_it.settings import (
    DEFAULT_MATERIAL,
    DEFAULT_MATERIAL_THICKNESS_IN,
    DEFAULT_MAX_PIXELS,
    DEFAULTS,
    MACHINE_BEDS_IN,
    PRESETS,
    ProcessingSettings,
    ValidationError,
    load_recipe_file,
    resolve_settings,
)

__all__ = [
    'CANVAS_BACKGROUND', 'DEFAULTS', 'DEFAULT_MATERIAL', 'DEFAULT_MATERIAL_THICKNESS_IN',
    'DEFAULT_MAX_PIXELS', 'MACHINE_BEDS_IN', 'PRESETS', 'BatchResult', 'JobOutcome',
    'PlannedJob', 'ProcessingSettings', 'RecoveryError', 'SUPPORTED_EXTENSIONS',
    'ValidationError', '__version__', 'build_manifest', 'build_parser', 'circle_cut_bounds',
    'discover_sources', 'estimate_image_memory', 'heart_cut_points', 'load_recipe_file',
    'main', 'memory_size_type', 'non_negative_float_type', 'non_negative_int_type',
    'odd_int_type', 'output_geometry', 'plan_batch', 'positive_float_type',
    'positive_inches_type', 'positive_int_type', 'prep_for_glowforge', 'process_directory',
    'publish_generation', 'render_svg_document', 'resolve_oriented_geometry',
    'resolve_settings', 'run_batch', 'settings_suffix', 'sha256_file', 'stage_beside',
    'threshold_type', 'transform_image', 'verify_job_manifest', 'write_svg_cut',
]


if __name__ == "__main__":
    sys.exit(main())
