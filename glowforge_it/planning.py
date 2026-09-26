"""Resolving every source and destination before anything is published.

Source discovery and identity, the destination namespace, containment against the output
root and the input trees, and structural file/directory conflicts. Publishes nothing.
"""

import json
import os
import re
import tempfile
import time
import unicodedata
from dataclasses import asdict, dataclass, replace

from .geometry import resolve_oriented_geometry
from .publication import sha256_file
from .workflow import WorkflowOptions, layout, digest
from .settings import DEFAULT_MAX_PIXELS, DEFAULTS, PRESETS

SUPPORTED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tif', '.tiff', '.gif')


@dataclass(frozen=True)
class PlannedJob:
    """One source and the complete set of files it will publish."""

    input_path: str
    output_path: str
    svg_path: str = None
    manifest_path: str = None
    estimated_memory_bytes: int = 0
    output_size: tuple = None
    is_skipped: bool = False
    skip_reason: str = None
    values: dict = None
    preset_name: str = None
    artifacts: dict = None
    workflow_geometry: dict = None

    @property
    def destinations(self):
        dests = [self.output_path]
        if self.svg_path:
            dests.append(self.svg_path)
        if self.manifest_path:
            dests.append(self.manifest_path)
        dests.extend((self.artifacts or {}).values())
        return dests


@dataclass(frozen=True)
class JobOutcome:
    """Outcome for a single input item in a batch."""

    input_path: str
    output_path: str
    svg_path: str = None
    manifest_path: str = None
    status: str = 'written'  # 'written', 'skipped', 'failed', 'planned'
    error_category: str = None  # 'planning_error', 'validation_error', 'transform_error', 'publication_error'
    error_message: str = None
    duration_seconds: float = 0.0
    output_size: tuple = None
    estimated_memory_bytes: int = None
    artifacts: dict = None
    workflow_summary: dict = None

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass(frozen=True)
class BatchResult:
    """Structured result of planning and executing a batch."""

    items: list
    written_count: int
    skipped_count: int
    failed_count: int
    total_planned: int
    exit_code: int
    errors: list
    duration_seconds: float = 0.0
    is_dry_run: bool = False

    @classmethod
    def from_items(cls, items, errors, exit_code, start_time, is_dry_run):
        return cls(
            items=list(items),
            written_count=sum(item.status == 'written' for item in items),
            skipped_count=sum(item.status == 'skipped' for item in items),
            failed_count=sum(item.status == 'failed' for item in items),
            total_planned=len(items), exit_code=exit_code, errors=list(errors),
            duration_seconds=round(time.time() - start_time, 2), is_dry_run=is_dry_run,
        )

    def __bool__(self):
        return self.exit_code == 0

    def to_dict(self):
        return {
            'success': self.exit_code == 0,
            'exit_code': self.exit_code,
            'is_dry_run': self.is_dry_run,
            'summary': {
                'written': self.written_count,
                'skipped': self.skipped_count,
                'failed': self.failed_count,
                'total_planned': self.total_planned,
            },
            'duration_seconds': self.duration_seconds,
            'errors': self.errors,
            'items': [item.to_dict() if hasattr(item, 'to_dict') else item for item in self.items],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent)


def _is_within(path, root):
    """True when an already-resolved path is root itself or lies beneath it."""
    try:
        return path == root or os.path.commonpath((root, path)) == root
    except ValueError:  # different drives on Windows
        return False


def _existing_parent(path):
    """Return the nearest existing ancestor without creating anything."""
    current = os.path.abspath(path)
    while not os.path.lexists(current):
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return current


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


def _destination_folds_case(directory, dry_run=False):
    """Probe whether the output filesystem folds case, so collisions are caught before writing.

    In dry-run mode, no probe files are created on disk; conservative folding is assumed.
    """
    if dry_run:
        return True

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


def estimate_image_memory(source_path, width_in=None, height_in=None, max_pixels=DEFAULT_MAX_PIXELS):
    """Estimate image working buffers, not total process RSS; invalid inputs raise."""
    orig_w, orig_h, target_w, target_h, _ = resolve_oriented_geometry(
        source_path, width_in=width_in, height_in=height_in, max_pixels=max_pixels
    )
    return _working_memory_bytes(orig_w, orig_h, target_w, target_h)


def _working_memory_bytes(orig_w, orig_h, target_w, target_h):
    """Conservative shared allowance for the current sequential renderer.

    Source: decode, EXIF copy, RGBA compositing and grayscale/filter copies.
    Target: three float64 dither buffers (24 B/pixel), byte output, retained
    image/threshold buffers, masks and PNG/SVG serialization. Two float64
    buffers include padding. Add fixed workspace headroom; codec/interpreter
    overhead is not a hard operating-system memory limit.
    """
    pixels = target_w * target_h
    padding = (target_w + 3) * (target_h + 2) - pixels
    return 32 * orig_w * orig_h + 48 * pixels + 16 * padding + 1024 * 1024


def verify_job_manifest(manifest_path, source_path=None, *, expected_recipe=None, expected_outputs=None):
    """Verify required hashes; malformed metadata and I/O failures are results."""
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return False, [f"Cannot parse manifest '{manifest_path}': {exc}"]
    if not isinstance(data, dict):
        return False, ["Manifest root must be a JSON object."]

    errors = []
    if data.get('schema_version') != "1.0":
        return False, [f"Unsupported or missing manifest schema version: {data.get('schema_version')!r}."]

    def valid_hash(value):
        return isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value) is not None

    def check_hash(path, expected, label):
        try:
            actual = sha256_file(path)
        except (OSError, ValueError) as exc:
            errors.append(f"{label} '{path}' cannot be read or does not exist: {exc}")
            return
        if actual != expected.lower():
            errors.append(f"{label} '{path}' hash mismatch (file has changed).")

    manifest_dir = os.path.realpath(os.path.dirname(os.path.abspath(manifest_path)))
    src_info = data.get('source')
    if not isinstance(src_info, dict) or not valid_hash(src_info.get('sha256')):
        errors.append("Manifest missing required source record or valid sha256 hash.")
    else:
        filename = src_info.get('filename')
        relpath = src_info.get('relpath')
        if not isinstance(filename, str) or not filename or '\x00' in filename:
            errors.append("Manifest source filename must be a non-empty string.")
        elif relpath is not None and (not isinstance(relpath, str) or not relpath or '\x00' in relpath or os.path.isabs(relpath)):
            errors.append("Manifest source relpath must be a non-empty relative path.")
        elif source_path is not None:
            check_hash(source_path, src_info['sha256'], 'Source file')
        else:
            # New manifests resolve relative to their own directory, never cwd.
            resolved = os.path.join(manifest_dir, relpath or filename)
            check_hash(resolved, src_info['sha256'], 'Source file')

    if source_path is not None and not os.path.exists(source_path):
        errors.append(f"Source file '{source_path}' does not exist.")

    outputs = data.get('outputs')
    if not isinstance(outputs, dict) or not outputs:
        errors.append("Manifest missing required outputs record.")
        outputs = {}
    if expected_outputs is not None and set(outputs) != set(expected_outputs):
        errors.append('Manifest output set does not match the requested job.')
    if expected_recipe is not None:
        recipe = data.get('recipe')
        if not isinstance(recipe, dict) or any(recipe.get(k) != v for k, v in expected_recipe.items()):
            errors.append('Manifest recipe does not match the requested job.')
    for name, metadata in outputs.items():
        # Generated output records are adjacent basenames, never arbitrary paths.
        if (not name or name in ('.', '..') or '/' in name or '\\' in name or '\x00' in name):
            errors.append(f"Invalid recorded output filename: {name!r}.")
            continue
        path = os.path.join(manifest_dir, name)
        if os.path.commonpath((manifest_dir, os.path.realpath(path))) != manifest_dir:
            errors.append(f"Recorded output '{name}' resolves outside the manifest directory.")
            continue
        expected = metadata.get('sha256') if isinstance(metadata, dict) else None
        if not valid_hash(expected):
            errors.append(f"Recorded output '{name}' has no valid sha256 hash.")
            continue
        check_hash(path, expected, 'Output file')

    return not errors, errors


def settings_suffix(values, svg_cut=False, svg_linework=False, workflow=None):
    """Filename tag: 'dithered' for an all-default job, else a digest of the whole recipe.

    The manifest, not the filename, is the readable record of what a job used.
    """
    record = {'values': {key: values[key] for key in sorted(values)},
              'svg_cut': svg_cut, 'svg_linework': svg_linework,
              'workflow': workflow.record() if workflow is not None and workflow.active else None}
    defaults = {key: DEFAULTS[key] for key in values}
    if record == {'values': defaults, 'svg_cut': False, 'svg_linework': False, 'workflow': None}:
        return 'dithered'
    return 'r' + digest(record)[:12]


class DestinationNamespace:
    """Every file a plan will publish, checked before anything is written.

    Shared by batch and audition planning: discovery, output-root containment,
    source protection, case-folding collisions and the existing-output policy.
    """

    def __init__(self, input_paths, output_dir, sources, folds_case, existing):
        self.output_dir = output_dir
        self.output_root = os.path.realpath(output_dir)
        self.input_roots = {os.path.realpath(p): p for p in input_paths if os.path.isdir(p)}
        self.sources = sources
        # Every identity a source can be reached by: resolved path and inode (hard links included).
        self.source_realpaths = {os.path.realpath(source) for _, source in sources}
        self.source_ids = {identity for _, source in sources if (identity := _file_identity(source))}
        self.folds_case = folds_case
        self.existing = existing
        self.claimed = {}
        self.required_dirs = {}

    @classmethod
    def open(cls, input_paths, output_dir, existing='overwrite', dry_run=False):
        """Return (namespace, errors); namespace is None when the batch cannot start."""
        if existing not in ('overwrite', 'skip', 'error'):
            return None, [f"Unsupported existing-output policy '{existing}'."]
        errors = []
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
            return None, errors
        if not sources:
            return None, ["No supported images found in the selected inputs."]

        # Dry-run must reject a blocked output root too, without creating it.
        parent = _existing_parent(output_dir)
        if not os.path.isdir(parent):
            return None, [f"Cannot use output directory '{output_dir}': '{parent}' is not a directory."]
        if os.path.lexists(output_dir) and not os.path.isdir(output_dir):
            return None, [f"Cannot use output directory '{output_dir}': it is not a directory."]
        if not dry_run:
            try:
                os.makedirs(output_dir, exist_ok=True)
            except OSError as exc:
                return None, [f"Cannot use output directory '{output_dir}': {exc}"]

        namespace = cls(input_paths, output_dir, sources, _destination_folds_case(output_dir, dry_run=dry_run), existing)
        for input_root, input_path in namespace.input_roots.items():
            if _is_within(namespace.output_root, input_root):
                errors.append(
                    f"Output directory '{output_dir}' is inside input directory '{input_path}'. "
                    "Choose a separate output directory to avoid reprocessing generated images."
                )
        return (None, errors) if errors else (namespace, [])

    def target_dir(self, input_path, source):
        """Mirror a source's folder beneath the output root, checking it is safe to publish into."""
        if os.path.isdir(input_path):
            rel_dir = os.path.dirname(os.path.relpath(source, start=input_path))
            target_dir = os.path.join(self.output_dir, rel_dir) if rel_dir else self.output_dir
        else:
            target_dir = self.output_dir

        # A symlinked or traversing parent must not redirect writes out of the output root...
        target_real = os.path.realpath(target_dir)
        if not _is_within(target_real, self.output_root):
            return target_dir, (
                f"{source}: destination folder '{target_dir}' resolves to '{target_real}', "
                f"outside the output root '{self.output_root}'."
            )

        # ...nor into a selected input tree. Staying inside the output root is not enough
        # when an input directory is itself beneath that root: a symlinked destination
        # folder would then deposit generated artwork among the sources, where a later
        # recursive run would ingest it.
        invaded = next(
            (path for root, path in self.input_roots.items() if _is_within(target_real, root)), None)
        if invaded is not None:
            return target_dir, (
                f"{source}: destination folder '{target_dir}' resolves to '{target_real}', "
                f"inside input directory '{invaded}'. Generated files must not enter a source tree."
            )

        # Every folder this job needs must be creatable: no existing non-directory on the
        # way down, and no other job planning to publish a file at one of those paths.
        ancestors = _ancestors_within(target_dir, self.output_dir)
        conflicting_parent = next(
            (path for path in ancestors if os.path.lexists(path) and not os.path.isdir(path)), None)
        if conflicting_parent is not None:
            return target_dir, (
                f"{source}: destination folder '{target_dir}' needs '{conflicting_parent}' "
                "to be a directory, but a file already exists there."
            )
        for path in ancestors:
            self.required_dirs.setdefault(_destination_key(path, self.folds_case), (path, source))
        return target_dir, None

    def claim(self, source, destinations):
        """Reserve a job's destinations. Returns (error, reusable): reusable means
        --existing skip found the complete output set already present."""
        def hits_a_source(destination):
            if os.path.realpath(destination) in self.source_realpaths:
                return True
            identity = _file_identity(destination)
            return identity is not None and identity in self.source_ids

        clobbered = [d for d in destinations if hits_a_source(d)]
        if clobbered:
            return (f"{source}: would overwrite input file(s) {clobbered}. "
                    "Choose an output folder that holds no source images."), False

        for destination in destinations:
            key = _destination_key(destination, self.folds_case)
            other = self.claimed.get(key)
            if other is not None:
                return (f"'{source}' and '{other}' both map to '{destination}'"
                        f"{' (this filesystem ignores case)' if self.folds_case else ''}. "
                        "Rename or separate the inputs."), False
            self.claimed[key] = source

        blocked = [path for path in destinations if os.path.isdir(path)]
        if blocked:
            return f'{source}: output path is a directory: {blocked}', False
        present = [path for path in destinations if os.path.exists(path)]
        if not present or self.existing == 'overwrite':
            return None, False
        if self.existing == 'error':
            return f"{source}: output already exists: {present}", False
        if len(present) != len(destinations):
            return (f"{source}: incomplete existing output set {present}. Repair or remove it, "
                    "or rerun with --existing overwrite."), False
        return None, True

    def conflicts(self):
        """Folders one job needs that another job would publish as a file."""
        errors = []
        for key, (path, needed_by) in self.required_dirs.items():
            published_by = self.claimed.get(key)
            if published_by is not None:
                errors.append(
                    f"'{published_by}' publishes a file at '{path}', which '{needed_by}' needs as a "
                    "directory. Rename or separate the inputs."
                )
        return errors


def plan_batch(
    input_paths,
    output_dir,
    values,
    preset_name=None,
    width_in=None,
    height_in=None,
    svg_cut=False,
    svg_linework=False,
    max_pixels=DEFAULT_MAX_PIXELS,
    machine=None,
    existing='overwrite',
    dry_run=False,
    manifest=False,
    max_memory=None,
    expected_recipe=None,
    workflow=None,
):
    """Resolve every source and destination before anything is written.

    Returns (jobs, errors). A non-empty errors list means nothing should be published:
    a destination that overlaps a source, escapes the output root, or collides with
    another destination is a whole-batch problem, not a per-file one.
    """
    workflow = workflow or WorkflowOptions()
    namespace, errors = DestinationNamespace.open(input_paths, output_dir, existing, dry_run)
    if namespace is None:
        return [], errors

    jobs = []
    for input_path, source in namespace.sources:
        filename = os.path.basename(source)
        name, ext = os.path.splitext(filename)

        try:
            orig_w, orig_h, target_w, target_h, dim_suffix = resolve_oriented_geometry(
                source, width_in=width_in, height_in=height_in, max_pixels=max_pixels, machine=machine
            )
        except Exception as exc:
            errors.append(f"{source}: {exc}")
            continue

        job_preset = preset_name
        if not job_preset and '--' in name:
            candidate = name.rpartition('--')[2].strip().lower()
            if candidate in PRESETS:
                job_preset = candidate

        try:
            workflow.validate(invert=values.get('invert', False), svg_cut=svg_cut, machine=machine)
            circle = values.get('circle_cut')
            workflow_geometry = layout(workflow, (target_w, target_h), machine=machine, circle_cut=circle)
        except ValueError as exc:
            errors.append(f'{source}: {exc}')
            continue
        est_memory = _working_memory_bytes(orig_w, orig_h, target_w, target_h)
        if workflow.active:
            # Extra masks, preview, PDF image serialization, and repeated SVG payloads.
            est_memory += target_w * target_h * (48 + 16 * len(workflow_geometry['placements_px'])) + 4 * 1024 * 1024
        if max_memory is not None and est_memory > max_memory:
            errors.append(
                f"{source}: estimated memory ({est_memory / 1024 / 1024:.1f} MB) exceeds budget ({max_memory / 1024 / 1024:.1f} MB). "
                "Reduce target dimensions or increase --max-memory."
            )
            continue

        job_preset_dict = PRESETS.get(job_preset, {}) if job_preset else {}
        job_values = dict(values)
        if job_preset and job_preset != preset_name:
            for k, v in job_preset_dict.items():
                job_values[k] = v

        # Match the recipe serialized by export for this particular job. A
        # filename-inferred preset can differ from the batch defaults.
        job_expected_recipe = dict(expected_recipe or {})
        job_expected_recipe.update(job_values)
        job_expected_recipe['preset'] = job_preset
        job_expected_recipe['no_border'] = job_values['no_border'] or svg_cut or workflow.suppress_border
        job_expected_recipe['svg_linework'] = svg_linework

        job_settings_str = settings_suffix(job_values, svg_cut, svg_linework, workflow)
        output_filename = f"{name}_{ext.lstrip('.').lower()}_{job_settings_str}{dim_suffix}.png"
        target_dir, error = namespace.target_dir(input_path, source)
        if error:
            errors.append(error)
            continue

        output_path = os.path.join(target_dir, output_filename)
        svg_path = f"{os.path.splitext(output_path)[0]}_cut.svg" if svg_cut else None
        manifest_path = f"{os.path.splitext(output_path)[0]}_manifest.json" if manifest else None
        artifact_paths = workflow.paths(output_path)
        if svg_linework:
            artifact_paths['linework'] = f"{os.path.splitext(output_path)[0]}_linework.svg"
        for index in range(1, job_values.get('tone_layers', 0) + 1):
            artifact_paths[f'tone_layer_{index}'] = (
                f"{os.path.splitext(output_path)[0]}_tone{index:02d}of{job_values['tone_layers']}.png"
            )
        if job_values.get('stamp_text') is not None:
            artifact_paths['stamp'] = f"{os.path.splitext(output_path)[0]}_stamp.png"
        if job_values.get('qr_text') is not None:
            artifact_paths['qr'] = f"{os.path.splitext(output_path)[0]}_qr.png"

        job = PlannedJob(
            input_path=source,
            output_path=output_path,
            svg_path=svg_path,
            manifest_path=manifest_path,
            estimated_memory_bytes=est_memory,
            output_size=(target_w, target_h),
            values=job_values,
            preset_name=job_preset,
            artifacts=artifact_paths,
            workflow_geometry=workflow_geometry,
        )

        error, reusable = namespace.claim(source, job.destinations)
        if error:
            errors.append(error)
            continue
        if reusable:
            if manifest:
                valid, verification_errors = verify_job_manifest(
                    manifest_path, source,
                    expected_recipe=job_expected_recipe,
                    expected_outputs=[os.path.basename(p) for p in job.destinations if p != manifest_path],
                )
                if not valid:
                    errors.extend(f'{source}: cannot reuse existing job: {error}' for error in verification_errors)
                    continue
            job = replace(
                job, is_skipped=True,
                skip_reason="manifest verified" if manifest else "existing output complete (existence only)",
            )

        jobs.append(job)

    errors.extend(namespace.conflicts())
    return jobs, errors
