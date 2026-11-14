"""Shared job contracts: artifact names, resource bounds and stable source bytes."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from importlib.metadata import PackageNotFoundError, version
import hashlib
import os
from pathlib import Path
import sys
import tempfile

from PIL import Image

from .geometry import resolve_oriented_geometry, rotated_size
from .publication import sha256_file
from .settings import DEFAULT_MAX_PIXELS, ProcessingSettings, ValidationError, __version__, validate_limits
from .workflow import WorkflowOptions, layout


def runtime_identity():
    libraries = {}
    for name in ('numpy', 'pillow', 'segno', 'reportlab'):
        try:
            libraries[name] = version(name)
        except PackageNotFoundError:
            libraries[name] = None
    source = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob('*.py')):
        source.update(path.name.encode('utf-8') + b'\0' + path.read_bytes() + b'\0')
    return {'engine': __version__, 'source_sha256': source.hexdigest(),
            'python': sys.version.split()[0], 'libraries': libraries}


def artifact_settings(settings, workflow):
    """Validate before expansion and require integrity records for new sidecars."""
    settings.validate()
    required = (settings.manifest or workflow.active or settings.svg_linework
                or settings.tone_layers != 0 or settings.stamp_text is not None
                or settings.qr_text is not None)
    return replace(settings, manifest=required)


def artifact_paths(output_path, settings, workflow, manifest_path=None):
    """The complete destination set, shared by planning and direct export."""
    settings = artifact_settings(settings, workflow)
    output_path = os.fspath(output_path)
    stem = os.path.splitext(output_path)[0]
    paths = {'primary': output_path, **workflow.paths(output_path)}
    if settings.svg_cut:
        paths['cut'] = stem + '_cut.svg'
    if settings.svg_linework:
        paths['linework'] = stem + '_linework.svg'
    for index in range(1, settings.tone_layers + 1):
        paths[f'tone_layer_{index}'] = f'{stem}_tone{index:02d}of{settings.tone_layers}.png'
    for role, text in (('stamp', settings.stamp_text), ('qr', settings.qr_text)):
        if text is not None:
            paths[role] = f'{stem}_{role}.png'
    if settings.manifest or workflow.active:
        paths['manifest'] = os.fspath(manifest_path) if manifest_path else stem + '_manifest.json'
        if os.path.realpath(os.path.dirname(os.path.abspath(paths['manifest']))) != os.path.realpath(os.path.dirname(os.path.abspath(output_path))):
            raise ValidationError('Manifest must be adjacent to its output artifacts.')
    return paths


def guard_unmanifested_output(paths, manifest_path=None):
    """Protect existing manifest-backed artwork from a plain export."""
    if 'manifest' in paths:
        return ()
    default_manifest = os.path.splitext(paths['primary'])[0] + '_manifest.json'
    # An explicit manifest can also be supplied by a direct export caller.
    candidates = [default_manifest]
    if manifest_path and os.path.realpath(os.path.dirname(manifest_path)) == os.path.realpath(os.path.dirname(default_manifest)):
        candidates.append(os.fspath(manifest_path))
    for candidate in candidates:
        if os.path.lexists(candidate):
            raise ValidationError(
                f"Existing manifest '{candidate}' belongs to this output name. "
                "Keep --manifest to verify or replace the complete job, or choose a different output."
            )
    return candidates


def source_relpath(source, record):
    """Resolve source and record paths the same way during writing and replay."""
    directory = os.path.realpath(os.path.dirname(os.path.abspath(record)))
    return os.path.relpath(os.path.realpath(source), directory)


def validate_combination(settings, workflow):
    # Tone bands are alternative material/operation assignments, not the primary
    # mask. A single simulated finish cannot truthfully preview all assignments.
    if settings.tone_layers and (workflow.preview_finish or workflow.proof_sheet):
        raise ValidationError('Tone layers require separate material/operation review; omit --preview-finish/--proof-sheet or export a selected layer separately.')
    if workflow.jig and (settings.stamp_text is not None or settings.qr_text is not None or settings.tone_layers or settings.svg_linework):
        raise ValidationError('Jig replication currently supports the primary engraving only; personalization, tone layers and linework require a separate non-jig job.')


def working_memory(orig_w, orig_h, width, height, settings=None, workflow=None, *, max_pixels=DEFAULT_MAX_PIXELS, placements=1):
    settings = settings or ProcessingSettings()
    workflow = workflow or WorkflowOptions()
    pixels = width * height
    padding = (width + 3) * (height + 2) - pixels
    estimate = 32*orig_w*orig_h + 80*pixels + 16*padding + 1024*1024
    if settings.denoise_radius:
        kernel = settings.denoise_radius
        # Pillow expands the L source before applying its rank filter. The
        # kernel scratch can use up to four bytes per sample.
        expanded = (orig_w + kernel - 1) * (orig_h + kernel - 1)
        if expanded > max_pixels:
            raise ValidationError(f'Denoise intermediate has {expanded:,} pixels; configured limit is {max_pixels:,}. Reduce --denoise or the source dimensions.')
        estimate += expanded + 4*kernel**2
    if settings.render_mode == 'halftone':
        rw, rh = rotated_size(width, height, settings.halftone_angle)
        if rw*rh > max_pixels:
            raise ValidationError(f'Rotated halftone intermediate has up to {rw*rh:,} pixels; configured limit is {max_pixels:,}. Reduce dimensions or angle.')
        estimate += 24*rw*rh
    if settings.svg_linework:
        # trace_skeleton has a matching foreground point ceiling.
        estimate += 48*pixels + 2048*min(pixels, 250_000)
    estimate += pixels * (8*settings.tone_layers + 16*(settings.stamp_text is not None) + 16*(settings.qr_text is not None))
    if workflow.active:
        estimate += pixels*(64 + 16*placements) + 4*1024*1024
    return estimate


def preflight_source(path, settings, workflow, *, width_in=None, height_in=None, max_pixels=DEFAULT_MAX_PIXELS, max_memory=None, machine=None):
    settings.validate()
    workflow.validate(invert=settings.invert, svg_cut=settings.svg_cut, machine=machine)
    validate_combination(settings, workflow)
    validate_limits(width_in, height_in, max_pixels, max_memory, machine)
    ow, oh, w, h, suffix = resolve_oriented_geometry(path, width_in, height_in, max_pixels, machine)
    geometry = layout(workflow, (w, h), machine=machine, circle_cut=settings.circle_cut)
    estimated = working_memory(ow, oh, w, h, settings, workflow, max_pixels=max_pixels, placements=len(geometry['placements_px']))
    if max_memory is not None and estimated > max_memory:
        raise ValidationError(f'Estimated memory ({estimated / 1024 / 1024:.1f} MB) exceeds budget ({max_memory / 1024 / 1024:.1f} MB). Reduce dimensions or increase --max-memory.')
    return (ow, oh, w, h, suffix), geometry, estimated


def protect_source(source, destinations):
    """Direct exports must never replace a source or alias two artifacts."""
    claimed = set()
    source_real = os.path.realpath(source)
    for destination in destinations:
        resolved = os.path.realpath(destination)
        # Conservative across case-sensitive and case-insensitive filesystems.
        key = resolved.casefold()
        if key in claimed:
            raise ValidationError('Artifact destinations must be distinct.')
        claimed.add(key)
        if resolved == source_real or (os.path.exists(destination) and os.path.samefile(source, destination)):
            raise ValidationError(f"Output '{destination}' would overwrite the source image.")
        if os.path.isdir(destination):
            raise IsADirectoryError(f"Destination '{destination}' is an existing directory.")


@dataclass(frozen=True)
class SourceSnapshot:
    path: str
    sha256: str
    original_size: list
    mode: str

    def require_unchanged(self, source):
        if sha256_file(source) != self.sha256:
            raise ValidationError('Source changed during processing; no new generation was published. Retry with a stable source file.')


@contextmanager
def snapshot_source(source, expected_sha256=None):
    """Stream to private temporary storage; every consumer uses these exact bytes."""
    with tempfile.TemporaryDirectory(prefix='gf-source-') as directory:
        path = os.path.join(directory, 'source' + os.path.splitext(source)[1])
        hasher = hashlib.sha256()
        with open(source, 'rb') as src, open(path, 'wb') as dst:
            before = os.fstat(src.fileno())
            while chunk := src.read(65536):
                hasher.update(chunk)
                dst.write(chunk)
            after = os.fstat(src.fileno())
        fingerprint = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if fingerprint(before) != fingerprint(after):
            raise ValidationError('Source changed while taking a snapshot; retry with a stable file.')
        digest = hasher.hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValidationError('Source changed after planning; rerun the job.')
        with Image.open(path) as image:
            snapshot = SourceSnapshot(path, digest, list(image.size), image.mode)
        snapshot.require_unchanged(source)
        yield snapshot
