"""Versioned maker workflow: burn semantics, registered geometry and visual aids.

Black means burn throughout. Preview pixels never flow back into machine artwork.
All geometry is in 300-DPI pixel coordinates, including fractional vector positions.
"""
from dataclasses import asdict, dataclass
import base64
import hashlib
import io
import json
import math
import os

import numpy as np
from PIL import Image, ImageFilter

from .geometry import circle_cut_bounds, heart_cut_points
from .settings import MACHINE_BEDS_IN, ValidationError

PROFILE_VERSION = 'burn-v1'
APPEARANCE_VERSION = 'maple-v1'
PALETTE = {'engrave': 'embedded monochrome raster', 'score': '#0000ff', 'cut': '#ff0000'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


@dataclass(frozen=True)
class WorkflowOptions:
    svg_operations: bool = False
    score_marks: bool = False
    material_mode: str = 'legacy'
    tone_black: int = 0
    tone_white: int = 255
    tone_gamma: float = 1.0
    preview_finish: bool = False
    preview_seed: int = 0
    preview_spread_mm: float = 0.0
    proof_sheet: bool = False
    client: str = ''
    order: str = ''
    jig: str = None
    blank_width: float = None
    blank_height: float = None
    pocket_clearance: float = None
    kerf: float = 0.0
    jig_margin: float = None
    jig_gap: float = 0.25
    jig_rows: int = 1
    jig_columns: int = 1
    trim: bool = False
    optimize_orientation: bool = False
    engraving_lpi: float = None
    orientation_constraint: str = 'free'

    @property
    def active(self):
        return self != WorkflowOptions()

    @property
    def svg(self):
        return self.svg_operations or self.jig is not None or self.trim

    @property
    def suppress_border(self):
        return self.svg_operations or self.jig is not None

    def record(self):
        return {'version': PROFILE_VERSION, **asdict(self)}

    def validate(self, *, invert=False, svg_cut=False, machine=None):
        for name in ('svg_operations', 'score_marks', 'preview_finish', 'proof_sheet', 'trim', 'optimize_orientation'):
            if type(getattr(self, name)) is not bool:
                raise ValidationError(f'{name} must be boolean.')
        for name in ('tone_black', 'tone_white', 'preview_seed', 'jig_rows', 'jig_columns'):
            if type(getattr(self, name)) is not int:
                raise ValidationError(f'{name} must be an integer.')
        for name in ('tone_gamma', 'preview_spread_mm', 'kerf', 'jig_gap', 'blank_width', 'blank_height', 'pocket_clearance', 'jig_margin', 'engraving_lpi'):
            value = getattr(self, name)
            nullable = name in ('blank_width', 'blank_height', 'pocket_clearance', 'jig_margin', 'engraving_lpi')
            if (value is None and not nullable) or (value is not None and (type(value) not in (int, float) or not math.isfinite(value))):
                raise ValidationError(f'{name} must be finite numeric input.')
        self.validate_tone(invert=invert)
        if not 0 <= self.preview_seed <= 2**32 - 1 or not 0 <= self.preview_spread_mm <= 2:
            raise ValidationError('Preview seed must be 0..2^32-1; spread must be 0..2 mm.')
        if self.score_marks and not self.svg:
            raise ValidationError('--score-marks requires --svg-operations, --jig or --trim.')
        if svg_cut and self.svg:
            raise ValidationError('Use either legacy --svg-cut or the new workflow SVG, not both.')
        if self.proof_sheet or self.preview_finish:
            if self.material_mode == 'lightening' or invert:
                raise ValidationError('Maple preview requires darkening artwork without legacy inversion.')
        if any(not isinstance(getattr(self, n), str) or len(getattr(self, n)) > 240 for n in ('client', 'order')):
            raise ValidationError('Client and order fields must be text of at most 240 characters.')
        if (self.client or self.order) and not self.proof_sheet:
            raise ValidationError('Client/order fields require --proof-sheet.')
        if self.orientation_constraint not in ('free', 'grain', 'reading'):
            raise ValidationError('orientation_constraint must be free, grain or reading.')
        if self.optimize_orientation and (self.engraving_lpi is None or self.engraving_lpi <= 0):
            raise ValidationError('Orientation advice requires positive --engraving-lpi.')
        if self.engraving_lpi is not None and self.engraving_lpi <= 0:
            raise ValidationError('engraving_lpi must be positive.')
        if self.jig is not None:
            if self.jig not in ('circle', 'rectangle'):
                raise ValidationError('Jig shape must be circle or rectangle.')
            if machine not in MACHINE_BEDS_IN:
                raise ValidationError('Jigs require --machine for bed preflight.')
            if any(v is None or v <= 0 for v in (self.blank_width, self.blank_height, self.jig_margin)):
                raise ValidationError('Jigs require measured blank width/height and positive jig margin in inches.')
            if self.pocket_clearance is None or self.pocket_clearance < 0 or self.kerf < 0 or self.jig_gap <= 0:
                raise ValidationError('Supply nonnegative per-side pocket clearance/kerf and positive gap.')
            if self.kerf >= min(self.blank_width, self.blank_height) + 2 * self.pocket_clearance:
                raise ValidationError('Kerf must be smaller than the finished pocket.')
            if self.jig_rows < 1 or self.jig_columns < 1 or self.jig_rows * self.jig_columns > 400:
                raise ValidationError('Jig grid must contain 1..400 pockets.')
            if self.jig == 'circle' and self.blank_width != self.blank_height:
                raise ValidationError('Circular blanks require equal measured width and height.')
        elif (any(v is not None for v in (self.blank_width, self.blank_height, self.pocket_clearance, self.jig_margin))
              or self.kerf or self.jig_rows != 1 or self.jig_columns != 1 or self.jig_gap != 0.25):
            raise ValidationError('Pocket geometry options require --jig.')

    def validate_tone(self, *, invert=False):
        if type(self.tone_black) is not int or type(self.tone_white) is not int:
            raise ValidationError('Tonal levels must be integers.')
        if type(self.tone_gamma) not in (int, float) or not math.isfinite(self.tone_gamma):
            raise ValidationError('Tonal gamma must be a finite number.')
        if self.material_mode not in ('legacy', 'darkening', 'lightening'):
            raise ValidationError('material_mode must be legacy, darkening or lightening.')
        if self.material_mode != 'legacy' and invert:
            raise ValidationError('Explicit material-mode cannot be combined with --invert.')
        if not 0 <= self.tone_black < self.tone_white <= 255 or self.tone_gamma <= 0:
            raise ValidationError('Tonal levels require 0 <= black < white <= 255 and gamma > 0.')
        if self.material_mode == 'legacy' and (self.tone_black, self.tone_white, self.tone_gamma) != (0, 255, 1.0):
            raise ValidationError('Tonal curves require explicit --material-mode.')

    def paths(self, output_path):
        stem = os.path.splitext(output_path)[0]
        paths = {}
        if self.svg:
            paths['operations'] = stem + '_operations.svg'
        if self.preview_finish or self.proof_sheet:
            paths['finish'] = stem + '_finish.png'
        if self.proof_sheet:
            paths['proof'] = stem + '_proof.pdf'
        if self.active:
            paths['workflow'] = stem + '_workflow.json'
        return paths


def layout(options, size, *, machine=None, circle_cut=False):
    w, h = size
    if not options.jig:
        return {'canvas_px': [w, h], 'placements_px': [[0, 0]], 'pockets': []}
    if w / 300 > options.blank_width + 1e-8 or h / 300 > options.blank_height + 1e-8:
        raise ValidationError('Artwork canvas exceeds the measured blank; set explicit artwork dimensions.')
    if options.jig == 'circle' and (not circle_cut or w != h):
        raise ValidationError('Circular jigs require square artwork with --circle-cut to keep burns on the blank.')
    fw = (options.blank_width + 2 * options.pocket_clearance) * 300
    fh = (options.blank_height + 2 * options.pocket_clearance) * 300
    gap, margin, kerf = options.jig_gap * 300, options.jig_margin * 300, options.kerf * 300
    cw = 2 * margin + options.jig_columns * fw + (options.jig_columns - 1) * gap
    ch = 2 * margin + options.jig_rows * fh + (options.jig_rows - 1) * gap
    if machine and (cw / 300 > MACHINE_BEDS_IN[machine][0] or ch / 300 > MACHINE_BEDS_IN[machine][1]):
        raise ValidationError('Jig pockets and margins exceed the nominal machine bed.')
    placements, pockets = [], []
    for row in range(options.jig_rows):
        for column in range(options.jig_columns):
            cx, cy = margin + fw / 2 + column * (fw + gap), margin + fh / 2 + row * (fh + gap)
            placements.append([cx - w / 2, cy - h / 2])
            pockets.append({'center_px': [cx, cy], 'finished_size_px': [fw, fh], 'path_size_px': [fw - kerf, fh - kerf]})
    return {'canvas_px': [cw, ch], 'placements_px': placements, 'pockets': pockets}


def burn_mask(image):
    rgba = np.asarray(image.convert('RGBA'), dtype=np.uint8)
    coverage = ((255 - rgba[:, :, 0].astype(np.uint16)) * rgba[:, :, 3].astype(np.uint16) // 255).astype(np.uint8)
    return Image.fromarray(coverage)


def mask_record(image):
    mask = burn_mask(image)
    return {'sha256': hashlib.sha256(mask.tobytes()).hexdigest(), 'size_px': list(mask.size),
            'bounds_px': list(mask.getbbox()) if mask.getbbox() else None, 'no_engrave': mask.getbbox() is None}


def finish_preview(image, options):
    """Seeded maple grain at 300 DPI; physical spread only affects display."""
    mask = burn_mask(image)
    if options.preview_spread_mm:
        mask = mask.filter(ImageFilter.GaussianBlur(options.preview_spread_mm * 300 / 25.4))
    h, w = image.height, image.width
    # Row-sized arrays avoid large float64 full-image workspace.
    rng = np.random.default_rng(options.preview_seed)
    phase = rng.uniform(0, 2 * np.pi, 3)
    x = np.arange(w, dtype=np.float32) / 300
    result = np.empty((h, w, 3), dtype=np.uint8)
    cov = np.asarray(mask)
    for y in range(h):
        grain = 4 * np.sin(x * 130 + phase[0] + 2 * np.sin(y / 170 + phase[1])) + 2 * np.sin(x * 480 + phase[2])
        substrate = np.clip(np.array([226, 194, 144]) + grain[:, None], 0, 255)
        alpha = cov[y, :, None].astype(np.float32) / 255
        result[y] = np.rint(substrate * (1 - alpha) + np.array([100, 58, 29]) * alpha).astype(np.uint8)
    preview = Image.fromarray(result)
    if image.mode == 'RGBA':
        preview.putalpha(image.getchannel('A'))
    return preview


def appearance_record(options):
    return {'version': APPEARANCE_VERSION, 'seed': options.preview_seed, 'dpi': 300,
            'spread_mm': options.preview_spread_mm, 'mark_rgb': [100, 58, 29],
            'substrate_base_rgb': [226, 194, 144], 'polarity': 'darkening',
            'label': 'Simulated appearance - actual finish varies.'}


def orientation_advice(options, geometry, bounds, machine):
    if not options.optimize_orientation:
        return None
    w, h = geometry['canvas_px']
    if bounds:
        placements = geometry['placements_px']
        bw = bounds[2] - bounds[0] + max(p[0] for p in placements) - min(p[0] for p in placements)
        bh = bounds[3] - bounds[1] + max(p[1] for p in placements) - min(p[1] for p in placements)
    else:
        bw, bh = 0, 0
    bed = MACHINE_BEDS_IN.get(machine)
    rows = []
    for angle in (0, 90):
        cw, ch = (w, h) if angle == 0 else (h, w)
        aw, ah = (bw, bh) if angle == 0 else (bh, bw)
        reasons = []
        if angle and (options.jig or options.orientation_constraint != 'free'):
            reasons.append('Registered jig or grain/reading constraint locks orientation.')
        if bed and (cw / 300 > bed[0] or ch / 300 > bed[1]):
            reasons.append('Canvas exceeds nominal bed.')
        rows.append({'degrees': angle, 'feasible': not reasons, 'reasons': reasons,
                     'canvas_in': [cw / 300, ch / 300], 'burn_bounds_in': [aw / 300, ah / 300],
                     'scan_rows': math.ceil(ah / 300 * options.engraving_lpi), 'sweep_in': aw / 300})
    return {'candidates': rows, 'lpi': options.engraving_lpi, 'timing_calibrated': False,
            'note': 'Geometric scan-row estimates only; no time or savings prediction. No artwork rotated.'}


def render_operations(image, options, geometry, *, circle_cut=False, heart_cut=False):
    width, height = geometry['canvas_px']
    bounds = burn_mask(image).getbbox()
    crop = image.crop(bounds) if options.trim and bounds else image
    offset = bounds[:2] if options.trim and bounds else (0, 0)
    raster = io.BytesIO()
    crop.save(raster, format='PNG', dpi=(300, 300))
    uri = 'data:image/png;base64,' + base64.b64encode(raster.getvalue()).decode('ascii')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width/300:.8f}in" height="{height/300:.8f}in" viewBox="0 0 {width:.8f} {height:.8f}">',
             '<title>Review operations and order in Glowforge before printing</title>', '<g id="engrave">']
    if bounds:
        for x, y in geometry['placements_px']:
            parts.append(f'<image x="{x+offset[0]:.8f}" y="{y+offset[1]:.8f}" width="{crop.width}" height="{crop.height}" href="{uri}" xlink:href="{uri}"/>')
    parts.append('</g><g id="score" fill="none" stroke="#0000ff" stroke-width="1">')
    if options.score_marks:
        # Top-left L mark, inside reserved margin for jigs; intentional scored content otherwise.
        length = min(15, width / 10, height / 10)
        start = min(5, length / 3)
        if options.jig:
            length = min(length, options.jig_margin * 300 / 2)
            start = min(start, length / 3)
        parts.append(f'<path d="M {start} {start+length} V {start} H {start+length}"/>')
    parts.append('</g><g id="cut" fill="none" stroke="#ff0000" stroke-width="1">')
    if options.jig:
        for pocket in geometry['pockets']:
            cx, cy = pocket['center_px']
            pw, ph = pocket['path_size_px']
            if options.jig == 'circle':
                parts.append(f'<circle cx="{cx:.8f}" cy="{cy:.8f}" r="{pw/2:.8f}"/>')
            else:
                parts.append(f'<rect x="{cx-pw/2:.8f}" y="{cy-ph/2:.8f}" width="{pw:.8f}" height="{ph:.8f}"/>')
    elif circle_cut:
        l, t, r, b = circle_cut_bounds(*image.size)
        parts.append(f'<circle cx="{(l+r)/2:.8f}" cy="{(t+b)/2:.8f}" r="{min(r-l,b-t)/2:.8f}"/>')
    elif heart_cut:
        points = ' '.join(f'{x:.8f},{y:.8f}' for x,y in heart_cut_points(*image.size))
        parts.append(f'<polygon points="{points}"/>')
    parts.append('</g></svg>')
    return '\n'.join(parts)


def intended_operations(options, mask, *, cut=False):
    if options.jig:
        return ['cut pockets and optional score (ignore engrave)',
                'secure jig and insert blanks', 'engrave (ignore cuts and score)']
    operations = []
    if not mask['no_engrave']:
        operations.append('engrave')
    if options.score_marks:
        operations.append('score')
    if cut:
        operations.append('cut')
    return operations
