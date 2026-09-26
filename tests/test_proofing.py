"""Mode-agnostic preset audition and final-size proofing."""

import json

from PIL import Image, ImageDraw

from glowforge_it.cli import build_parser, main
from glowforge_it.proofing import render_audition_sheet, run_audition
from glowforge_it.settings import resolve_settings
from glowforge_it.workflow import WorkflowOptions


def candidate(name):
    args = build_parser().parse_args(["--preset", name])
    settings = resolve_settings(args)
    settings.validate()
    return name, settings


def source_image():
    image = Image.new("L", (80, 40), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 28, 34), fill=20)
    draw.ellipse((35, 5, 74, 34), fill=128)
    return image


def test_render_audition_sheet_uses_full_size_candidates_and_records_metrics(tmp_path):
    source_path = tmp_path / "art.png"
    source_image().save(source_path)

    sheet, metadata = render_audition_sheet(
        str(source_path),
        [candidate("photo-soft"), candidate("line-art")],
        width_in=1.0,
        height_in=1.0,
    )
    try:
        assert sheet.mode == "RGB"
        assert sheet.size[0] > 0 and sheet.size[1] > 0
        assert metadata["schema_version"] == "1.0"
        assert metadata["source"]["original_size"] == [80, 40]
        assert metadata["audition"]["display"]["machine_artifact"] is False
        assert metadata["audition"]["candidate_presets"] == ["photo-soft", "line-art"]
        assert len(metadata["candidates"]) == 2
        for record in metadata["candidates"]:
            assert record["output"]["size_px"] == [300, 300]
            assert record["output"]["physical_size_in"] == [1.0, 1.0]
            assert 0 <= record["burn"]["coverage"] <= 1
            assert record["display"]["machine_artifact"] is False
    finally:
        sheet.close()


def test_run_audition_publishes_sheet_and_recipe_record_atomically(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "proofs"
    input_dir.mkdir()
    source_path = input_dir / "art.png"
    source_image().save(source_path)
    original = source_path.read_bytes()

    result = run_audition(
        [str(input_dir)],
        str(output_dir),
        [candidate("photo-soft"), candidate("stamp")],
        width_in=1.0,
        height_in=1.0,
        quiet=True,
    )

    assert result
    assert result.written_count == 1
    item = result.items[0]
    assert item.status == "written"
    assert item.output_path.endswith("art_audition.png")
    assert item.manifest_path.endswith("art_audition.json")
    assert source_path.read_bytes() == original

    with Image.open(item.output_path) as sheet:
        assert sheet.mode == "RGB"
    metadata = json.loads((output_dir / "art_audition.json").read_text())
    assert metadata["outputs"]["art_audition.png"]["sha256"]
    assert metadata["candidates"][0]["recipe"]["contrast"] == 1.2
    assert metadata["candidates"][1]["preset"] == "stamp"

    skipped = run_audition(
        [str(input_dir)],
        str(output_dir),
        [candidate("photo-soft"), candidate("stamp")],
        width_in=1.0,
        height_in=1.0,
        existing="skip",
        quiet=True,
    )
    assert skipped
    assert skipped.skipped_count == 1
    assert skipped.items[0].status == "skipped"


def test_audition_dry_run_does_not_create_output_directory(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "proofs"
    input_dir.mkdir()
    source_image().save(input_dir / "art.png")

    result = run_audition(
        [str(input_dir)],
        str(output_dir),
        [candidate("photo-soft"), candidate("line-art")],
        width_in=1.0,
        height_in=1.0,
        dry_run=True,
        quiet=True,
    )

    assert result
    assert result.is_dry_run is True
    assert result.items[0].status == "planned"
    assert result.items[0].output_size == (300, 300)
    assert not output_dir.exists()


def test_audition_rejects_machine_artifact_workflow(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source_image().save(input_dir / "art.png")

    result = run_audition(
        [str(input_dir)],
        str(tmp_path / "proofs"),
        [candidate("photo-soft")],
        workflow=WorkflowOptions(svg_operations=True),
        quiet=True,
    )

    assert not result
    assert result.exit_code == 2
    assert "mode-agnostic proof" in result.errors[0]


def test_cli_audition_writes_only_proof_artifacts(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "proofs"
    input_dir.mkdir()
    source_image().save(input_dir / "art.png")

    exit_code = main(
        [
            "--audition",
            "photo-soft",
            "line-art",
            "--input",
            str(input_dir),
            "-o",
            str(output_dir),
            "-w",
            "1",
            "-h",
            "1",
            "--quiet",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in output_dir.iterdir()) == [
        "art_audition.json",
        "art_audition.png",
    ]


def test_audition_shares_the_batch_destination_namespace(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source_image().save(input_dir / "art.png")
    source_image().save(input_dir / "art.jpg")
    candidates = [candidate("photo-soft"), candidate("line-art")]

    # art.png and art.jpg both want art_audition.*; nothing may be written.
    collided = run_audition([str(input_dir)], str(tmp_path / "proofs"), candidates, quiet=True)
    assert collided.exit_code == 1 and "both map to" in collided.errors[0]
    assert not list((tmp_path / "proofs").glob("*_audition.*"))

    (input_dir / "art.jpg").unlink()
    assert run_audition([str(input_dir)], str(tmp_path / "proofs"), candidates, quiet=True)
    reused = run_audition([str(input_dir)], str(tmp_path / "proofs"), candidates,
                          existing="skip", quiet=True)
    assert reused.skipped_count == 1
