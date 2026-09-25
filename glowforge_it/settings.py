"""Defaults, presets, and resolved processing settings.

Owns the option surface and its precedence rules. Writes no files and prints nothing.
"""

import json
import math
import os
import tomllib
from dataclasses import asdict, dataclass

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
    'coaster': {
        'circle_cut': True
    },
    'coaster-heart': {
        'heart_cut': True
    }
}

DEFAULTS = {
    'black_threshold': 0,
    'white_threshold': 255,
    'dither_threshold': 128,
    'clean_solids': False,
    'clean_solids_black': 35,
    'clean_solids_white': 220,
    'invert': False,
    'no_border': False,
    'denoise': 0,
    'contrast': 1.5,
    'sharpen_radius': 2.0,
    'sharpen_percent': 150,
    'sharpen_threshold': 3,
    'circle_cut': False,
    'heart_cut': False,
    'fit_mode': 'stretch',
    'svg_cut': False,
    'manifest': False,
    'material': DEFAULT_MATERIAL,
    'material_thickness_in': DEFAULT_MATERIAL_THICKNESS_IN,
}


class ValidationError(ValueError):
    """Raised when options or settings violate configuration invariants."""
    pass


ALLOWED_RECIPE_KEYS = {
    'workflow', 'preset', 'black_threshold', 'black_thresh', 'white_threshold', 'white_thresh',
    'dither_threshold', 'dither_thresh', 'clean_solids', 'clean_solids_black',
    'clean_solids_white', 'invert', 'no_border', 'denoise', 'denoise_radius',
    'contrast', 'sharpen_radius', 'sharpen_percent', 'sharpen_threshold',
    'circle_cut', 'heart_cut', 'fit_mode', 'name', 'version', 'description',
    'material', 'material_thickness_in', 'material_thickness', 'manifest', 'svg_cut',
}


def load_recipe_file(recipe_path):
    """Load and validate a TOML or JSON recipe file.

    Rejects unknown keys to prevent silent misconfiguration.
    """
    if not os.path.exists(recipe_path):
        raise FileNotFoundError(f"Recipe file '{recipe_path}' does not exist.")

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

    # Normalize key aliases
    normalized = dict(recipe_dict)
    key_aliases = {
        'black_thresh': 'black_threshold',
        'white_thresh': 'white_threshold',
        'dither_thresh': 'dither_threshold',
        'denoise_radius': 'denoise',
        'material_thickness': 'material_thickness_in',
    }
    for alias, canonical in key_aliases.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized.pop(alias)

    return normalized


@dataclass(frozen=True)
class ProcessingSettings:
    """Resolved image-processing options for one batch run."""

    black_threshold: int = DEFAULTS['black_threshold']
    white_threshold: int = DEFAULTS['white_threshold']
    dither_threshold: int = DEFAULTS['dither_threshold']
    clean_solids: bool = DEFAULTS['clean_solids']
    clean_solids_black: int = DEFAULTS['clean_solids_black']
    clean_solids_white: int = DEFAULTS['clean_solids_white']
    invert: bool = DEFAULTS['invert']
    no_border: bool = DEFAULTS['no_border']
    denoise: int = DEFAULTS['denoise']
    contrast: float = DEFAULTS['contrast']
    sharpen_radius: float = DEFAULTS['sharpen_radius']
    sharpen_percent: int = DEFAULTS['sharpen_percent']
    sharpen_threshold: int = DEFAULTS['sharpen_threshold']
    circle_cut: bool = DEFAULTS['circle_cut']
    heart_cut: bool = DEFAULTS['heart_cut']
    fit_mode: str = DEFAULTS['fit_mode']
    svg_cut: bool = DEFAULTS['svg_cut']
    manifest: bool = DEFAULTS['manifest']
    material: str = DEFAULTS['material']
    material_thickness_in: float = DEFAULTS['material_thickness_in']

    def validate(self, svg_cut=None, material=None, material_thickness_in=None):
        """Enforce shared invariants across CLI and direct API calls.

        Strictly validates field types, finite numeric values, and valid ranges.
        """
        effective_svg_cut = self.svg_cut if svg_cut is None else svg_cut
        effective_material = self.material if material is None else material
        effective_thickness = self.material_thickness_in if material_thickness_in is None else material_thickness_in

        # 1. Type validation for boolean fields
        bool_fields = {
            'clean_solids': self.clean_solids,
            'invert': self.invert,
            'no_border': self.no_border,
            'circle_cut': self.circle_cut,
            'heart_cut': self.heart_cut,
            'svg_cut': effective_svg_cut,
            'manifest': self.manifest,
        }
        for name, val in bool_fields.items():
            if type(val) is not bool:
                raise ValidationError(f"Field '{name}' must be a boolean (True/False), got {type(val).__name__} ({val!r}).")

        # 2. Type validation for integer fields (in Python, bool is a subclass of int, so reject bool)
        int_fields = {
            'black_threshold': self.black_threshold,
            'white_threshold': self.white_threshold,
            'dither_threshold': self.dither_threshold,
            'clean_solids_black': self.clean_solids_black,
            'clean_solids_white': self.clean_solids_white,
            'denoise': self.denoise,
            'sharpen_percent': self.sharpen_percent,
            'sharpen_threshold': self.sharpen_threshold,
        }
        for name, val in int_fields.items():
            if type(val) is not int or isinstance(val, bool):
                raise ValidationError(f"Field '{name}' must be an integer, got {type(val).__name__} ({val!r}).")

        # 3. Type and finiteness validation for float/numeric fields
        numeric_fields = {
            'contrast': self.contrast,
            'sharpen_radius': self.sharpen_radius,
            'material_thickness_in': effective_thickness,
        }
        for name, val in numeric_fields.items():
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
                raise ValidationError(f"Field '{name}' must be a finite number, got {type(val).__name__} ({val!r}).")

        # 4. String field validation
        if not isinstance(self.fit_mode, str):
            raise ValidationError(f"Field 'fit_mode' must be a string, got {type(self.fit_mode).__name__}.")
        if not isinstance(effective_material, str):
            raise ValidationError(f"Field 'material' must be a string, got {type(effective_material).__name__}.")

        # 5. Range and semantic validation
        if not (0 <= self.black_threshold <= 255):
            raise ValidationError(f"Black threshold '{self.black_threshold}' must be between 0 and 255.")
        if not (0 <= self.white_threshold <= 255):
            raise ValidationError(f"White threshold '{self.white_threshold}' must be between 0 and 255.")
        if self.black_threshold > self.white_threshold:
            raise ValidationError(
                f"Resolved black threshold ({self.black_threshold}) cannot be greater than white threshold ({self.white_threshold})."
            )
        if not (0 <= self.clean_solids_black <= 255):
            raise ValidationError(f"Clean solids black threshold '{self.clean_solids_black}' must be between 0 and 255.")
        if not (0 <= self.clean_solids_white <= 255):
            raise ValidationError(f"Clean solids white threshold '{self.clean_solids_white}' must be between 0 and 255.")
        if self.clean_solids_black > self.clean_solids_white:
            raise ValidationError(
                f"Resolved clean-solids black threshold ({self.clean_solids_black}) cannot be greater than white threshold ({self.clean_solids_white})."
            )
        if not (0 <= self.dither_threshold <= 255):
            raise ValidationError(f"Dither threshold '{self.dither_threshold}' must be between 0 and 255.")
        if self.circle_cut and self.heart_cut:
            raise ValidationError("Cannot apply both --circle-cut and --heart-cut.")
        if effective_svg_cut and not (self.circle_cut or self.heart_cut):
            raise ValidationError("--svg-cut requires --circle-cut, --heart-cut, or a coaster preset.")
        if self.contrast <= 0:
            raise ValidationError(f"Contrast factor '{self.contrast}' must be greater than 0.")
        if self.denoise < 0 or (self.denoise > 0 and (self.denoise < 3 or self.denoise % 2 == 0)):
            raise ValidationError(f"Denoise size '{self.denoise}' must be 0 (off) or an odd integer >= 3.")
        if self.sharpen_radius < 0:
            raise ValidationError(f"Sharpen radius '{self.sharpen_radius}' must be 0 (off) or greater.")
        if self.sharpen_percent < 0:
            raise ValidationError(f"Sharpen percent '{self.sharpen_percent}' must be 0 (off) or greater.")
        if self.sharpen_threshold < 0:
            raise ValidationError(f"Sharpen threshold '{self.sharpen_threshold}' must be 0 or greater.")
        if self.fit_mode not in ('stretch', 'contain', 'cover'):
            raise ValidationError(f"Fit mode '{self.fit_mode}' must be 'stretch', 'contain', or 'cover'.")
        if not str(effective_material).strip():
            raise ValidationError("--material must contain a descriptive label.")
        if effective_thickness <= 0:
            raise ValidationError("Material thickness must be greater than 0 inches.")

    def transform_kwargs(self):
        """Translate stable CLI names to the image function's legacy API."""
        values = asdict(self)
        values['black_thresh'] = values.pop('black_threshold')
        values['white_thresh'] = values.pop('white_threshold')
        values['dither_thresh'] = values.pop('dither_threshold')
        values['denoise_radius'] = values.pop('denoise')
        # Remove batch/output-level options that are not transform_image kwargs
        values.pop('svg_cut', None)
        values.pop('manifest', None)
        values.pop('material', None)
        values.pop('material_thickness_in', None)
        return values


def resolve_settings(args, recipe_dict=None):
    """Resolve defaults, preset values, user recipe file, then explicit CLI overrides.

    Precedence:
        1. DEFAULTS
        2. Preset values
        3. Recipe file values
        4. Explicit CLI arguments
    """
    if recipe_dict is None and hasattr(args, 'recipe') and args.recipe:
        recipe_dict = load_recipe_file(args.recipe)
    recipe = recipe_dict or {}

    preset_name = getattr(args, 'preset', None) or recipe.get('preset')
    if preset_name is not None and (not isinstance(preset_name, str) or preset_name not in PRESETS):
        raise ValidationError(f'Unknown recipe preset: {preset_name!r}.')
    preset = PRESETS.get(preset_name, {}) if preset_name else {}

    fields = (
        ('black_threshold', 'black_threshold', 'black_thresh', 'black_threshold'),
        ('white_threshold', 'white_threshold', 'white_thresh', 'white_threshold'),
        ('dither_threshold', 'dither_threshold', 'dither_thresh', 'dither_threshold'),
        ('clean_solids', 'clean_solids', 'clean_solids', 'clean_solids'),
        ('clean_solids_black', 'clean_solids_black', 'clean_solids_black', 'clean_solids_black'),
        ('clean_solids_white', 'clean_solids_white', 'clean_solids_white', 'clean_solids_white'),
        ('invert', 'invert', 'invert', 'invert'),
        ('no_border', 'no_border', 'no_border', 'no_border'),
        ('denoise', 'denoise', 'denoise_radius', 'denoise'),
        ('contrast', 'contrast', 'contrast', 'contrast'),
        ('sharpen_radius', 'sharpen_radius', 'sharpen_radius', 'sharpen_radius'),
        ('sharpen_percent', 'sharpen_percent', 'sharpen_percent', 'sharpen_percent'),
        ('sharpen_threshold', 'sharpen_threshold', 'sharpen_threshold', 'sharpen_threshold'),
        ('circle_cut', 'circle_cut', 'circle_cut', 'circle_cut'),
        ('heart_cut', 'heart_cut', 'heart_cut', 'heart_cut'),
        ('fit_mode', 'fit_mode', None, 'fit_mode'),
        ('svg_cut', 'svg_cut', None, 'svg_cut'),
        ('manifest', 'manifest', None, 'manifest'),
        ('material', 'material', None, 'material'),
        ('material_thickness_in', 'material_thickness', None, 'material_thickness_in'),
    )
    resolved = {}
    for field, argument, preset_key, default_key in fields:
        explicit = getattr(args, argument, None) if hasattr(args, argument) else None
        if explicit is not None:
            resolved[field] = explicit
        elif field in recipe:
            resolved[field] = recipe[field]
        elif preset_key is not None and preset_key in preset:
            resolved[field] = preset[preset_key]
        else:
            resolved[field] = DEFAULTS[default_key]
    return ProcessingSettings(**resolved)
