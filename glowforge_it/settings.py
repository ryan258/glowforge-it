"""Defaults, presets, and resolved processing settings.

Owns the option surface and its precedence rules. Writes no files and prints nothing.
"""

from dataclasses import asdict, dataclass

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
    'fit_mode': 'stretch'
}

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

    def transform_kwargs(self):
        """Translate stable CLI names to the image function's legacy API."""
        values = asdict(self)
        values['black_thresh'] = values.pop('black_threshold')
        values['white_thresh'] = values.pop('white_threshold')
        values['dither_thresh'] = values.pop('dither_threshold')
        values['denoise_radius'] = values.pop('denoise')
        return values

def resolve_settings(args):
    """Resolve defaults, preset values, then explicit CLI overrides."""
    preset = PRESETS.get(args.preset, {}) if args.preset else {}
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
    )
    resolved = {}
    for field, argument, preset_key, default_key in fields:
        explicit = getattr(args, argument)
        if explicit is not None:
            resolved[field] = explicit
        elif preset_key is not None and preset_key in preset:
            resolved[field] = preset[preset_key]
        else:
            resolved[field] = DEFAULTS[default_key]
    return ProcessingSettings(**resolved)
