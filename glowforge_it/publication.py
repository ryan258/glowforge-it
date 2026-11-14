"""Staging temporary files and replacing destinations, with recovery.

Deliberately knows nothing about presets, Pillow, or this project's file naming: it moves
bytes into place and puts the previous bytes back when it cannot.
"""

from contextlib import contextmanager
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import tempfile
import unicodedata
import uuid

JOURNAL_PREFIX = '.gf-publish-'
BACKUP_PREFIX = '.gf-prev-'
STAGE_PREFIX = '.gf-stage-'
JOURNAL_TEMP_PREFIX = '.gf-journal-'
MAX_JOURNAL_BYTES = 1_048_576
EMPTY_SHA256 = hashlib.sha256(b'').hexdigest()
RESERVED_PREFIXES = (JOURNAL_PREFIX, BACKUP_PREFIX, STAGE_PREFIX, JOURNAL_TEMP_PREFIX)

def sha256_file(path):
    """Compute the SHA-256 hex digest of a file in 64 KiB chunks."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()

def stage_beside(destination, write_callback):
    """Write content to a temporary file next to its destination and return that path."""
    directory = os.path.dirname(os.path.abspath(destination)) or '.'
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise OSError(f"Cannot create output directory '{directory}': {exc}") from exc
    directory = os.path.realpath(directory)
    fd, staged = tempfile.mkstemp(prefix=STAGE_PREFIX, suffix=os.path.splitext(destination)[1], dir=directory)
    os.close(fd)
    # mkstemp creates 0600; published files should get the mode a normal write would (umask).
    umask = os.umask(0)
    os.umask(umask)
    try:
        os.chmod(staged, 0o666 & ~umask)
        write_callback(staged)
    except BaseException:
        if os.path.exists(staged):
            os.unlink(staged)
        raise
    return staged

class RecoveryError(OSError):
    """An unresolved publication, a recovery conflict, or a busy output directory."""

    def __init__(self, message, cause, backups, journal_path=None):
        super().__init__(message)
        self.cause = cause
        self.backups = backups
        self.journal_path = journal_path


def _is_journal_name(name):
    return name.startswith(JOURNAL_PREFIX) and name.endswith('.json')


def pending_publication(directory):
    """Return the first pending journal in this literal directory, without writing."""
    directory = os.path.realpath(directory)
    try:
        with os.scandir(directory) as entries:
            name = min((entry.name for entry in entries if _is_journal_name(entry.name)), default=None)
    except FileNotFoundError:
        return None
    return os.path.join(directory, name) if name else None


def check_pending_publication(directory):
    journal = pending_publication(directory)
    if journal:
        command = f"gf --recover-publication {shlex.quote(journal)} --dry-run"
        raise RecoveryError(f"An unresolved publication needs review first: {journal}. "
                            f"Inspect with {command}", None, {}, journal)


def format_cleanup_warning(warning):
    journal = warning['journal']
    backup = f" Retained backup: {warning['backup']}." if warning['backup'] else ''
    command = f"gf --recover-publication {shlex.quote(journal)} --dry-run"
    return (f"Warning: published successfully. Cleanup needs review: {warning['message']}."
            f"{backup} Inspect with {command}")


def _identity(status):
    return status.st_dev, status.st_ino


def _check_directory(directory, identity):
    if os.path.realpath(directory) != directory or _identity(os.stat(directory)) != identity:
        raise RecoveryError(f"Publication stopped: output directory changed: {directory}", None, {})


@contextmanager
def _locked_directory(directory, *, dry_run=False):
    """Hold an advisory lock on the directory inode on macOS and Linux."""
    if os.name != 'posix':
        yield _identity(os.stat(directory))
        return
    import fcntl

    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        mode = fcntl.LOCK_SH if dry_run else fcntl.LOCK_EX
        try:
            fcntl.flock(descriptor, mode | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryError(f"Another Glowforge publication or recovery is active in '{directory}'.",
                                exc, {}) from exc
        identity = _identity(os.fstat(descriptor))
        _check_directory(directory, identity)
        yield identity
    finally:
        os.close(descriptor)


def _regular_stat(path):
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(status.st_mode):
        raise ValueError(f"Refusing a symlink publication path: {path}")
    if stat.S_ISDIR(status.st_mode):
        raise IsADirectoryError(f"Publication path '{path}' is an existing directory.")
    if not stat.S_ISREG(status.st_mode):
        raise ValueError(f"Publication path must be a regular file: {path}")
    return status


def validate_publication_destinations(paths):
    """Accept absent or regular output files and reject reserved transaction names."""
    for path in paths:
        path = os.fsdecode(path)
        if os.path.basename(path).casefold().startswith(RESERVED_PREFIXES):
            raise ValueError(f"Destination is a reserved publication name: {path}")
        _regular_stat(path)


@contextmanager
def _open_regular(path):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    descriptor = os.open(path, flags | getattr(os, 'O_BINARY', 0))
    with os.fdopen(descriptor, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Publication path must be a regular file: {path}")
        yield stream


def _current_hash(path):
    if path is None or _regular_stat(path) is None:
        return None
    with _open_regular(path) as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _journal_bytes(record):
    return json.dumps(record, sort_keys=True, indent=2).encode('utf-8')


def _write_journal(path, record):
    """Expose the final name only after the complete record has been written."""
    raw = _journal_bytes(record)
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError('Recovery record is too large.')
    descriptor, staged = tempfile.mkstemp(prefix=JOURNAL_TEMP_PREFIX, dir=os.path.dirname(path))
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def _in_job_directory(path, directory, identity):
    if (not isinstance(path, str) or not os.path.isabs(path)
            or '\x00' in path or os.path.normpath(path) != path
            or not os.path.basename(path)):
        raise ValueError('Invalid publication path.')
    if _identity(os.stat(os.path.dirname(path))) != identity:
        raise ValueError(f"Publication path must be in the job directory: {path}")
    return os.path.join(directory, os.path.basename(path))


def _require_distinct_paths(paths):
    names, identities = set(), set()
    for path in paths:
        if path is None:
            continue
        key = unicodedata.normalize('NFC', os.path.basename(path)).casefold()
        status = _regular_stat(path)
        identity = _identity(status) if status else None
        if key in names or (identity is not None and identity in identities):
            raise ValueError(f"Publication paths must be distinct and cannot alias each other: {path}")
        names.add(key)
        if identity is not None:
            identities.add(identity)


def _owned_stage(staged, destination):
    name = os.path.basename(staged)
    suffix = re.escape(os.path.splitext(destination)[1])
    return re.fullmatch(re.escape(STAGE_PREFIX) + r'[a-z0-9_]{8}' + suffix, name) is not None


def _valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _read_journal(journal, directory, identity):
    _regular_stat(journal)
    with _open_regular(journal) as stream:
        raw = stream.read(MAX_JOURNAL_BYTES + 1)
    if len(raw) > MAX_JOURNAL_BYTES:
        raise ValueError('Recovery record is too large.')
    try:
        record = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise ValueError(f"Cannot read publication journal '{journal}': {exc}") from exc
    if (not isinstance(record, dict) or record.get('kind') != 'glowforge-publication'
            or type(record.get('version')) is not int or record['version'] not in (1, 2)
            or record.get('state') not in ('publishing', 'restored', 'committed')
            or not isinstance(record.get('files'), list) or not record['files']):
        raise ValueError('Not an interrupted Glowforge publication record.')
    version = record['version']
    if version == 2 and record.get('directory_identity') != list(identity):
        raise ValueError('Recovery record belongs to a different output directory.')
    paths = [journal]
    keys = {'destination', 'backup', 'old_sha256', 'new_sha256'}
    if version == 2:
        keys.add('staged')
    for index, item in enumerate(record['files']):
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError('Invalid publication recovery entry.')
        destination = _in_job_directory(item['destination'], directory, identity)
        validate_publication_destinations((destination,))
        old_hash, new_hash = item['old_sha256'], item['new_sha256']
        if (old_hash is not None and not _valid_hash(old_hash)) or not _valid_hash(new_hash):
            raise ValueError('Invalid recovery fingerprint.')
        backup = item['backup']
        if old_hash is None:
            if backup is not None:
                raise ValueError('A new destination cannot have a previous-generation backup.')
        else:
            backup = _in_job_directory(backup, directory, identity)
            if not os.path.basename(backup).startswith(BACKUP_PREFIX):
                raise ValueError('Invalid previous-generation backup path.')
            if version == 2 and backup != _backup_path(journal, index):
                raise ValueError('Backup path does not belong to this recovery journal.')
        staged = item.get('staged')
        if staged is not None:
            staged = _in_job_directory(staged, directory, identity)
            if not _owned_stage(staged, destination):
                raise ValueError('Invalid staged artifact path.')
        item.update(destination=destination, backup=backup)
        if version == 2:
            item['staged'] = staged
        paths.extend((destination, backup, staged))
    _require_distinct_paths(paths)
    return record, hashlib.sha256(raw).hexdigest()


def _recovery_error(message, item, journal):
    backups = {item['destination']: item['backup']} if item['backup'] else {}
    return RecoveryError(message, None, backups, journal)


def _require_committed_artifact(item, observed_hash, journal):
    if observed_hash != item['new_sha256']:
        raise _recovery_error(
            f"Cleanup refused: committed artifact '{item['destination']}' is missing or changed. "
            "Preserve the journal and backups.",
            item, journal,
        )


def _recovery_actions(record, journal):
    actions = []
    for item in record['files']:
        destination, backup, staged = item['destination'], item['backup'], item.get('staged')
        old_hash, new_hash = item['old_sha256'], item['new_sha256']
        current_hash, backup_hash, staged_hash = map(_current_hash, (destination, backup, staged))
        state = record['state']
        if state == 'committed':
            _require_committed_artifact(item, current_hash, journal)
            action = 'cleanup_committed'
        elif current_hash == old_hash:
            action = 'unchanged'
        elif state == 'restored' or current_hash not in (None, new_hash):
            raise _recovery_error(f"Recovery refused: '{destination}' changed after interruption.", item, journal)
        else:
            action = 'restore' if old_hash is not None else 'remove_new'

        allowed_backups = {None, old_hash}
        if record['version'] == 1 and action == 'unchanged':
            allowed_backups.add(EMPTY_SHA256)
        if backup_hash not in allowed_backups or (action == 'restore' and backup_hash != old_hash):
            raise _recovery_error(f"Recovery refused: previous bytes are missing or changed for '{destination}'.",
                                  item, journal)
        if staged_hash not in (None, new_hash):
            raise _recovery_error(f"Recovery refused: staged bytes changed for '{destination}'.", item, journal)
        actions.append({**item, 'action': action, 'observed_sha256': current_hash,
                        'observed_backup_sha256': backup_hash, 'observed_staged_sha256': staged_hash})
    return actions


def _require_hash(path, expected, journal):
    if _current_hash(path) != expected:
        raise RecoveryError(f"Publication stopped: '{path}' changed during publication or recovery.",
                            None, {}, journal)


def _restore_copy(item, directory, identity, journal):
    destination, backup = item['destination'], item['backup']
    staged = stage_beside(destination, lambda name: shutil.copy2(backup, name))
    try:
        _require_hash(staged, item['old_sha256'], journal)
        _check_directory(directory, identity)
        _require_hash(destination, item['observed_sha256'], journal)
        os.replace(staged, destination)
        _require_hash(destination, item['old_sha256'], journal)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def recover_publication(journal_path, *, dry_run=False):
    """Inspect or restore one interrupted job with directory and byte guards.

    The journal supports local process interruption. This is a per-job operation
    and does not guarantee recovery from an OS crash or storage failure.
    """
    journal_path = os.path.abspath(os.fsdecode(journal_path))
    directory = os.path.realpath(os.path.dirname(journal_path))
    journal = os.path.join(directory, os.path.basename(journal_path))
    if not _is_journal_name(os.path.basename(journal)):
        raise ValueError('Choose a .gf-publish-*.json recovery journal from the output directory.')
    with _locked_directory(directory, dry_run=dry_run) as identity:
        record, journal_hash = _read_journal(journal, directory, identity)
        actions = _recovery_actions(record, journal)
        result = {'journal_path': journal, 'dry_run': dry_run, 'actions': actions}
        if dry_run:
            return result
        for item in actions:
            _check_directory(directory, identity)
            _require_hash(journal, journal_hash, journal)
            destination = item['destination']
            _require_hash(destination, item['observed_sha256'], journal)
            if item['action'] == 'restore':
                _restore_copy(item, directory, identity, journal)
            elif item['action'] == 'remove_new' and item['observed_sha256'] is not None:
                os.unlink(destination)
        committed = record['state'] == 'committed'
        if record['state'] == 'publishing':
            _check_directory(directory, identity)
            _require_hash(journal, journal_hash, journal)
            record['state'] = 'restored'
            _write_journal(journal, record)
            journal_hash = hashlib.sha256(_journal_bytes(record)).hexdigest()
        for item in actions:
            for key in ('backup', 'staged'):
                path, expected = item.get(key), item[f'observed_{key}_sha256']
                if path is not None:
                    _check_directory(directory, identity)
                    _require_hash(journal, journal_hash, journal)
                    if committed:
                        _require_committed_artifact(item, _current_hash(item['destination']), journal)
                    _require_hash(path, expected, journal)
                    if expected is not None:
                        os.unlink(path)
        _check_directory(directory, identity)
        _require_hash(journal, journal_hash, journal)
        os.unlink(journal)
        result.update(restored=not committed, cleaned_committed=committed)
        return result


def _backup_path(journal, index):
    identifier = os.path.basename(journal)[len(JOURNAL_PREFIX):-len('.json')]
    return os.path.join(os.path.dirname(journal), f'{BACKUP_PREFIX}{identifier}-{index}')


def _rollback(attempted, directory, identity, journal, cause):
    unrecovered, errors = {}, []
    for item in reversed(attempted):
        destination, backup = item['destination'], item['backup']
        try:
            _check_directory(directory, identity)
            current_hash = _current_hash(destination)
            backup_hash = _current_hash(backup)
            if current_hash not in (None, item['old_sha256'], item['new_sha256']):
                raise OSError('Destination bytes changed during publication.')
            if backup_hash not in (None, item['old_sha256']):
                raise OSError('Previous bytes changed during publication.')
            if backup_hash is not None:
                os.replace(backup, destination)
            elif current_hash != item['old_sha256']:
                if backup is not None:
                    raise OSError('Previous bytes are missing or changed.')
                os.unlink(destination)
        except (OSError, ValueError) as exc:
            if backup is not None:
                unrecovered[destination] = backup
            errors.append(f'{destination}: {exc}')
    if errors:
        raise RecoveryError(f"Publication failed ({cause}) and recovery was incomplete. "
                            f"Journal: {journal}. Recovery errors: {'; '.join(errors)}",
                            cause, unrecovered, journal) from cause


def _cleanup_committed(record, journal, directory, identity):
    warnings = []
    journal_hash = hashlib.sha256(_journal_bytes(record)).hexdigest()
    try:
        _check_directory(directory, identity)
        _require_hash(journal, journal_hash, journal)
        for item in record['files']:
            _require_committed_artifact(item, _current_hash(item['destination']), journal)
    except (OSError, ValueError) as exc:
        return [{'destination': None, 'backup': None, 'journal': journal, 'message': str(exc)}]
    for item in record['files']:
        backup = item['backup']
        if backup is None:
            continue
        try:
            _check_directory(directory, identity)
            _require_hash(journal, journal_hash, journal)
            _require_committed_artifact(item, _current_hash(item['destination']), journal)
            _require_hash(backup, item['old_sha256'], journal)
            os.unlink(backup)
        except (OSError, ValueError) as exc:
            warnings.append({'destination': item['destination'], 'backup': backup,
                             'journal': journal, 'message': str(exc)})
    if not warnings:
        try:
            _check_directory(directory, identity)
            _require_hash(journal, journal_hash, journal)
            os.unlink(journal)
        except (OSError, ValueError) as exc:
            warnings.append({'destination': None, 'backup': None, 'journal': journal, 'message': str(exc)})
    return warnings


def publish_generation(staged_pairs, *, must_be_absent=()):
    """Publish one job, rolling back errors and journaling process interruption."""
    staged_pairs = [(os.path.abspath(os.fsdecode(d)), os.path.abspath(os.fsdecode(s))) for d, s in staged_pairs]
    if not staged_pairs:
        return []
    directory = os.path.realpath(os.path.dirname(staged_pairs[0][0]))
    with _locked_directory(directory) as identity:
        check_pending_publication(directory)
        pairs = [(_in_job_directory(destination, directory, identity),
                  _in_job_directory(staged, directory, identity)) for destination, staged in staged_pairs]
        destinations = tuple(destination for destination, _ in pairs)
        for protected in must_be_absent:
            protected = _in_job_directory(os.path.abspath(os.fsdecode(protected)), directory, identity)
            if os.path.lexists(protected):
                if protected in destinations:
                    raise FileExistsError(f"Output appeared after planning: {protected}. "
                                          "Rerun to apply the existing-output policy.")
                raise RecoveryError(f"Publication would leave an outdated companion: {protected}. "
                                    "Include its manifest or choose a separate output folder.", None, {})
        validate_publication_destinations(destinations)
        _require_distinct_paths(path for pair in pairs for path in pair)
        journal = os.path.join(directory, f'{JOURNAL_PREFIX}{uuid.uuid4().hex}.json')
        entries = []
        for index, (destination, staged) in enumerate(pairs):
            old_hash, new_hash = _current_hash(destination), _current_hash(staged)
            if new_hash is None:
                raise FileNotFoundError(f"Staged publication artifact is missing: {staged}")
            backup = _backup_path(journal, index) if old_hash is not None else None
            entries.append({'destination': destination, 'backup': backup,
                            'staged': staged if _owned_stage(staged, destination) else None,
                            'old_sha256': old_hash, 'new_sha256': new_hash})
        record = {'kind': 'glowforge-publication', 'version': 2, 'state': 'publishing',
                  'directory_identity': list(identity), 'files': entries}
        _check_directory(directory, identity)
        _write_journal(journal, record)
        journal_hash = hashlib.sha256(_journal_bytes(record)).hexdigest()

        attempted = []
        try:
            for (_, staged), item in zip(pairs, entries):
                _check_directory(directory, identity)
                destination, backup = item['destination'], item['backup']
                _require_hash(destination, item['old_sha256'], journal)
                _require_hash(staged, item['new_sha256'], journal)
                if backup is not None:
                    _require_hash(backup, None, journal)
                attempted.append(item)
                if backup is not None:
                    os.replace(destination, backup)
                os.replace(staged, destination)
            _check_directory(directory, identity)
            _require_hash(journal, journal_hash, journal)
            record['state'] = 'committed'
            _write_journal(journal, record)
        except BaseException as exc:
            # A signal can interrupt Python after the OS installed the commit record.
            if record['state'] == 'committed':
                try:
                    persisted, _ = _read_journal(journal, directory, identity)
                except (OSError, ValueError) as journal_error:
                    raise RecoveryError(f"Cannot determine publication state; inspect {journal}. {journal_error}",
                                        exc, {}, journal) from exc
                if persisted['state'] == 'committed':
                    if isinstance(exc, Exception):
                        return _cleanup_committed(record, journal, directory, identity)
                    raise
            _rollback(attempted, directory, identity, journal, exc)
            try:
                _check_directory(directory, identity)
                _require_hash(journal, journal_hash, journal)
                for item in entries:
                    if item['staged'] and _current_hash(item['staged']) == item['new_sha256']:
                        os.unlink(item['staged'])
                os.unlink(journal)
            except (OSError, ValueError) as cleanup_error:
                raise RecoveryError(f"Publication failed ({exc}). Previous output was restored, "
                                    f"but cleanup needs review: {journal}. {cleanup_error}",
                                    exc, {}, journal) from exc
            raise
        return _cleanup_committed(record, journal, directory, identity)
