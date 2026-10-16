"""Stage 2 tests: shared validation, structured BatchResult, dry-run, manifests, replay, recipes, and memory limits."""

import json
import os
import re

import pytest
from PIL import Image

from tests.helpers import gray
from glowforge_it import __version__
from glowforge_it.batch import BatchResult, run_batch
from glowforge_it.cli import main, memory_size_type
from glowforge_it.planning import estimate_image_memory, verify_job_manifest
from glowforge_it.publication import sha256_file
from glowforge_it.settings import (
    ProcessingSettings,
    ValidationError,
    load_recipe_file,
    resolve_settings,
)


def test_shared_typed_validation_direct_api(tmp_path):
    """Direct API calls must enforce the exact same validation invariants as the CLI."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    gray().save(in_dir / "art.png")

    # Black threshold > white threshold
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(black_thresh=200, white_thresh=100))
    assert not res
    assert res.exit_code == 2
    assert "cannot be greater than white threshold" in res.errors[0]

    # Clean solids black > white
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(clean_solids_black=200, clean_solids_white=100))
    assert not res
    assert res.exit_code == 2

    # Mutually exclusive circle and heart
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(circle_cut=True, heart_cut=True))
    assert not res
    assert res.exit_code == 2
    assert "Cannot apply both --circle-cut and --heart-cut" in res.errors[0]

    # SVG cut without shape cut
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(svg_cut=True, circle_cut=False, heart_cut=False))
    assert not res
    assert res.exit_code == 2
    assert "--svg-cut requires" in res.errors[0]

    # Invalid contrast
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(contrast=0))
    assert not res
    assert res.exit_code == 2

    # Invalid denoise (even integer)
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(denoise_radius=4))
    assert not res
    assert res.exit_code == 2

    # Empty material label
    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(material="   "))
    assert not res
    assert res.exit_code == 2


def test_structured_batch_result_contract(tmp_path):
    """BatchResult provides structured outcome items and backwards-compatible boolean behavior."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    gray().save(in_dir / "a.png")
    gray().save(in_dir / "b.png")

    result = run_batch([str(in_dir)], str(out_dir))
    assert isinstance(result, BatchResult)
    assert bool(result) is True
    assert result.exit_code == 0
    assert result.written_count == 2
    assert result.skipped_count == 0
    assert result.failed_count == 0
    assert result.total_planned == 2
    assert len(result.items) == 2
    assert all(item.status == "written" for item in result.items)

    # Test dictionary / JSON serialization
    res_dict = result.to_dict()
    assert res_dict["success"] is True
    assert res_dict["summary"]["written"] == 2
    json_str = result.to_json()
    parsed = json.loads(json_str)
    assert parsed["summary"]["written"] == 2

    # Second run with 'skip' policy
    skip_res = run_batch([str(in_dir)], str(out_dir), existing="skip")
    assert bool(skip_res) is True
    assert skip_res.exit_code == 0
    assert skip_res.written_count == 0
    assert skip_res.skipped_count == 2
    assert skip_res.total_planned == 2
    assert all(item.status == "skipped" for item in skip_res.items)


def test_pure_dry_run_zero_disk_mutation(tmp_path):
    """Dry run previews destinations and dimensions without creating folders or writing files."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "nonexistent_dry_run_out"
    in_dir.mkdir()
    gray((20, 20)).save(in_dir / "art.png")

    assert not out_dir.exists()

    result = run_batch(
        [str(in_dir)],
        str(out_dir),
        dry_run=True,
        width_in=2.0,
        height_in=2.0,
        settings=ProcessingSettings(svg_cut=True, circle_cut=True),
        )

    # Verifications:
    assert bool(result) is True
    assert result.is_dry_run is True
    assert result.total_planned == 1
    assert result.written_count == 0
    assert result.items[0].status == "planned"
    assert re.fullmatch(r"art_png_r[0-9a-f]{12}_w2h2\.png", os.path.basename(result.items[0].output_path))
    assert result.items[0].svg_path.endswith("_cut.svg")

    # CRITICAL: out_dir MUST NOT have been created on disk!
    assert not out_dir.exists()


def test_versioned_job_manifest_generation_and_atomic_publication(tmp_path):
    """Manifests are published atomically alongside outputs with full metadata and SHA-256 hashes."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    src_file = in_dir / "source.png"
    gray((30, 30)).save(src_file)

    result = run_batch(
        [str(in_dir)],
        str(out_dir),
        settings=ProcessingSettings(manifest=True, svg_cut=True, circle_cut=True),
        prompt="A robotic raven on a pine tree",
        model="midjourney-v6",
        width_in=1.0,
        height_in=1.0,
    )

    assert result.exit_code == 0
    item = result.items[0]
    assert item.manifest_path is not None
    assert os.path.exists(item.manifest_path)
    assert os.path.exists(item.output_path)
    assert os.path.exists(item.svg_path)

    # Inspect manifest structure
    with open(item.manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    assert manifest_data["schema_version"] == "1.0"
    assert manifest_data["tool"]["name"] == "glowforge-it"
    assert manifest_data["tool"]["version"] == __version__
    assert manifest_data["provenance"]["prompt"] == "A robotic raven on a pine tree"
    assert manifest_data["provenance"]["model"] == "midjourney-v6"

    # Verify source hash
    expected_src_sha = sha256_file(str(src_file))
    assert manifest_data["source"]["sha256"] == expected_src_sha
    assert manifest_data["source"]["filename"] == "source.png"

    # Verify output hashes
    out_png_sha = sha256_file(item.output_path)
    svg_sha = sha256_file(item.svg_path)
    assert manifest_data["outputs"][os.path.basename(item.output_path)]["sha256"] == out_png_sha
    assert manifest_data["outputs"][os.path.basename(item.svg_path)]["sha256"] == svg_sha

    # Test replay verification
    valid, errors = verify_job_manifest(item.manifest_path, str(src_file))
    assert valid is True
    assert errors == []

    # Test detection of modified output (tamper check)
    with open(item.output_path, "ab") as f:
        f.write(b"tamper")
    valid_tampered, tamper_errors = verify_job_manifest(item.manifest_path, str(src_file))
    assert valid_tampered is False
    assert any("hash mismatch" in err for err in tamper_errors)


def test_resource_memory_preflight_budget(tmp_path):
    """Memory budget preflight rejects images exceeding the budget without writing files."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    # Reject before rendering when the conservative working-buffer estimate exceeds the budget.
    gray((500, 500)).save(in_dir / "large.png")

    est = estimate_image_memory(str(in_dir / "large.png"))
    assert est > 1_000_000

    # Set budget lower than requirement: 100 KB
    res = run_batch([str(in_dir)], str(out_dir), max_memory=100_000)
    assert res.exit_code == 1
    assert "exceeds budget" in res.errors[0]
    assert not list(out_dir.glob("*.png"))


def test_user_recipe_file_loading_toml_and_json(tmp_path):
    """Recipes can be loaded from TOML or JSON, enforcing schema and precedence."""
    recipe_toml = tmp_path / "custom.toml"
    recipe_toml.write_text(
        """
        [recipe]
        name = "fine-walnut"
        contrast = 2.2
        denoise_radius = 3
        sharpen_radius = 1.5
        fit_mode = "contain"
        clean_solids = true
        """,
        encoding="utf-8",
    )

    data = load_recipe_file(str(recipe_toml))
    assert data["contrast"] == 2.2
    assert data["denoise_radius"] == 3
    assert data["fit_mode"] == "contain"

    # Precedence test: recipe overrides defaults
    class DummyArgs:
        preset = None
        recipe = str(recipe_toml)
        black_thresh = None
        white_thresh = None
        dither_thresh = None
        clean_solids = None
        clean_solids_black = None
        clean_solids_white = None
        invert = None
        no_border = None
        denoise_radius = None
        contrast = None
        sharpen_radius = None
        sharpen_percent = None
        sharpen_threshold = None
        circle_cut = None
        heart_cut = None
        fit_mode = None

    settings = resolve_settings(DummyArgs())
    assert settings.contrast == 2.2
    assert settings.denoise_radius == 3
    assert settings.fit_mode == "contain"
    assert settings.clean_solids is True

    # Unknown key rejects
    bad_toml = tmp_path / "bad.toml"
    bad_toml.write_text("unknown_option = 42\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Unknown key"):
        load_recipe_file(str(bad_toml))


def test_cli_flags_dry_run_json_version(tmp_path, capsys):
    """CLI supports --dry-run, --json, and --version."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    gray().save(in_dir / "art.png")

    # --json output
    exit_code = main(["--input", str(in_dir), "-o", str(out_dir), "--json"])
    assert exit_code == 0
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    assert parsed["success"] is True
    assert parsed["summary"]["written"] == 1

    # Memory size parser
    assert memory_size_type("500MB") == 500 * 1024 * 1024
    assert memory_size_type("1GB") == 1024 * 1024 * 1024
    assert memory_size_type("256K") == 256 * 1024


def test_p1_exif_orientation_memory_estimate(tmp_path):
    """P1: Memory estimate accounts for EXIF orientation when planning output sizes."""
    # Create a 100 x 10 image with EXIF orientation 6 (rotated 90 deg -> 10 x 100 oriented)
    img = Image.new("RGB", (100, 10), color="gray")
    exif = img.getexif()
    exif[274] = 6
    jpeg_path = tmp_path / "rotated.jpg"
    img.save(jpeg_path, format="JPEG", exif=exif)

    # When requested at width_in=1.0 (300px), oriented geometry produces target:
    # 300 x (100 * 300 / 10) = 300 x 3000 pixels.
    est = estimate_image_memory(str(jpeg_path), width_in=1.0)
    assert est > 24 * 300 * 3000  # three live float64 buffers, before other workspace

    # Under a 100,000 byte budget, the batch must reject this rotated image during preflight
    out_dir = tmp_path / "out"
    res = run_batch(
        [str(jpeg_path)],
        str(out_dir),
        width_in=1.0,
        max_memory=100_000,
    )
    assert not res
    assert res.exit_code == 1
    assert "exceeds budget" in res.errors[0]


def test_p2_memory_budget_preflight_does_not_decode_pixels(tmp_path, monkeypatch):
    """P2: Memory check runs ahead of pixel decoding; dry runs reject before exif_transpose."""
    from PIL import ImageOps
    transposed = []
    real_exif_transpose = ImageOps.exif_transpose

    def spy_transpose(im):
        transposed.append(im)
        return real_exif_transpose(im)

    monkeypatch.setattr(ImageOps, "exif_transpose", spy_transpose)

    in_dir = tmp_path / "in"
    in_dir.mkdir()
    gray((50, 50)).save(in_dir / "test.png")

    out_dir = tmp_path / "out"
    result = run_batch(
        [str(in_dir)],
        str(out_dir),
        dry_run=True,
        max_memory=1,  # 1-byte budget forces preflight rejection
    )
    assert not result
    assert result.exit_code == 1
    assert "exceeds budget" in result.errors[0]
    # Verify ImageOps.exif_transpose was never called
    assert len(transposed) == 0


def test_p2_manifest_verification_strictness(tmp_path):
    """P2: Manifest verification enforces schema version, required evidence, and hash matches."""
    # 1. Bare schema_version only: must reject for missing source and output records
    empty_manifest = tmp_path / "empty_manifest.json"
    empty_manifest.write_text('{"schema_version": "1.0"}', encoding="utf-8")
    valid, errors = verify_job_manifest(str(empty_manifest))
    assert valid is False
    assert any("source record" in e for e in errors)
    assert any("outputs record" in e for e in errors)

    # 2. Nonexistent source path passed explicitly: must reject
    valid, errors = verify_job_manifest(str(empty_manifest), source_path=str(tmp_path / "nonexistent.png"))
    assert valid is False
    assert any("does not exist" in e for e in errors)

    # 3. Real run: source file modified must fail verification
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    src_file = in_dir / "item.png"
    gray((40, 40)).save(src_file)

    result = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(manifest=True))
    assert result.exit_code == 0
    item = result.items[0]

    # Tamper with the source file
    src_file.write_bytes(b"corrupted_content")
    valid_mod, mod_errors = verify_job_manifest(item.manifest_path, str(src_file))
    assert valid_mod is False
    assert any("hash mismatch" in e for e in mod_errors)


def test_p2_recipe_options_cli_and_precedence(tmp_path):
    """P2: Recipe options for svg_cut, manifest, material, and thickness are applied by CLI."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    gray((40, 40)).save(in_dir / "test.png")

    recipe_path = tmp_path / "art_recipe.toml"
    recipe_path.write_text(
        """
        [recipe]
        name = "craft-cut"
        circle_cut = true
        svg_cut = true
        manifest = true
        material = "cherry plywood"
        material_thickness_in = 0.125
        """,
        encoding="utf-8",
    )

    exit_code = main(["--input", str(in_dir), "-o", str(out_dir), "--recipe", str(recipe_path)])
    assert exit_code == 0

    # Verify PNG, SVG, and manifest all exist
    pngs = list(out_dir.glob("*.png"))
    svgs = list(out_dir.glob("*.svg"))
    manifests = list(out_dir.glob("*_manifest.json"))
    assert len(pngs) == 1
    assert len(svgs) == 1
    assert len(manifests) == 1

    # Verify manifest recorded recipe and material options
    with open(manifests[0], "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["recipe"]["material"] == "cherry plywood"
    assert meta["recipe"]["material_thickness_in"] == 0.125
    assert meta["recipe"]["svg_cut"] is True
    assert meta["recipe"]["manifest"] is True
    assert len(meta["outputs"]) == 2


def test_p2_shared_validation_types_and_finiteness(tmp_path):
    """P2: ProcessingSettings strictly checks types and finite numeric values."""
    # String instead of bool
    settings = ProcessingSettings(invert="false")
    with pytest.raises(ValidationError, match="must be a boolean"):
        settings.validate()

    # Non-integer denoise
    settings = ProcessingSettings(denoise_radius=3.5)
    with pytest.raises(ValidationError, match="must be an integer"):
        settings.validate()

    # Quoted string threshold
    settings = ProcessingSettings(black_thresh="40")
    with pytest.raises(ValidationError, match="must be an integer"):
        settings.validate()

    # NaN / Inf contrast
    settings = ProcessingSettings(contrast=float("nan"))
    with pytest.raises(ValidationError, match="must be a finite number"):
        settings.validate()

    settings = ProcessingSettings(contrast=float("inf"))
    with pytest.raises(ValidationError, match="must be a finite number"):
        settings.validate()

    # Direct API calls also catch these cleanly through run_batch
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    gray().save(in_dir / "art.png")

    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(invert="false"))
    assert res.exit_code == 2
    assert "must be a boolean" in res.errors[0]

    res = run_batch([str(in_dir)], str(out_dir), settings=ProcessingSettings(contrast=float("nan")))
    assert res.exit_code == 2
    assert "must be a finite number" in res.errors[0]

