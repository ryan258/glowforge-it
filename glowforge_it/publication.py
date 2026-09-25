"""Staging temporary files and replacing destinations, with recovery.

Deliberately knows nothing about presets, Pillow, or this project's file naming: it moves
bytes into place and puts the previous bytes back when it cannot.
"""

import hashlib
import os
import tempfile

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
    fd, staged = tempfile.mkstemp(prefix='.gf-', suffix=os.path.splitext(destination)[1], dir=directory)
    os.close(fd)
    try:
        write_callback(staged)
    except BaseException:
        if os.path.exists(staged):
            os.unlink(staged)
        raise
    return staged

class RecoveryError(OSError):
    """A publication failed and at least one previous file could not be put back.

    `backups` maps each destination that is still missing to the temporary file holding
    its previous bytes, so the operator can restore it by hand.
    """

    def __init__(self, message, cause, backups):
        super().__init__(message)
        self.cause = cause
        self.backups = backups

def publish_generation(staged_pairs):
    """Replace every destination with its staged file, or put the previous files back.

    Two os.replace() calls are not a cross-file transaction, so the previous files are
    moved aside first and moved back if any destination fails. A publication failure
    therefore aims to leave the complete previous generation rather than half of the new
    one, and does so whenever recovery itself succeeds. When it does not, see below.

    Recovery is attempted for every file independently: one failed restoration does not
    abandon the others. If any file cannot be put back, the remaining `.gf-prev-*`
    backups are kept and a RecoveryError names which backup belongs to which destination.

    ponytail: rollback, not crash-proof. A kill between the renames can still leave a
    mixed pair, and a backup left on disk is a manual repair; immutable job directories
    plus a committed manifest (E02/E10) is the upgrade path when that window matters.
    """
    for destination, _ in staged_pairs:
        if os.path.isdir(destination):
            raise IsADirectoryError(f"Destination '{destination}' is an existing directory.")

    backups = []
    published = []
    try:
        for destination, staged in staged_pairs:
            if os.path.lexists(destination):
                fd, backup = tempfile.mkstemp(
                    prefix='.gf-prev-', dir=os.path.dirname(os.path.abspath(destination)))
                os.close(fd)
                os.replace(destination, backup)
                backups.append((destination, backup))
            os.replace(staged, destination)
            published.append(destination)
    except BaseException as publication_error:
        unrecovered = {}
        recovery_errors = []
        for destination in published:
            try:
                if os.path.lexists(destination):
                    os.unlink(destination)
            except OSError as exc:
                recovery_errors.append(f"{destination}: {exc}")
        for destination, backup in backups:
            try:
                os.replace(backup, destination)
            except OSError as exc:
                # Keep the backup: it still holds the only copy of the previous bytes.
                unrecovered[destination] = backup
                recovery_errors.append(f"{destination}: {exc}")
        if unrecovered or recovery_errors:
            raise RecoveryError(
                f"Publication failed ({publication_error}) and recovery was incomplete. "
                f"Restore by hand: {unrecovered or 'nothing left to restore'}. "
                f"Recovery errors: {'; '.join(recovery_errors)}",
                publication_error,
                unrecovered,
            ) from publication_error
        raise
    for _, backup in backups:
        if os.path.lexists(backup):
            os.unlink(backup)
