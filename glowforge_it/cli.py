"""Argument parsing, CLI-specific validation, and the console entry point.

Everything below delegates the actual work to the application modules. Nothing in the
package imports this module.
"""

import argparse
import math
import re
import sys
from fractions import Fraction

from .batch import BatchResult, JobOutcome, run_batch
from .settings import (
    DEFAULT_MATERIAL,
    DEFAULT_MATERIAL_THICKNESS_IN,
    DEFAULT_MAX_PIXELS,
    MACHINE_BEDS_IN,
    PRESETS,
    ValidationError,
    __version__,
    load_recipe_file,
    resolve_settings,
)


def threshold_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue < 0 or ivalue > 255:
        raise argparse.ArgumentTypeError(f"Threshold '{value}' must be between 0 and 255.")
    return ivalue


def positive_float_type(value):
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number.")
    if not math.isfinite(fvalue) or fvalue <= 0:
        raise argparse.ArgumentTypeError(f"Dimension '{value}' must be greater than 0.")
    return fvalue


def positive_inches_type(value):
    """Parse a positive inch value as a decimal or fraction such as 1/8."""
    try:
        fvalue = float(Fraction(value.strip()))
    except (ValueError, ZeroDivisionError, AttributeError):
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid inch measurement.")
    if not math.isfinite(fvalue) or fvalue <= 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than 0 inches.")
    return fvalue


def non_negative_float_type(value):
    """Parse a float where 0 explicitly disables the stage."""
    try:
        fvalue = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a number.")
    if not math.isfinite(fvalue) or fvalue < 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be 0 (off) or greater.")
    return fvalue


def odd_int_type(value):
    """Parse a median-filter size; 0 explicitly disables denoising."""
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue == 0:
        return 0
    if ivalue < 3 or ivalue % 2 == 0:
        raise argparse.ArgumentTypeError(f"Denoise size '{value}' must be 0 (off) or an odd integer >= 3.")
    return ivalue


def positive_int_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than 0.")
    return ivalue


def non_negative_int_type(value):
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not an integer.")
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"'{value}' must be greater than or equal to 0.")
    return ivalue


def memory_size_type(value):
    """Parse memory size string like '500MB', '1GB', '256M', or integer bytes."""
    val = value.strip().upper()
    units = {
        'B': 1,
        'K': 1024,
        'KB': 1024,
        'M': 1024 * 1024,
        'MB': 1024 * 1024,
        'G': 1024 * 1024 * 1024,
        'GB': 1024 * 1024 * 1024,
    }
    match = re.match(r'^([0-9]+(?:\.[0-9]+)?)\s*([A-Z]*)$', val)
    if not match:
        raise argparse.ArgumentTypeError(f"Invalid memory size '{value}'.")
    num_str, unit_str = match.groups()
    unit = units.get(unit_str, None) if unit_str else 1
    if unit is None:
        raise argparse.ArgumentTypeError(f"Unknown memory unit in '{value}'. Use B, KB, MB, or GB.")
    try:
        bytes_val = int(float(num_str) * unit)
    except (ValueError, OverflowError):
        raise argparse.ArgumentTypeError(f"Invalid number in memory size '{value}'.")
    if bytes_val <= 0:
        raise argparse.ArgumentTypeError(f"Memory budget '{value}' must be greater than 0.")
    return bytes_val


def workflow_from_args(args):
    from dataclasses import fields
    from .workflow import WorkflowOptions
    from .settings import load_recipe_file
    recipe = load_recipe_file(args.recipe) if args.recipe else {}
    values = recipe.get('workflow', {})
    if not isinstance(values, dict):
        raise ValidationError('Recipe workflow must be an object/table.')
    known = {f.name for f in fields(WorkflowOptions)}
    if set(values) - known:
        raise ValidationError('Unknown workflow recipe keys: ' + ', '.join(sorted(set(values) - known)))
    values = dict(values)
    for key in known:
        value = getattr(args, key, None)
        if value is not None:
            values[key] = value
    return WorkflowOptions(**values)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="glowforge-it",
        description=(
            "Prepare raster artwork for Glowforge. Project material context: "
            f"{DEFAULT_MATERIAL} at {DEFAULT_MATERIAL_THICKNESS_IN:g} in. "
            "This tool does not set laser power, speed, or passes."
        ),
        add_help=False,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--help', action='help', help='Show this help message and exit.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}', help='Show program version number and exit.')
    parser.add_argument('--input', nargs='+', default=['input'], help='One or more image files or folders.')
    parser.add_argument('-o', '--output', default='output', help='Folder where processed files are saved.')
    parser.add_argument('-p', '--preset', choices=sorted(PRESETS), help='Image-preparation preset; does not select machine settings.')
    parser.add_argument('--recipe', help='Path to custom recipe profile (.toml or .json).')
    parser.add_argument('--material', default=None, help=f'Descriptive stock label for this run (default: {DEFAULT_MATERIAL}).')
    parser.add_argument('--material-thickness', type=positive_inches_type, default=None, metavar='IN', help=f'Descriptive stock thickness in inches (default: {DEFAULT_MATERIAL_THICKNESS_IN}).')
    parser.add_argument('-b', '--black-threshold', type=threshold_type, default=None, help='Force pixels at or below this grayscale value to black.')
    parser.add_argument('-W', '--white-threshold', type=threshold_type, default=None, help='Force pixels at or above this grayscale value to white.')
    parser.add_argument('-d', '--dither-threshold', type=threshold_type, default=None, help='Atkinson decision threshold for midtones.')
    parser.add_argument('-c', '--clean-solids', action=argparse.BooleanOptionalAction, default=None, help='Snap near-black and near-white pixels to solid values.')
    parser.add_argument('--clean-solids-black', type=threshold_type, default=None, help='Near-black snapping threshold.')
    parser.add_argument('--clean-solids-white', type=threshold_type, default=None, help='Near-white snapping threshold.')
    parser.add_argument('-i', '--invert', action=argparse.BooleanOptionalAction, default=None, help='Invert grayscale values before thresholding and dithering.')
    parser.add_argument('-w', '--width', type=positive_float_type, default=None, help='Target physical width in inches at 300 DPI.')
    parser.add_argument('-h', '--height', type=positive_float_type, default=None, help='Target physical height in inches at 300 DPI.')
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', default=None, help='Disable the 1-pixel bitmap border.')
    parser.add_argument('--denoise', type=odd_int_type, default=None, help='Median filter size; 0 turns denoising off, otherwise an odd integer of at least 3.')
    parser.add_argument('--contrast', type=positive_float_type, default=None, help='Contrast enhancement factor.')
    parser.add_argument('--sharpen-radius', type=non_negative_float_type, default=None, help='Unsharp-mask radius; 0 turns sharpening off.')
    parser.add_argument('--sharpen-percent', type=non_negative_int_type, default=None, help='Unsharp-mask strength percentage; 0 turns sharpening off.')
    parser.add_argument('--sharpen-threshold', type=non_negative_int_type, default=None, help='Unsharp-mask minimum brightness difference.')
    parser.add_argument('--circle-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a circular transparent raster mask.')
    parser.add_argument('--heart-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a heart-shaped transparent raster mask.')
    parser.add_argument('--fit', '--fit-mode', dest='fit_mode', choices=('stretch', 'contain', 'cover'), default=None, help='When both target dimensions are given: stretch, fit inside with white padding (padding never inverts), or fill and crop.')
    parser.add_argument('--svg-cut', action=argparse.BooleanOptionalAction, default=None, help='Write an SVG sidecar with an embedded engraving image and vector cut outline. Requires a circle or heart shape.')
    parser.add_argument('--manifest', action=argparse.BooleanOptionalAction, default=None, help='Emit a companion versioned job manifest JSON file adjacent to each output.')
    parser.add_argument('--machine', choices=sorted(MACHINE_BEDS_IN), help='Check approximate nominal printable area for a Glowforge model.')
    parser.add_argument('--max-pixels', type=positive_int_type, default=DEFAULT_MAX_PIXELS, help='Maximum source and output pixels per image.')
    parser.add_argument('--max-memory', type=memory_size_type, default=None, help='Maximum estimated working memory per image (e.g. 500MB, 1GB).')
    parser.add_argument('--existing', choices=('overwrite', 'skip', 'error'), default='overwrite', help='Policy for an existing PNG and its optional SVG sidecar.')
    parser.add_argument('--dry-run', action='store_true', help='Preview planned files, dimensions, and memory without creating directories or writing outputs.')
    parser.add_argument('--json', action='store_true', help='Output structured machine-readable JSON result summary.')
    parser.add_argument('--prompt', help='AI source-art prompt string to record in job manifest.')
    parser.add_argument('--model', help='AI model or generator identifier to record in job manifest.')
    parser.add_argument('--quiet', action='store_true', help='Suppress conversational progress and batch summary logs.')
    for flag, help_text in (
        ('svg-operations', 'Opt in to unified SVG: raster engraving, red cuts, blue scores.'),
        ('score-marks', 'Add an intentional blue L-shaped orientation score at top left.'),
        ('preview-finish', 'Write deterministic simulated maple PNG from the exact burn mask.'),
        ('proof-sheet', 'Write a one-page approval PDF plus simulated finish.'),
        ('trim', 'Trim empty burn bounds; preserve placement in companion SVG.'),
        ('optimize-orientation', 'Compare 0/90 degree scan rows; never rotates artwork.')):
        parser.add_argument('--' + flag, action=argparse.BooleanOptionalAction, default=None, help=help_text)
    parser.add_argument('--material-mode', choices=('legacy', 'darkening', 'lightening'), default=None)
    parser.add_argument('--tone-black', type=threshold_type, default=None)
    parser.add_argument('--tone-white', type=threshold_type, default=None)
    parser.add_argument('--tone-gamma', type=positive_float_type, default=None)
    parser.add_argument('--preview-seed', type=non_negative_int_type, default=None)
    parser.add_argument('--preview-spread-mm', type=non_negative_float_type, default=None)
    parser.add_argument('--client', default=None)
    parser.add_argument('--order', default=None)
    parser.add_argument('--jig', choices=('circle', 'rectangle'), default=None)
    for flag in ('blank-width', 'blank-height', 'jig-margin', 'jig-gap', 'engraving-lpi'):
        parser.add_argument('--' + flag, type=positive_float_type, default=None)
    for flag in ('pocket-clearance', 'kerf'):
        parser.add_argument('--' + flag, type=non_negative_float_type, default=None)
    for flag in ('jig-rows', 'jig-columns'):
        parser.add_argument('--' + flag, type=positive_int_type, default=None)
    parser.add_argument('--orientation-constraint', choices=('free', 'grain', 'reading'), default=None)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        settings = resolve_settings(args)
        settings.validate()
        workflow = workflow_from_args(args)
        workflow.validate(invert=settings.invert, svg_cut=settings.svg_cut, machine=args.machine)
    except (ValidationError, FileNotFoundError) as exc:
        parser.error(str(exc))

    result = run_batch(
        args.input,
        args.output,
        preset_name=args.preset,
        width_in=args.width,
        height_in=args.height,
        svg_cut=settings.svg_cut,
        max_pixels=args.max_pixels,
        machine=args.machine,
        existing=args.existing,
        material=settings.material,
        material_thickness_in=settings.material_thickness_in,
        dry_run=args.dry_run,
        manifest=settings.manifest,
        max_memory=args.max_memory,
        prompt=args.prompt,
        model=args.model,
        json_output=args.json,
        quiet=args.quiet,
        workflow=workflow,
        **settings.transform_kwargs(),
    )
    return result.exit_code


def gf_main(argv=None):
    """Match the repository gf wrapper's clean-solids default after installation."""
    return main(['--clean-solids', *(sys.argv[1:] if argv is None else argv)])
