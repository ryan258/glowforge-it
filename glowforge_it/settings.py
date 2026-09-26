"""Defaults, presets, and resolved processing settings.

Owns the option surface and its precedence rules. Writes no files and prints nothing.
"""

import json
import math
import tomllib
from dataclasses import asdict, dataclass, fields

__version__ = "0.2.0rc1"

DEFAULT_MAX_PIXELS = 20_000_000

DEFAULT_MATERIAL = 'medium maple plywood'

DEFAULT_MATERIAL_THICKNESS_IN = 0.125

MACHINE_BEDS_IN = {
    # Nominal printable areas; leave additional margin in the Glowforge app.
    'performance': (19.5, 11.0),
    'aura': (12.0, 12.0),
    'spark': (8.5, 11.0),
}

# --- Presets and Defaults ---
PRESETS = {
    'photo-high-detail': {
        'denoise_radius': 3,
        'contrast': 1.8,
        'sharpen_radius': 1.5,
        'sharpen_percent': 200
    },
    'photo-soft': {
        'contrast': 1.2,
        'sharpen_radius': 1.0,
        'sharpen_percent': 100
    },
    'vector-graphic': {
        'clean_solids': True,
        'clean_solids_black': 50,
        'clean_solids_white': 200,
        'contrast': 2.0
    },
    'ai-art': {
        'denoise_radius': 3,
        'clean_solids': True,
        'contrast': 1.6,
        'sharpen_radius': 2.0,
        'sharpen_percent': 150
    },
    'ai-art-detailed': {
        'denoise_radius': 5,
        'clean_solids': True,
        'contrast': 1.8,
        'sharpen_radius': 2.5,
        'sharpen_percent': 200
    },
    'line-art': {
        'clean_solids': True,
        'contrast': 2.5,
        'black_thresh': 20
    },
    'sketch': {
        'contrast': 1.3,
        'sharpen_radius': 1.0,
        'sharpen_percent': 250,
        'sharpen_threshold': 1
    },
    'wood-hard': {
        'contrast': 1.7,
        'black_thresh': 10,
        'sharpen_radius': 2.0
    },
    'wood-soft': {
        'contrast': 1.4,
        'white_thresh': 245,
        'denoise_radius': 3
    },
    'acrylic': {
        'clean_solids': True,
        'contrast': 2.0,
        'sharpen_radius': 1.5,
        'sharpen_percent': 180
    },
    'leather': {
        'contrast': 1.3,
        'denoise_radius': 3,
        'sharpen_radius': 1.0,
        'sharpen_percent': 120
    },
    'glass': {
        'contrast': 1.9,
        'sharpen_radius': 2.0,
        'sharpen_percent': 170
    },
    'stamp': {
        'clean_solids': True,
        'clean_solids_black': 60,
        'clean_solids_white': 190,
        'contrast': 3.0
    },
    'high-contrast': {
        'clean_solids': True,
        'black_thresh': 15,
        'white_thresh': 240,
        'contrast': 2.5
    },
    'low-res-enhance': {
        'denoise_radius': 3,
        'contrast': 1.6,
        'sharpen_radius': 1.5,
        'sharpen_percent': 220
    },
}


class ValidationError(ValueError):
    """Raised when options or settings violate configuration invariants."""
    pass


def load_recipe_file(recipe_path):
    """Load and validate a TOML or JSON recipe file.

    Rejects unknown keys to prevent silent misconfiguration.
    """
    with open(recipe_path, 'rb') as f:
        content = f.read()

    data = None
    parse_errors = []
    # Try TOML first (supports UTF-8 text/bytes)
    try:
        data = tomllib.loads(content.decode('utf-8'))
    except Exception as toml_err:
        parse_errors.append(f"TOML: {toml_err}")
        try:
            data = json.loads(content.decode('utf-8'))
        except Exception as json_err:
            parse_errors.append(f"JSON: {json_err}")
            raise ValidationError(
                f"Cannot parse recipe '{recipe_path}' as TOML or JSON ({'; '.join(parse_errors)})."
            )

    if not isinstance(data, dict):
        raise ValidationError(f"Recipe file '{recipe_path}' must contain a key-value mapping.")

    # Support optional [recipe] table wrapper or top-level keys
    recipe_dict = data.get('recipe', data)
    if not isinstance(recipe_dict, dict):
        raise ValidationError(f"Recipe section in '{recipe_path}' must be a dictionary.")

    unknown_keys = set(recipe_dict.keys()) - ALLOWED_RECIPE_KEYS
    if unknown_keys:
        raise ValidationError(
            f"Unknown key(s) in recipe file '{recipe_path}': {sorted(unknown_keys)}."
        )

    return recipe_dict


@dataclass(frozen=True)
class ProcessingSettings:
    """Resolved image-processing options for one batch run."""

    black_thresh: int = 0
    white_thresh: int = 255
    dither_thresh: int = 128
    clean_solids: bool = False
    clean_solids_black: int = 35
    clean_solids_white: int = 220
    invert: bool = False
    no_border: bool = False
    denoise_radius: int = 0
    contrast: float = 1.5
    sharpen_radius: float = 2.0
    sharpen_percent: int = 150
    sharpen_threshold: int = 3
    circle_cut: bool = False
    heart_cut: bool = False
    fit_mode: str = 'stretch'
    render_mode: str = 'atkinson'
    silhouette_threshold: int = 128
    ordered_matrix_size: int = 4
    halftone_cell_px: int = 8
    halftone_angle: float = 0.0
    hatch_spacing_px: int = 6
    hatch_angle: float = 45.0
    hatch_cross: bool = False
    edge_threshold: int = 32
    contour_levels: int = 8
    svg_cut: bool = False
    svg_linework: bool = False
    tone_layers: int = 0
    stamp_text: str = None
    stamp_position: str = 'bottom-left'
    stamp_size_px: int = 24
    stamp_margin_px: int = 12
    qr_text: str = None
    qr_position: str = 'bottom-right'
    qr_module_px: int = 4
    qr_margin_px: int = 12
    manifest: bool = False
    material: str = DEFAULT_MATERIAL
    material_thickness_in: float = DEFAULT_MATERIAL_THICKNESS_IN

    def validate(self):
        """Enforce shared invariants across CLI and direct API calls.

        Strictly validates field types, finite numeric values, and valid ranges.
        """
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None and field.default is None:
                continue
            if field.type is float:
                valid = type(value) in (int, float) and math.isfinite(value)
            else:
                valid = type(value) is field.type
            if not valid:
                description = {bool: 'a boolean', int: 'an integer', str: 'a string', float: 'a finite number'}[field.type]
                raise ValidationError(
                    f"Field '{field.name}' must be {description}, "
                    f"got {type(value).__name__} ({value!r})."
                )

        # 5. Range and semantic validation
        if not (0 <= self.black_thresh <= 255):
            raise ValidationError(f"Black threshold '{self.black_thresh}' must be between 0 and 255.")
        if not (0 <= self.white_thresh <= 255):
            raise ValidationError(f"White threshold '{self.white_thresh}' must be between 0 and 255.")
        if self.black_thresh > self.white_thresh:
            raise ValidationError(
                f"Resolved black threshold ({self.black_thresh}) cannot be greater than white threshold ({self.white_thresh})."
            )
        if not (0 <= self.clean_solids_black <= 255):
            raise ValidationError(f"Clean solids black threshold '{self.clean_solids_black}' must be between 0 and 255.")
        if not (0 <= self.clean_solids_white <= 255):
            raise ValidationError(f"Clean solids white threshold '{self.clean_solids_white}' must be between 0 and 255.")
        if self.clean_solids_black > self.clean_solids_white:
            raise ValidationError(
                f"Resolved clean-solids black threshold ({self.clean_solids_black}) cannot be greater than white threshold ({self.clean_solids_white})."
            )
        if not (0 <= self.dither_thresh <= 255):
            raise ValidationError(f"Dither threshold '{self.dither_thresh}' must be between 0 and 255.")
        if self.circle_cut and self.heart_cut:
            raise ValidationError("Cannot apply both --circle-cut and --heart-cut.")
        if self.svg_cut and not (self.circle_cut or self.heart_cut):
            raise ValidationError("--svg-cut requires --circle-cut or --heart-cut.")
        if self.contrast <= 0:
            raise ValidationError(f"Contrast factor '{self.contrast}' must be greater than 0.")
        if self.denoise_radius < 0 or (self.denoise_radius > 0 and (self.denoise_radius < 3 or self.denoise_radius % 2 == 0)):
            raise ValidationError(f"Denoise size '{self.denoise_radius}' must be 0 (off) or an odd integer >= 3.")
        if self.sharpen_radius < 0:
            raise ValidationError(f"Sharpen radius '{self.sharpen_radius}' must be 0 (off) or greater.")
        if self.sharpen_percent < 0:
            raise ValidationError(f"Sharpen percent '{self.sharpen_percent}' must be 0 (off) or greater.")
        if self.sharpen_threshold < 0:
            raise ValidationError(f"Sharpen threshold '{self.sharpen_threshold}' must be 0 or greater.")
        if self.fit_mode not in ('stretch', 'contain', 'cover'):
            raise ValidationError(f"Fit mode '{self.fit_mode}' must be 'stretch', 'contain', or 'cover'.")
        if self.render_mode not in ('atkinson', 'silhouette', 'ordered', 'halftone', 'hatch', 'edge', 'contour'):
            raise ValidationError(
                f"Render mode '{self.render_mode}' must be 'atkinson', 'silhouette', 'ordered', 'halftone', 'hatch', 'edge', or 'contour'."
            )
        if not (0 <= self.silhouette_threshold <= 255):
            raise ValidationError(
                f"Silhouette threshold '{self.silhouette_threshold}' must be between 0 and 255."
            )
        if self.ordered_matrix_size not in (2, 4, 8):
            raise ValidationError("Ordered matrix size must be 2, 4, or 8.")
        if self.halftone_cell_px < 2:
            raise ValidationError("Halftone cell size must be at least 2 pixels.")
        if not 0 <= self.halftone_angle < 180:
            raise ValidationError("Halftone angle must be in the range 0 <= angle < 180.")
        if self.hatch_spacing_px < 2:
            raise ValidationError("Hatch line spacing must be at least 2 pixels.")
        if not 0 <= self.hatch_angle < 180:
            raise ValidationError("Hatch angle must be in the range 0 <= angle < 180.")
        if not 1 <= self.edge_threshold <= 255:
            raise ValidationError("Edge threshold must be between 1 and 255.")
        if not 2 <= self.contour_levels <= 64:
            raise ValidationError("Contour levels must be between 2 and 64.")
        if self.tone_layers not in (0, 2, 3, 4):
            raise ValidationError("Tone layers must be 0 (off) or 2, 3, or 4 registered layers.")
        if self.stamp_text is not None:
            if not self.stamp_text.strip() or '\n' in self.stamp_text or '\r' in self.stamp_text or len(self.stamp_text) > 240:
                raise ValidationError("Stamp text must be non-empty single-line text of at most 240 characters.")
        if self.stamp_position not in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
            raise ValidationError("Stamp position must be top-left, top-right, bottom-left, or bottom-right.")
        if self.stamp_size_px < 6:
            raise ValidationError("Stamp size must be at least 6 pixels.")
        if self.stamp_margin_px < 0:
            raise ValidationError("Stamp margin must be nonnegative.")
        if self.qr_text is not None and not self.qr_text:
            raise ValidationError("QR text must be non-empty when supplied.")
        if self.qr_text is not None and len(self.qr_text.encode('utf-8')) > 17:
            raise ValidationError("QR text must be at most 17 UTF-8 bytes for the version-1/L sidecar.")
        if self.qr_position not in ('top-left', 'top-right', 'bottom-left', 'bottom-right'):
            raise ValidationError("QR position must be top-left, top-right, bottom-left, or bottom-right.")
        if self.qr_module_px < 2:
            raise ValidationError("QR module size must be at least 2 pixels.")
        if self.qr_margin_px < 0:
            raise ValidationError("QR margin must be nonnegative.")
        if not self.material.strip():
            raise ValidationError("--material must contain a descriptive label.")
        if self.material_thickness_in <= 0:
            raise ValidationError("Material thickness must be greater than 0 inches.")



DEFAULTS = asdict(ProcessingSettings())
ALLOWED_RECIPE_KEYS = set(DEFAULTS) | {
    'workflow', 'preset', 'name', 'version', 'description',
}


def validate_limits(width_in, height_in, max_pixels, max_memory, machine):
    for name, value in (('width_in', width_in), ('height_in', height_in)):
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
            raise ValidationError(f'{name} must be a finite positive number.')
    for name, value in (('max_pixels', max_pixels), ('max_memory', max_memory)):
        if (value is not None or name == 'max_pixels') and (type(value) is not int or value <= 0):
            raise ValidationError(f'{name} must be a positive integer.')
    if machine is not None and (not isinstance(machine, str) or machine not in MACHINE_BEDS_IN):
        raise ValidationError(f'Unknown machine: {machine!r}.')


def resolve_settings(args, recipe_dict=None):
    """Resolve defaults < preset < recipe < explicit CLI arguments."""
    if recipe_dict is None and getattr(args, 'recipe', None):
        recipe_dict = load_recipe_file(args.recipe)
    recipe = recipe_dict or {}
    preset_name = getattr(args, 'preset', None) or recipe.get('preset')
    if preset_name is not None and (not isinstance(preset_name, str) or preset_name not in PRESETS):
        raise ValidationError(f'Unknown recipe preset: {preset_name!r}.')
    resolved = {**DEFAULTS, **PRESETS.get(preset_name, {})}
    resolved.update({key: value for key, value in recipe.items() if key in DEFAULTS})
    for field in fields(ProcessingSettings):
        explicit = getattr(args, field.name, None)
        if explicit is not None:
            resolved[field.name] = explicit
    return ProcessingSettings(**resolved)
