"""Resolving every source and destination before anything is published.

Source discovery and identity, the destination namespace, containment against the output
root and the input trees, and structural file/directory conflicts. Publishes nothing.
"""

import os
import tempfile
import unicodedata
from dataclasses import dataclass

from .geometry import output_geometry
from .settings import DEFAULT_MAX_PIXELS, DEFAULTS, PRESETS

SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff', '.gif')

@dataclass(frozen=True)
class PlannedJob:
    """One source and the complete set of files it will publish."""

    input_path: str
    output_path: str
    svg_path: str = None

    @property
    def destinations(self):
        return [self.output_path] + ([self.svg_path] if self.svg_path else [])

def _is_within(path, root):
    """True when an already-resolved path is root itself or lies beneath it."""
    try:
        return path == root or os.path.commonpath((root, path)) == root
    except ValueError:  # different drives on Windows
        return False

def _ancestors_within(target_dir, output_dir):
    """Every directory that must exist between the output root (exclusive) and target_dir."""
    paths = []
    current = os.path.abspath(target_dir)
    stop = os.path.abspath(output_dir)
    while current != stop:
        paths.append(current)
        parent = os.path.dirname(current)
        if parent == current:  # ran past the root; the containment check already rejected this
            return []
        current = parent
    return list(reversed(paths))

def _file_identity(path):
    """Inode identity, which survives symlinks and hard links. None when path is absent."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (status.st_dev, status.st_ino)

def _destination_folds_case(directory):
    """Probe whether the output filesystem folds case, so collisions are caught before writing."""
    try:
        fd, probe = tempfile.mkstemp(prefix='.gf-case-', dir=directory)
    except OSError:
        return True  # ponytail: unknown filesystem, assume folding (the conservative answer)
    os.close(fd)
    try:
        return os.path.exists(probe.replace('.gf-case-', '.GF-CASE-'))
    finally:
        os.unlink(probe)

def _destination_key(path, folds_case):
    """Namespace key for collision detection on the destination filesystem."""
    key = os.path.realpath(path)
    if folds_case:
        # Compare the way the filesystem does: NFC for composed/decomposed Unicode, casefold for case.
        key = unicodedata.normalize('NFC', key).casefold()
    return key

def discover_sources(input_path, errors):
    """Return supported image files under one input path, recording any traversal failure."""
    if not os.path.exists(input_path):
        errors.append(f"Input path '{input_path}' does not exist.")
        return []

    if os.path.isdir(input_path):
        found = []

        def on_walk_error(exc):
            errors.append(f"Cannot read '{getattr(exc, 'filename', input_path)}': {exc}")

        for root, dirs, filenames in os.walk(input_path, onerror=on_walk_error):
            dirs.sort()
            found.extend(
                os.path.join(root, filename)
                for filename in sorted(filenames)
                if filename.lower().endswith(SUPPORTED_EXTENSIONS)
            )
        if not found:
            errors.append(f"No supported images found in '{input_path}'.")
        return found

    if input_path.lower().endswith(SUPPORTED_EXTENSIONS):
        return [input_path]

    errors.append(f"Input path '{input_path}' is not a directory or supported image file.")
    return []

def settings_suffix(values, preset_dict, preset_name, svg_cut):
    """Encode the settings that differ from the preset (or defaults) as filename tags."""
    baseline = {
        'black_thresh': DEFAULTS['black_threshold'],
        'white_thresh': DEFAULTS['white_threshold'],
        'dither_thresh': DEFAULTS['dither_threshold'],
        'clean_solids': DEFAULTS['clean_solids'],
        'clean_solids_black': DEFAULTS['clean_solids_black'],
        'clean_solids_white': DEFAULTS['clean_solids_white'],
        'invert': DEFAULTS['invert'],
        'no_border': DEFAULTS['no_border'],
        'denoise_radius': DEFAULTS['denoise'],
        'contrast': DEFAULTS['contrast'],
        'sharpen_radius': DEFAULTS['sharpen_radius'],
        'sharpen_percent': DEFAULTS['sharpen_percent'],
        'sharpen_threshold': DEFAULTS['sharpen_threshold'],
        'circle_cut': DEFAULTS['circle_cut'],
        'heart_cut': DEFAULTS['heart_cut'],
        'fit_mode': DEFAULTS['fit_mode'],
    }
    baseline.update(preset_dict)

    tags = []
    if preset_name:
        tags.append(f"pr{preset_name}")
    tag_formats = {
        'black_thresh': lambda value: f"b{value}",
        'white_thresh': lambda value: f"W{value}",
        'dither_thresh': lambda value: f"d{value}",
        'invert': lambda value: 'inv' if value else 'noinv',
        'no_border': lambda value: 'nb' if value else 'border',
        'denoise_radius': lambda value: f"dn{value}",
        'contrast': lambda value: f"c{value:g}",
        'fit_mode': lambda value: f"fit{value}",
    }
    for key, formatter in tag_formats.items():
        if values[key] != baseline[key]:
            tags.append(formatter(values[key]))
    if values['clean_solids'] != baseline['clean_solids']:
        tags.append('clean' if values['clean_solids'] else 'noclean')
    if values['clean_solids'] and (
        values['clean_solids_black'] != baseline['clean_solids_black']
        or values['clean_solids_white'] != baseline['clean_solids_white']
    ):
        tags.append(f"csb{values['clean_solids_black']}w{values['clean_solids_white']}")
    if any(values[key] != baseline[key] for key in ('sharpen_radius', 'sharpen_percent', 'sharpen_threshold')):
        tags.append(
            f"sh{values['sharpen_radius']:g}p{values['sharpen_percent']}t{values['sharpen_threshold']}"
        )
    if values['circle_cut'] != baseline['circle_cut']:
        tags.append('cc' if values['circle_cut'] else 'nocc')
    if values['heart_cut'] != baseline['heart_cut']:
        tags.append('hc' if values['heart_cut'] else 'nohc')
    if svg_cut:
        tags.append('svg')

    return '_'.join(tags) if tags else 'dithered'

def plan_batch(
    input_paths,
    output_dir,
    values,
    preset_name=None,
    width_in=None,
    height_in=None,
    svg_cut=False,
    max_pixels=DEFAULT_MAX_PIXELS,
    machine=None,
    existing='overwrite',
):
    """Resolve every source and destination before anything is written.

    Returns (jobs, errors). A non-empty errors list means nothing should be published:
    a destination that overlaps a source, escapes the output root, or collides with
    another destination is a whole-batch problem, not a per-file one.
    """
    errors = []
    if existing not in ('overwrite', 'skip', 'error'):
        return [], [f"Unsupported existing-output policy '{existing}'."]

    sources = []
    seen_sources = set()
    for input_path in input_paths:
        for source in discover_sources(input_path, errors):
            real = os.path.realpath(source)
            if real in seen_sources:
                continue
            seen_sources.add(real)
            sources.append((input_path, source))
    if errors:
        return [], errors
    if not sources:
        return [], ["No supported images found in the selected inputs."]

    # Every identity a source can be reached by: resolved path and inode (hard links included).
    source_realpaths = {os.path.realpath(source) for _, source in sources}
    source_ids = {identity for _, source in sources if (identity := _file_identity(source))}

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as exc:
        return [], [f"Cannot use output directory '{output_dir}': {exc}"]

    output_root = os.path.realpath(output_dir)
    input_roots = {os.path.realpath(p): p for p in input_paths if os.path.isdir(p)}
    for input_root, input_path in input_roots.items():
        if _is_within(output_root, input_root):
            errors.append(
                f"Output directory '{output_dir}' is inside input directory '{input_path}'. "
                "Choose a separate output directory to avoid reprocessing generated images."
            )
    if errors:
        return [], errors

    folds_case = _destination_folds_case(output_dir)
    preset_dict = PRESETS.get(preset_name, {}) if preset_name else {}
    settings_str = settings_suffix(values, preset_dict, preset_name, svg_cut)

    jobs = []
    claimed = {}
    required_dirs = {}
    for input_path, source in sources:
        filename = os.path.basename(source)
        name, ext = os.path.splitext(filename)

        try:
            dim_suffix = output_geometry(source, width_in, height_in, max_pixels, machine)
        except Exception as exc:
            errors.append(f"{source}: {exc}")
            continue

        output_filename = f"{name}_{ext.lstrip('.').lower()}_{settings_str}{dim_suffix}.png"
        if os.path.isdir(input_path):
            rel_dir = os.path.dirname(os.path.relpath(source, start=input_path))
            target_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
        else:
            target_dir = output_dir

        # A symlinked or traversing parent must not redirect writes out of the output root...
        target_real = os.path.realpath(target_dir)
        if not _is_within(target_real, output_root):
            errors.append(
                f"{source}: destination folder '{target_dir}' resolves to '{target_real}', "
                f"outside the output root '{output_root}'."
            )
            continue

        # ...nor into a selected input tree. Staying inside the output root is not enough
        # when an input directory is itself beneath that root: a symlinked destination
        # folder would then deposit generated artwork among the sources, where a later
        # recursive run would ingest it.
        invaded = next(
            (path for root, path in input_roots.items() if _is_within(target_real, root)), None)
        if invaded is not None:
            errors.append(
                f"{source}: destination folder '{target_dir}' resolves to '{target_real}', "
                f"inside input directory '{invaded}'. Generated files must not enter a source tree."
            )
            continue

        # Every folder this job needs must be creatable: no existing non-directory on the
        # way down, and no other job planning to publish a file at one of those paths.
        conflicting_parent = next(
            (path for path in _ancestors_within(target_dir, output_dir)
             if os.path.lexists(path) and not os.path.isdir(path)), None)
        if conflicting_parent is not None:
            errors.append(
                f"{source}: destination folder '{target_dir}' needs '{conflicting_parent}' "
                "to be a directory, but a file already exists there."
            )
            continue
        for path in _ancestors_within(target_dir, output_dir):
            required_dirs.setdefault(_destination_key(path, folds_case), (path, source))

        output_path = os.path.join(target_dir, output_filename)
        job = PlannedJob(
            input_path=source,
            output_path=output_path,
            svg_path=f"{os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else None,
        )

        def hits_a_source(destination):
            if os.path.realpath(destination) in source_realpaths:
                return True
            identity = _file_identity(destination)
            return identity is not None and identity in source_ids

        clobbered = [d for d in job.destinations if hits_a_source(d)]
        if clobbered:
            errors.append(
                f"{source}: would overwrite input file(s) {clobbered}. "
                "Choose an output folder that holds no source images."
            )
            continue

        collided = False
        for destination in job.destinations:
            key = _destination_key(destination, folds_case)
            other = claimed.get(key)
            if other is not None:
                errors.append(
                    f"'{source}' and '{other}' both map to '{destination}'"
                    f"{' (this filesystem ignores case)' if folds_case else ''}. "
                    "Rename or separate the inputs."
                )
                collided = True
                break
            claimed[key] = source
        if collided:
            continue

        present = [path for path in job.destinations if os.path.exists(path)]
        if present:
            if existing == 'error':
                errors.append(f"{source}: output already exists: {present}")
                continue
            if existing == 'skip':
                if len(present) != len(job.destinations):
                    errors.append(
                        f"{source}: incomplete existing output set {present}. Repair or remove it, "
                        "or rerun with --existing overwrite."
                    )
                else:
                    print(f"Skipping existing output set: {job.destinations}")
                continue

        jobs.append(job)

    for key, (path, needed_by) in required_dirs.items():
        published_by = claimed.get(key)
        if published_by is not None:
            errors.append(
                f"'{published_by}' publishes a file at '{path}', which '{needed_by}' needs as a "
                "directory. Rename or separate the inputs."
            )

    return jobs, errors
