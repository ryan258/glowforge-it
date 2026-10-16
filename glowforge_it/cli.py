"""Argument parsing, CLI-specific validation, and the console entry point.

Everything below delegates the actual work to the application modules. Nothing in the
package imports this module.
"""

import argparse
import json
import time
import math
import re
import sys
from dataclasses import fields
from fractions import Fraction

from .batch import export_audition_candidate, run_batch
from .proofing import run_audition
from .planning import BatchResult, verify_job_manifest
from .settings import (
    DEFAULT_MATERIAL,
    DEFAULT_MATERIAL_THICKNESS_IN,
    DEFAULT_MAX_PIXELS,
    MACHINE_BEDS_IN,
    PRESETS,
    RENDER_MODES,
    ProcessingSettings,
    ValidationError,
    __version__,
    explicit_keys,
    load_recipe_file,
    resolve_settings,
)
from .workflow import WorkflowOptions


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
    except (ValueError, ZeroDivisionError, AttributeError, OverflowError):
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


def workflow_from_args(args, recipe=None):
    if recipe is None:
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


class CLIUsageError(ValueError):
    """Usage failures become data when --json is requested."""


class ResultParser(argparse.ArgumentParser):
    json_errors = False

    def error(self, message):
        if self.json_errors:
            raise CLIUsageError(message)
        super().error(message)


def build_parser():
    parser = ResultParser(
        prog="glowforge-it",
        description=(
            "Prepare raster artwork for Glowforge. Project material context: "
            f"{DEFAULT_MATERIAL} at {DEFAULT_MATERIAL_THICKNESS_IN:g} in. "
            "This tool does not set laser power, speed, or passes."
        ),
        add_help=False,
        allow_abbrev=False,  # an abbreviated --json would skip the JSON error contract
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--help', action='help', help='Show this help message and exit.')
    parser.add_argument('--verify-manifest', metavar='PATH', help='Verify source/output hashes in an archived job manifest without rendering.')
    parser.add_argument('--verify-current-engine', action='store_true', help='Also require the manifest engine/runtime to match this installation; use with --verify-manifest.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}', help='Show program version number and exit.')
    parser.add_argument('--input', nargs='+', default=None, help='One or more image files or folders (default: input/); one source override when exporting an audition.')
    parser.add_argument('-o', '--output', default='output', help='Folder where processed files are saved.')
    parser.add_argument('-p', '--preset', choices=sorted(PRESETS), help='Image-preparation preset; does not select machine settings.')
    parser.add_argument(
        '--audition',
        nargs='+',
        choices=sorted(PRESETS),
        metavar='PRESET',
        help='Write a labeled, mode-agnostic contact sheet comparing these presets; no machine artwork is emitted.',
    )
    parser.add_argument('--recipe', help='Path to custom recipe profile (.toml or .json).')
    parser.add_argument('--export-audition', metavar='PATH', help='Export a candidate from a saved audition JSON record, using its recorded source, dimensions and recipe.')
    parser.add_argument('--candidate', metavar='NAME_OR_NUMBER', help='Candidate name or 1-based contact-sheet number; requires --export-audition.')
    parser.add_argument('--material', default=None, help=f'Descriptive stock label for this run (default: {DEFAULT_MATERIAL}).')
    parser.add_argument('--material-thickness', dest='material_thickness_in', type=positive_inches_type, default=None, metavar='IN', help=f'Descriptive stock thickness in inches (default: {DEFAULT_MATERIAL_THICKNESS_IN}).')
    parser.add_argument('-b', '--black-threshold', dest='black_thresh', type=threshold_type, default=None, help='Force pixels at or below this grayscale value to black.')
    parser.add_argument('-W', '--white-threshold', dest='white_thresh', type=threshold_type, default=None, help='Force pixels at or above this grayscale value to white.')
    parser.add_argument('-d', '--dither-threshold', dest='dither_thresh', type=threshold_type, default=None, help='Atkinson decision threshold for midtones.')
    parser.add_argument('-c', '--clean-solids', action=argparse.BooleanOptionalAction, default=None, help='Snap near-black and near-white pixels to solid values.')
    parser.add_argument('--clean-solids-black', type=threshold_type, default=None, help='Near-black snapping threshold.')
    parser.add_argument('--clean-solids-white', type=threshold_type, default=None, help='Near-white snapping threshold.')
    parser.add_argument('-i', '--invert', action=argparse.BooleanOptionalAction, default=None, help='Invert grayscale values before thresholding and dithering.')
    parser.add_argument('-w', '--width', type=positive_inches_type, default=None, help='Target physical width in inches at 300 DPI.')
    parser.add_argument('-h', '--height', type=positive_inches_type, default=None, help='Target physical height in inches at 300 DPI.')
    parser.add_argument('--nb', '--no-border', dest='no_border', action='store_true', default=None, help='Disable the 1-pixel bitmap border.')
    parser.add_argument('--border', dest='no_border', action='store_false', default=None, help='Keep the 1-pixel bitmap border, overriding a recipe that disables it.')
    parser.add_argument('--denoise', dest='denoise_radius', type=odd_int_type, default=None, help='Median filter size; 0 turns denoising off, otherwise an odd integer of at least 3.')
    parser.add_argument('--contrast', type=positive_float_type, default=None, help='Contrast enhancement factor.')
    parser.add_argument('--sharpen-radius', type=non_negative_float_type, default=None, help='Unsharp-mask radius; 0 turns sharpening off.')
    parser.add_argument('--sharpen-percent', type=non_negative_int_type, default=None, help='Unsharp-mask strength percentage; 0 turns sharpening off.')
    parser.add_argument('--sharpen-threshold', type=non_negative_int_type, default=None, help='Unsharp-mask minimum brightness difference.')
    parser.add_argument('--circle-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a circular transparent raster mask.')
    parser.add_argument('--heart-cut', action=argparse.BooleanOptionalAction, default=None, help='Make a heart-shaped transparent raster mask.')
    parser.add_argument('--fit', '--fit-mode', dest='fit_mode', choices=('stretch', 'contain', 'cover'), default=None, help='When both target dimensions are given: stretch, fit inside with white padding (padding never inverts), or fill and crop.')
    parser.add_argument('--render-mode', choices=RENDER_MODES, default=None, help='Artwork renderer: Atkinson, solid silhouette, ordered Bayer screen, variable-cell halftone, directional hatch, Sobel edge, or tone contour.')
    parser.add_argument('--silhouette-threshold', type=threshold_type, default=None, help='Grayscale threshold for --render-mode silhouette; values at or below burn.')
    parser.add_argument('--ordered-matrix-size', type=positive_int_type, choices=(2, 4, 8), default=None, help='Bayer matrix size for --render-mode ordered.')
    parser.add_argument('--halftone-cell-px', type=positive_int_type, default=None, help='Halftone screen cell size in output pixels; minimum 2.')
    parser.add_argument('--halftone-angle', type=non_negative_float_type, default=None, help='Halftone screen angle in degrees, 0 inclusive and 180 exclusive.')
    parser.add_argument('--hatch-spacing-px', type=positive_int_type, default=None, help='Hatch line spacing in output pixels; minimum 2.')
    parser.add_argument('--hatch-angle', type=non_negative_float_type, default=None, help='Hatch line angle in degrees, 0 inclusive and 180 exclusive.')
    parser.add_argument('--hatch-cross', action=argparse.BooleanOptionalAction, default=None, help='Add a perpendicular hatch family for crosshatching.')
    parser.add_argument('--edge-threshold', type=positive_int_type, default=None, help='Sobel edge strength threshold for --render-mode edge; range 1..255.')
    parser.add_argument('--contour-levels', type=positive_int_type, default=None, help='Tone-band count for --render-mode contour; range 2..64.')
    parser.add_argument('--svg-cut', action=argparse.BooleanOptionalAction, default=None, help='Write an SVG sidecar with an embedded engraving image and vector cut outline. Requires a circle or heart shape.')
    parser.add_argument('--svg-linework', action=argparse.BooleanOptionalAction, default=None, help='Write a deterministic centerline-style SVG sidecar derived from the final binary artwork mask. It is not a cutline.')
    parser.add_argument('--tone-layers', type=non_negative_int_type, choices=(0, 2, 3, 4), default=None, help='Write 2, 3, or 4 registered exclusive tone-band PNG sidecars; 0 disables them.')
    parser.add_argument('--stamp-text', default=None, help='Write a separate collision-checked personalization text-mask sidecar.')
    parser.add_argument('--stamp-position', choices=('top-left', 'top-right', 'bottom-left', 'bottom-right'), default=None, help='Position for --stamp-text.')
    parser.add_argument('--stamp-size-px', type=positive_int_type, default=None, help='Personalization text size in output pixels; minimum 6.')
    parser.add_argument('--stamp-margin-px', type=non_negative_int_type, default=None, help='Personalization text margin in output pixels.')
    parser.add_argument('--qr-text', default=None, help='Write a separate protected version-1/L QR mask for 1–17 UTF-8 bytes.')
    parser.add_argument('--qr-position', choices=('top-left', 'top-right', 'bottom-left', 'bottom-right'), default=None, help='Position for --qr-text.')
    parser.add_argument('--qr-module-px', type=positive_int_type, default=None, help='QR module size in output pixels; minimum 2.')
    parser.add_argument('--qr-margin-px', type=non_negative_int_type, default=None, help='QR quiet-zone and canvas margin in output pixels.')
    parser.add_argument('--manifest', action=argparse.BooleanOptionalAction, default=None, help='Emit a companion job manifest. Text, QR, tone-layer, linework and active workflow exports always require it, even with --no-manifest.')
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
        ('trim', 'Trim empty burn bounds; preserve placement in companion SVG.')):
        parser.add_argument('--' + flag, action=argparse.BooleanOptionalAction, default=None, help=help_text)
    parser.add_argument('--material-mode', choices=('legacy', 'darkening', 'lightening'), default=None, help='Substrate ablation polarity: darkening (light substrate) or lightening (slate, dark acrylic). Required for tone curves.')
    parser.add_argument('--tone-black', type=threshold_type, default=None, help='Tone curve black clip, 0-255 (needs --material-mode).')
    parser.add_argument('--tone-white', type=threshold_type, default=None, help='Tone curve white clip, 0-255 (needs --material-mode).')
    parser.add_argument('--tone-gamma', type=positive_float_type, default=None, help='Tone curve gamma exponent, greater than 0 (needs --material-mode).')
    parser.add_argument('--preview-seed', type=non_negative_int_type, default=None, help='Random seed for the procedural wood grain in --preview-finish.')
    parser.add_argument('--preview-spread-mm', type=non_negative_float_type, default=None, help='Simulated burn spread in mm for the finish preview, 0-2.')
    parser.add_argument('--client', default=None, help='Client name for --proof-sheet (max 240 characters).')
    parser.add_argument('--order', default=None, help='Order reference for --proof-sheet (max 240 characters).')
    parser.add_argument('--jig', choices=('circle', 'rectangle'), default=None, help='Write a registered pocket-jig SVG; needs --machine and measured blank dimensions.')
    for flag, help_text in (
            ('blank-width', 'Measured blank width in inches (jig).'),
            ('blank-height', 'Measured blank height in inches (jig).'),
            ('jig-margin', 'Margin around the jig canvas in inches.'),
            ('jig-gap', 'Gap between pocket blanks in inches.')):
        parser.add_argument('--' + flag, type=positive_inches_type, default=None, help=help_text)
    for flag, help_text in (
            ('pocket-clearance', 'Per-side clearance around each blank in inches (0 allowed).'),
            ('kerf', 'Measured full laser cut width in inches; shrinks the cut path.')):
        parser.add_argument('--' + flag, type=non_negative_float_type, default=None, help=help_text)
    for flag, help_text in (
            ('jig-rows', 'Pocket rows (rows x columns at most 400).'),
            ('jig-columns', 'Pocket columns (rows x columns at most 400).')):
        parser.add_argument('--' + flag, type=positive_int_type, default=None, help=help_text)
    return parser


def main(argv=None, defaults=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    parser.json_errors = '--json' in argv
    started = time.time()
    try:
        args = parser.parse_args(argv)

        if args.export_audition:
            if args.candidate is None:
                parser.error('--export-audition requires --candidate NAME_OR_NUMBER.')
            locked = {field.name for field in fields(ProcessingSettings)} | {field.name for field in fields(WorkflowOptions)}
            overrides = sorted(key for key in locked if getattr(args, key, None) is not None)
            if (overrides or args.preset or args.recipe or args.audition or args.width is not None
                    or args.height is not None or args.verify_manifest or args.verify_current_engine):
                parser.error('Selected audition export uses its recorded recipe and dimensions; omit rendering, recipe, audition and verification overrides.')
            if args.input is not None and len(args.input) != 1:
                parser.error('Selected audition export accepts one --input source file override.')
            result = export_audition_candidate(args.export_audition, args.candidate, args.output,
                source_path=args.input[0] if args.input is not None else None,
                max_pixels=args.max_pixels, max_memory=args.max_memory, machine=args.machine,
                existing=args.existing, dry_run=args.dry_run, json_output=args.json, quiet=args.quiet,
                prompt=args.prompt, model=args.model)
            return result.exit_code
        if args.candidate is not None:
            parser.error('--candidate requires --export-audition.')
        args.input = args.input if args.input is not None else ['input']
        if args.verify_manifest:
            valid, errors = verify_job_manifest(args.verify_manifest, require_current_engine=args.verify_current_engine)
            mode = 'current-engine-and-archive-integrity' if args.verify_current_engine else 'archive-integrity'
            if args.json:
                print(json.dumps({'success': valid, 'exit_code': 0 if valid else 1, 'verification': mode,
                                  'manifest_path': args.verify_manifest, 'errors': errors}, indent=2))
            else:
                if not args.quiet:
                    print(f'{mode}: {"verified" if valid else "failed"}')
                for error in errors:
                    print(error, file=sys.stderr)
            return 0 if valid else 1
        if args.verify_current_engine:
            parser.error('--verify-current-engine requires --verify-manifest.')
        if args.audition:
            if args.preset is not None:
                parser.error('--audition names the candidate presets; do not combine it with --preset.')
            try:
                recipe = load_recipe_file(args.recipe) if args.recipe else {}
                workflow = workflow_from_args(args, recipe)
                candidates = []
                for candidate in args.audition:
                    candidate_args = argparse.Namespace(**vars(args))
                    candidate_args.preset = candidate
                    candidate_settings = resolve_settings(candidate_args, recipe, defaults=defaults)
                    candidate_settings.validate()
                    candidates.append((candidate, candidate_settings))
            except (ValidationError, OSError) as exc:
                parser.error(str(exc))

            result = run_audition(
                args.input,
                args.output,
                candidates,
                width_in=args.width,
                height_in=args.height,
                max_pixels=args.max_pixels,
                max_memory=args.max_memory,
                machine=args.machine,
                existing=args.existing,
                dry_run=args.dry_run,
                json_output=args.json,
                quiet=args.quiet,
                workflow=workflow,
            )
            return result.exit_code

        try:
            recipe = load_recipe_file(args.recipe) if args.recipe else {}
            settings = resolve_settings(args, recipe, defaults=defaults)
            settings.validate()
            workflow = workflow_from_args(args, recipe)
            workflow.validate(invert=settings.invert, svg_cut=settings.svg_cut, machine=args.machine)
        except (ValidationError, OSError) as exc:
            parser.error(str(exc))

        result = run_batch(
            args.input,
            args.output,
            # A recipe's preset is as explicit as --preset: it must not be mixed with a filename-inferred one.
            preset_name=args.preset or recipe.get('preset'),
            width_in=args.width,
            height_in=args.height,
            settings=settings,
            max_pixels=args.max_pixels,
            machine=args.machine,
            existing=args.existing,
            dry_run=args.dry_run,
            max_memory=args.max_memory,
            prompt=args.prompt,
            model=args.model,
            json_output=args.json,
            quiet=args.quiet,
            workflow=workflow,
            explicit_keys=explicit_keys(args, recipe),
        )
        return result.exit_code
    except CLIUsageError as exc:
        print(BatchResult.from_items([], [str(exc)], 2, started, '--dry-run' in argv).to_json())
        return 2


def gf_main(argv=None):
    """Match the repository gf wrapper's clean-solids default after installation."""
    return main(sys.argv[1:] if argv is None else argv, defaults={'clean_solids': True})
