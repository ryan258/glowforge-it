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

from glowforge_it.batch import process_directory, run_batch
from glowforge_it.cli import (
    build_parser,
    main,
    non_negative_float_type,
    non_negative_int_type,
    odd_int_type,
    positive_float_type,
    positive_inches_type,
    positive_int_type,
    threshold_type,
)
from glowforge_it.export import prep_for_glowforge, render_svg_document, write_svg_cut
from glowforge_it.geometry import circle_cut_bounds, heart_cut_points, output_geometry
from glowforge_it.imaging import CANVAS_BACKGROUND, transform_image
from glowforge_it.planning import (
    PlannedJob,
    SUPPORTED_EXTENSIONS,
    discover_sources,
    plan_batch,
    settings_suffix,
)
from glowforge_it.publication import RecoveryError, publish_generation, stage_beside
from glowforge_it.settings import (
    DEFAULT_MATERIAL,
    DEFAULT_MATERIAL_THICKNESS_IN,
    DEFAULT_MAX_PIXELS,
    DEFAULTS,
    MACHINE_BEDS_IN,
    PRESETS,
    ProcessingSettings,
    resolve_settings,
)

__all__ = [
    'CANVAS_BACKGROUND', 'DEFAULTS', 'DEFAULT_MATERIAL', 'DEFAULT_MATERIAL_THICKNESS_IN',
    'DEFAULT_MAX_PIXELS', 'MACHINE_BEDS_IN', 'PRESETS', 'PlannedJob', 'ProcessingSettings',
    'RecoveryError', 'SUPPORTED_EXTENSIONS', 'build_parser', 'circle_cut_bounds',
    'discover_sources', 'heart_cut_points', 'main', 'non_negative_float_type',
    'non_negative_int_type', 'odd_int_type', 'output_geometry', 'plan_batch',
    'positive_float_type', 'positive_inches_type', 'positive_int_type',
    'prep_for_glowforge', 'process_directory', 'publish_generation', 'render_svg_document',
    'resolve_settings', 'run_batch', 'settings_suffix', 'stage_beside', 'threshold_type',
    'transform_image', 'write_svg_cut',
]


if __name__ == "__main__":
    sys.exit(main())
