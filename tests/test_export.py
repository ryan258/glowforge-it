"""PNG/SVG rendering and publishing one image's output set."""

import pytest
from PIL import Image

from glowforge_it.batch import process_directory
from glowforge_it.export import prep_for_glowforge, render_svg_document


def test_svg_document_rendering():
    img = Image.new("RGBA", (300, 300), (255, 255, 255, 255))
    circle_svg = render_svg_document(img, circle_cut=True)
    assert "<circle" in circle_svg
    assert 'stroke="#0000ff"' in circle_svg
    assert "data:image/png;base64," in circle_svg

    heart_svg = render_svg_document(img, heart_cut=True)
    assert "<polygon" in heart_svg
    assert 'stroke="#0000ff"' in heart_svg

    with pytest.raises(ValueError, match="SVG cut output requires"):
        render_svg_document(img, circle_cut=False, heart_cut=False)


def test_batch_svg_cut_output(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    img = Image.new("RGB", (30, 30), "gray")
    img.save(in_dir / "sample.png")

    assert process_directory(
        str(in_dir), str(out_dir),
        black_thresh=0, white_thresh=255, dither_thresh=128,
        clean_solids=False, clean_solids_black=35, clean_solids_white=220,
        invert=False, width_in=1.0, height_in=1.0, no_border=False,
        denoise_radius=0, contrast=1.5, sharpen_radius=2.0,
        sharpen_percent=150, sharpen_threshold=3,
        circle_cut=True, heart_cut=False, preset_name=None,
        svg_cut=True,
    )

    svg_files = list(out_dir.glob("*.svg"))
    png_files = list(out_dir.glob("*.png"))
    assert len(svg_files) == 1
    assert len(png_files) == 1
    with open(svg_files[0]) as f:
        content = f.read()
    assert "<circle" in content


def test_f04_blocked_svg_sidecar_preserves_existing_png(tmp_path):
    source = tmp_path / "art.png"
    Image.new("RGB", (30, 30), "gray").save(source)
    output = tmp_path / "out.png"
    output.write_bytes(b"previous")
    (tmp_path / "out_cut.svg").mkdir()

    with pytest.raises(IsADirectoryError):
        prep_for_glowforge(str(source), str(output), circle_cut=True, svg_cut=True)
    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".gf-*"))
