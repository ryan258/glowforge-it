"""Discovery, naming, sizing preflight, path protection, destination namespace."""

import os

import pytest
from PIL import Image

from tests.helpers import BATCH_DEFAULTS, folds_case, gray as _gray
from glowforge_it.batch import process_directory
from glowforge_it.cli import main
from glowforge_it.geometry import output_geometry


def _run_batch(tmp_path, images, **overrides):
    """Run process_directory over {relpath: PIL image} and return sorted output relpaths."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    for rel, img in images.items():
        dest = in_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)

    kwargs = dict(BATCH_DEFAULTS)
    kwargs.update(overrides)
    assert process_directory(str(in_dir), str(out_dir), **kwargs)
    return sorted(
        str(p.relative_to(out_dir)) for p in out_dir.rglob("*.png")
    )

def test_batch_default_naming(tmp_path):
    outputs = _run_batch(tmp_path, {"pic.png": Image.new("RGB", (8, 8), "gray")})
    assert outputs == ["pic_png_dithered.png"]


def test_batch_mirrors_subdirectories(tmp_path):
    outputs = _run_batch(tmp_path, {
        "top.png": Image.new("RGB", (8, 8), "gray"),
        "nested/deep/inner.png": Image.new("RGB", (8, 8), "gray"),
    })
    assert outputs == [
        os.path.join("nested", "deep", "inner_png_dithered.png"),
        "top_png_dithered.png",
    ]


def test_batch_tags_non_default_settings(tmp_path):
    outputs = _run_batch(
        tmp_path,
        {"pic.png": Image.new("RGB", (8, 8), "gray")},
        invert=True, no_border=True, black_thresh=20,
    )
    assert outputs == ["pic_png_b20_inv_nb.png"]


def test_batch_tags_preset_and_overrides(tmp_path):
    outputs = _run_batch(
        tmp_path,
        {"pic.png": Image.new("RGB", (8, 8), "gray")},
        preset_name="ai-art", denoise_radius=3, clean_solids=True,
        contrast=1.6, sharpen_radius=2.0, sharpen_percent=150,
        black_thresh=20,
    )
    # Preset values are baseline; only black_thresh deviates from ai-art.
    assert outputs == ["pic_png_prai-art_b20.png"]


def test_batch_dimension_suffix_respects_exif(tmp_path):
    # 200x400 stored, EXIF orientation 6 -> displays as 400x200 (landscape).
    img = Image.new("RGB", (200, 400), "gray")
    exif = img.getexif()
    exif[274] = 6
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    img.save(in_dir / "rot.jpg", exif=exif)

    outputs = _run_batch(tmp_path, {}, width_in=2.0)
    # 2in wide at 300 DPI on a 2:1 landscape source -> 1in tall, not 4in.
    assert outputs == ["rot_jpg_dithered_w2h1.png"]
    with Image.open(tmp_path / "out" / outputs[0]) as out:
        assert out.size == (600, 300)


def test_machine_bed_preflight(tmp_path):
    img_path = tmp_path / "test.png"
    Image.new("RGB", (300, 300), "white").save(img_path)

    # Spark bed is 8.5 x 11. 12 x 12 exceeds nominal bed.
    with pytest.raises(ValueError, match="exceeds the nominal spark area"):
        output_geometry(str(img_path), width_in=12.0, height_in=12.0, max_pixels=20_000_000, machine="spark")

    # Within bounds passes without error
    suffix = output_geometry(str(img_path), width_in=5.0, height_in=5.0, max_pixels=20_000_000, machine="spark")
    assert suffix == "_w5h5"


def test_existing_output_policies(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    img = Image.new("RGB", (30, 30), "gray")
    img.save(in_dir / "pic.png")

    kwargs = dict(
        black_thresh=0, white_thresh=255, dither_thresh=128,
        clean_solids=False, clean_solids_black=35, clean_solids_white=220,
        invert=False, width_in=None, height_in=None, no_border=False,
        denoise_radius=0, contrast=1.5, sharpen_radius=2.0,
        sharpen_percent=150, sharpen_threshold=3,
        circle_cut=False, heart_cut=False, preset_name=None,
    )
    # First pass writes output
    assert process_directory(str(in_dir), str(out_dir), existing="overwrite", **kwargs)

    # Second pass with 'skip' policy succeeds
    assert process_directory(str(in_dir), str(out_dir), existing="skip", **kwargs)

    # Second pass with 'error' policy fails
    assert not process_directory(str(in_dir), str(out_dir), existing="error", **kwargs)


def test_f01_explicit_inputs_are_never_overwritten(tmp_path):
    """An earlier job's output must not land on a later job's source file."""
    work = tmp_path / "work"
    work.mkdir()
    source = work / "art.png"
    victim = work / "art_png_dithered.png"  # exactly what art.png would be named
    _gray().save(source)
    _gray((12, 12)).save(victim)
    before = victim.read_bytes()

    assert main(["--input", str(source), str(victim), "-o", str(work)]) != 0
    assert victim.read_bytes() == before


def test_f01_hard_linked_destination_is_rejected(tmp_path):
    """A hard link is the same file under another name; it must be protected too."""
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    source = in_dir / "art.png"
    _gray().save(source)
    before = source.read_bytes()
    os.link(source, out_dir / "art_png_dithered.png")

    assert not process_directory(str(in_dir), str(out_dir), **BATCH_DEFAULTS)
    assert source.read_bytes() == before


def test_f01_symlinked_destination_is_rejected(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    source = in_dir / "art.png"
    _gray().save(source)
    before = source.read_bytes()
    os.symlink(source, out_dir / "art_png_dithered.png")

    assert not process_directory(str(in_dir), str(out_dir), **BATCH_DEFAULTS)
    assert source.read_bytes() == before


def test_f02_case_only_destination_collision(tmp_path):
    """Two sources differing only by case must not silently collapse into one output."""
    a, b, out_dir = tmp_path / "a", tmp_path / "b", tmp_path / "out"
    a.mkdir()
    b.mkdir()
    out_dir.mkdir()
    _gray().save(a / "Photo.png")
    _gray((12, 12)).save(b / "photo.png")

    ok = main(["--input", str(a), str(b), "-o", str(out_dir)]) == 0
    # Both sources always survive; on a case-folding filesystem the batch must refuse.
    assert (a / "Photo.png").exists() and (b / "photo.png").exists()
    if folds_case(str(out_dir)):
        assert not ok
        assert list(out_dir.glob("*.png")) == []
    else:
        assert ok
        assert len(list(out_dir.glob("*.png"))) == 2


def test_f03_symlinked_output_subfolder_cannot_escape(tmp_path):
    """A symlinked destination folder must not redirect writes into the source tree."""
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    (in_dir / "nested").mkdir(parents=True)
    out_dir.mkdir()
    _gray().save(in_dir / "nested" / "art.png")
    os.symlink(in_dir / "nested", out_dir / "nested")

    assert not process_directory(str(in_dir), str(out_dir), **BATCH_DEFAULTS)
    assert sorted(p.name for p in (in_dir / "nested").iterdir()) == ["art.png"]


def test_f07_output_root_that_is_a_file_fails_cleanly(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _gray().save(in_dir / "art.png")
    blocker = tmp_path / "out"
    blocker.write_text("not a directory")

    assert not process_directory(str(in_dir), str(blocker), **BATCH_DEFAULTS)
    assert blocker.read_text() == "not a directory"


def test_destination_cannot_enter_an_input_tree_inside_the_output_root(tmp_path):
    """Staying inside the output root is not enough when the input lives under it too."""
    out = tmp_path / "out"
    source = out / "source"
    (source / "nested").mkdir(parents=True)
    _gray().save(source / "nested" / "art.png")
    os.symlink(source / "nested", out / "nested", target_is_directory=True)

    assert main(["--input", str(source), "-o", str(out)]) != 0
    assert sorted(p.name for p in (source / "nested").iterdir()) == ["art.png"]


def test_planned_file_and_directory_conflict_is_a_planning_error(tmp_path):
    """One job's output file cannot be another job's required output folder."""
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    (in_dir / "a_png_dithered.png").mkdir(parents=True)
    _gray().save(in_dir / "a.png")
    _gray().save(in_dir / "a_png_dithered.png" / "b.png")

    assert not process_directory(str(in_dir), str(out_dir), **BATCH_DEFAULTS)
    assert list(out_dir.rglob("*.png")) == []  # nothing published, not one-of-two


def test_existing_file_on_the_destination_path_is_a_planning_error(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    (in_dir / "nested").mkdir(parents=True)
    _gray().save(in_dir / "nested" / "art.png")
    out_dir.mkdir()
    (out_dir / "nested").write_text("a file, not a folder")

    assert not process_directory(str(in_dir), str(out_dir), **BATCH_DEFAULTS)
    assert (out_dir / "nested").read_text() == "a file, not a folder"
