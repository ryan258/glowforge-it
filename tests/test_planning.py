"""Discovery, naming, sizing preflight, path protection, destination namespace."""

import os
import re

import pytest
from PIL import Image

from tests.helpers import folds_case, gray as _gray
from glowforge_it.batch import run_batch
from glowforge_it.cli import main
from glowforge_it.geometry import resolve_oriented_geometry
from glowforge_it.settings import ProcessingSettings


def _run_batch(tmp_path, images, preset_name=None, width_in=None, **settings):
    """Run run_batch over {relpath: PIL image} and return sorted output relpaths."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    for rel, img in images.items():
        dest = in_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)

    assert run_batch([str(in_dir)], str(out_dir), ProcessingSettings(**settings),
                     preset_name=preset_name, width_in=width_in)
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


def test_batch_names_non_default_recipes_by_digest(tmp_path):
    image = {"pic.png": Image.new("RGB", (8, 8), "gray")}
    # Explicit defaults are still the default recipe.
    assert _run_batch(tmp_path / "a", image, contrast=1.5, black_thresh=0) == ["pic_png_dithered.png"]
    first = _run_batch(tmp_path / "b", image, invert=True, no_border=True, black_thresh=20)
    assert re.fullmatch(r"pic_png_r[0-9a-f]{12}\.png", first[0])
    assert _run_batch(tmp_path / "c", image, black_thresh=20, no_border=True, invert=True) == first
    assert _run_batch(tmp_path / "d", image, invert=True, no_border=True, black_thresh=21) != first


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
        resolve_oriented_geometry(str(img_path), width_in=12.0, height_in=12.0, max_pixels=20_000_000, machine="spark")

    # Within bounds passes without error
    suffix = resolve_oriented_geometry(str(img_path), width_in=5.0, height_in=5.0, max_pixels=20_000_000, machine="spark")[4]
    assert suffix == "_w5h5"


def test_existing_output_policies(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    img = Image.new("RGB", (30, 30), "gray")
    img.save(in_dir / "pic.png")

    # First pass writes output
    assert run_batch([str(in_dir)], str(out_dir), existing="overwrite")

    # Second pass with 'skip' policy succeeds
    assert run_batch([str(in_dir)], str(out_dir), existing="skip")

    # Second pass with 'error' policy fails
    assert not run_batch([str(in_dir)], str(out_dir), existing="error")


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

    assert not run_batch([str(in_dir)], str(out_dir))
    assert source.read_bytes() == before


def test_f01_symlinked_destination_is_rejected(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    source = in_dir / "art.png"
    _gray().save(source)
    before = source.read_bytes()
    os.symlink(source, out_dir / "art_png_dithered.png")

    assert not run_batch([str(in_dir)], str(out_dir))
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

    assert not run_batch([str(in_dir)], str(out_dir))
    assert sorted(p.name for p in (in_dir / "nested").iterdir()) == ["art.png"]


def test_f07_output_root_that_is_a_file_fails_cleanly(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    _gray().save(in_dir / "art.png")
    blocker = tmp_path / "out"
    blocker.write_text("not a directory")

    assert not run_batch([str(in_dir)], str(blocker))
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

    assert not run_batch([str(in_dir)], str(out_dir))
    assert list(out_dir.rglob("*.png")) == []  # nothing published, not one-of-two


def test_existing_file_on_the_destination_path_is_a_planning_error(tmp_path):
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    (in_dir / "nested").mkdir(parents=True)
    _gray().save(in_dir / "nested" / "art.png")
    out_dir.mkdir()
    (out_dir / "nested").write_text("a file, not a folder")

    assert not run_batch([str(in_dir)], str(out_dir))
    assert (out_dir / "nested").read_text() == "a file, not a folder"


def test_filename_preset_inference(tmp_path):
    """Filenames with *--[mode].png automatically select the matching preset when none is given."""
    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    _gray().save(in_dir / "cat--photo-soft.png")
    _gray().save(in_dir / "fox--line-art.png")
    _gray().save(in_dir / "plain.png")

    assert run_batch([str(in_dir)], str(out_dir))
    produced = sorted(p.name for p in out_dir.glob("*.png"))
    assert "plain_png_dithered.png" in produced
    inferred = [name for name in produced if name.startswith(("cat--", "fox--"))]
    assert len(inferred) == 2 and all(re.search(r"_png_r[0-9a-f]{12}\.png$", n) for n in inferred)
    assert inferred[0].rpartition("_")[2] != inferred[1].rpartition("_")[2]


def test_filename_preset_inference_can_reuse_a_manifest_backed_output(tmp_path):
    """The inferred per-file preset is part of verified reuse, not batch defaults."""
    from glowforge_it.batch import run_batch

    in_dir, out_dir = tmp_path / "in", tmp_path / "out"
    in_dir.mkdir()
    _gray().save(in_dir / "cat--photo-soft.png")

    first = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(manifest=True))
    assert first.exit_code == 0

    reused = run_batch(
        [str(in_dir)], str(out_dir), settings=ProcessingSettings(manifest=True), existing="skip"
    )
    assert reused.exit_code == 0
    assert reused.skipped_count == 1
    assert reused.items[0].status == "skipped"
