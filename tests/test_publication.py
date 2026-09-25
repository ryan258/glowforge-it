"""Staging, replacement, rollback and incomplete recovery."""

import os

import pytest

from glowforge_it.publication import RecoveryError, publish_generation, stage_beside


def test_f04_failed_publication_keeps_the_previous_generation(tmp_path):
    """A partial publish must roll back, not leave the old PNG destroyed."""
    good = tmp_path / "good.png"
    good.write_bytes(b"previous")
    blocked = tmp_path / "blocked.svg"
    blocked.mkdir()  # an existing directory cannot be replaced by a file

    staged = [
        (str(good), stage_beside(str(good), lambda p: open(p, "wb").write(b"new"))),
        (str(blocked), stage_beside(str(blocked), lambda p: open(p, "wb").write(b"new"))),
    ]
    with pytest.raises(IsADirectoryError):
        publish_generation(staged)
    assert good.read_bytes() == b"previous"


def _injecting_replace(monkeypatch, fail_when):
    """Make a chosen rename fail, so the tests reach the real rollback path.

    Patched through `glowforge_it.publication`, which is the module whose renames are
    under test. (That name refers to the one shared `os` module, so the patch is global
    for the duration of the test; naming the owning module keeps the intent clear if the
    dependency is ever injected properly.)
    """
    from glowforge_it import publication

    real = os.replace

    def replace(source, destination):
        failure = fail_when(str(source), str(destination))
        if failure:
            raise OSError(failure)
        return real(source, destination)

    monkeypatch.setattr(publication.os, "replace", replace)


def test_f04_rollback_restores_exact_previous_bytes(monkeypatch, tmp_path):
    """Fail the SECOND publication, after the first destination was already replaced."""
    png, svg = tmp_path / "a.png", tmp_path / "b.svg"
    png.write_bytes(b"old-png")
    svg.write_bytes(b"old-svg")
    staged_png, staged_svg = tmp_path / "s1", tmp_path / "s2"
    staged_png.write_bytes(b"new-png")
    staged_svg.write_bytes(b"new-svg")

    _injecting_replace(
        monkeypatch,
        lambda s, d: "injected publication failure" if s == str(staged_svg) else None,
    )
    with pytest.raises(OSError, match="injected publication failure"):
        publish_generation([(str(png), str(staged_png)), (str(svg), str(staged_svg))])

    assert png.read_bytes() == b"old-png"
    assert svg.read_bytes() == b"old-svg"
    assert list(tmp_path.glob(".gf-prev-*")) == []


def test_f04_incomplete_recovery_keeps_backups_and_reports_the_map(monkeypatch, tmp_path):
    """One failed restoration must not abandon the others, and must not lose the bytes."""
    png, svg = tmp_path / "a.png", tmp_path / "b.svg"
    png.write_bytes(b"old-png")
    svg.write_bytes(b"old-svg")
    staged_png, staged_svg = tmp_path / "s1", tmp_path / "s2"
    staged_png.write_bytes(b"new-png")
    staged_svg.write_bytes(b"new-svg")

    def fail_when(source, destination):
        if source == str(staged_svg):
            return "injected publication failure"
        if os.path.basename(source).startswith(".gf-prev-") and destination == str(png):
            return "injected restoration failure"
        return None

    _injecting_replace(monkeypatch, fail_when)
    with pytest.raises(RecoveryError) as raised:
        publish_generation([(str(png), str(staged_png)), (str(svg), str(staged_svg))])

    # The recoverable file was still recovered.
    assert svg.read_bytes() == b"old-svg"
    # The unrecoverable one is named, and its bytes are still on disk under the backup.
    assert list(raised.value.backups) == [str(png)]
    assert open(raised.value.backups[str(png)], "rb").read() == b"old-png"
    assert "injected publication failure" in str(raised.value)
