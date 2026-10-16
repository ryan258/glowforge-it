"""PNG/SVG rendering and publishing one image's output set."""

import pytest
import numpy as np
from PIL import Image

from glowforge_it.batch import run_batch
from glowforge_it.export import prep_for_glowforge, render_svg_document
from glowforge_it.settings import ProcessingSettings


@pytest.mark.parametrize("mark", [{"stamp_text": "ORDER-42"}, {"qr_text": "hello"}])
def test_outside_shape_personalization_preserves_previous_export(tmp_path, mark):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    Image.new("L", (300, 300), 255).save(source)
    output.write_bytes(b"previous generation")
    with pytest.raises(ValueError, match="outside the usable shape"):
        prep_for_glowforge(
            str(source), str(output), settings=ProcessingSettings(circle_cut=True, no_border=True, render_mode="silhouette", **mark), quiet=True,
        )
    assert output.read_bytes() == b"previous generation"
    assert not list(tmp_path.glob(".gf-*"))
    assert not list(tmp_path.glob("output_*.png"))


@pytest.mark.parametrize("layers", [2, 3, 4])
@pytest.mark.parametrize("shape", [None, "circle_cut", "heart_cut"])
def test_tone_layers_are_exclusive_with_default_border(tmp_path, layers, shape):
    source = tmp_path / "source.png"
    Image.new("L", (40, 40), 128).save(source)
    result = prep_for_glowforge(
        str(source), str(tmp_path / "output.png"), settings=ProcessingSettings(tone_layers=layers, contrast=1, sharpen_radius=0,
                                    **({shape: True} if shape else {})),
        quiet=True,
    )
    coverage = np.zeros((40, 40), dtype=np.uint8)
    for path in result["layer_paths"]:
        with Image.open(path) as image:
            rgba = np.asarray(image.convert("RGBA"))
            coverage += (rgba[:, :, 0] == 0) & (rgba[:, :, 3] > 0)
    assert coverage.max() == 1
    # The primary export retains its ordinary border setting.
    if shape is None:
        with Image.open(result["output_path"]) as primary:
            assert primary.getpixel((0, 0)) == 0


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

    assert run_batch(
        [str(in_dir)], str(out_dir),
        settings=ProcessingSettings(black_thresh=0, white_thresh=255, dither_thresh=128, clean_solids=False, clean_solids_black=35, clean_solids_white=220, invert=False, no_border=False, denoise_radius=0, contrast=1.5, sharpen_radius=2.0, sharpen_percent=150, sharpen_threshold=3, circle_cut=True, heart_cut=False, svg_cut=True), width_in=1.0, height_in=1.0, preset_name=None,
        )

    svg_files = list(out_dir.glob("*.svg"))
    png_files = list(out_dir.glob("*.png"))
    assert len(svg_files) == 1
    assert len(png_files) == 1
    with open(svg_files[0]) as f:
        content = f.read()
    assert "<circle" in content


def test_centerline_style_linework_sidecar_is_vector_and_aligned(tmp_path):
    source = tmp_path / "line.png"
    output = tmp_path / "line_out.png"
    image = Image.new("L", (40, 40), 255)
    for x in range(8, 32):
        image.putpixel((x, 20), 0)
    image.save(source)

    result = prep_for_glowforge(
        str(source), str(output), width_in=1.0, height_in=1.0,
        settings=ProcessingSettings(contrast=1.0, sharpen_radius=0, sharpen_percent=0, no_border=True, svg_linework=True), quiet=True,
    )

    linework = tmp_path / "line_out_linework.svg"
    assert result["linework_path"] == str(linework)
    content = linework.read_text()
    assert 'data-role="centerline-style-linework"' in content
    assert '<path ' in content
    assert '<image ' not in content


def test_registered_tone_layers_are_aligned_png_sidecars_and_manifest_outputs(tmp_path):
    source = tmp_path / "tones.png"
    output = tmp_path / "tones_out.png"
    image = Image.new("L", (24, 24))
    for x in range(24):
        for y in range(24):
            image.putpixel((x, y), (x * 255) // 23)
    image.save(source)

    result = prep_for_glowforge(
        str(source), str(output), width_in=1.0, height_in=1.0,
        settings=ProcessingSettings(contrast=1.0, sharpen_radius=0, sharpen_percent=0, no_border=True, tone_layers=3, manifest=True), quiet=True,
    )

    layers = sorted(tmp_path.glob("tones_out_tone*of3.png"))
    assert len(layers) == 3
    assert all(Image.open(path).size == (300, 300) for path in layers)
    manifest = (tmp_path / "tones_out_manifest.json").read_text()
    assert '"role": "registered-exclusive-tone-layer"' in manifest
    assert result["layer_paths"] == [str(path) for path in layers]


def test_protected_personalization_sidecar_requires_clear_space(tmp_path):
    source = tmp_path / "blank.png"
    output = tmp_path / "blank_out.png"
    Image.new("L", (40, 40), 255).save(source)

    result = prep_for_glowforge(
        str(source), str(output), width_in=1.0, height_in=1.0,
        settings=ProcessingSettings(contrast=1.0, sharpen_radius=0, sharpen_percent=0, no_border=True, stamp_text="ORDER-42", stamp_size_px=24, stamp_margin_px=12, manifest=True), quiet=True,
    )

    stamp = tmp_path / "blank_out_stamp.png"
    assert stamp.exists()
    assert result["stamp_path"] == str(stamp)
    assert '"role": "personalization-stamp"' in (tmp_path / "blank_out_manifest.json").read_text()


def test_protected_qr_sidecar_is_manifested_separately(tmp_path):
    source = tmp_path / "blank_qr.png"
    output = tmp_path / "blank_qr_out.png"
    Image.new("L", (40, 40), 255).save(source)

    result = prep_for_glowforge(
        str(source), str(output), width_in=1.0, height_in=1.0,
        settings=ProcessingSettings(contrast=1.0, sharpen_radius=0, sharpen_percent=0, no_border=True, qr_text="HELLO-42", qr_module_px=4, qr_margin_px=12, manifest=True), quiet=True,
    )

    qr = tmp_path / "blank_qr_out_qr.png"
    assert qr.exists()
    assert result["qr_path"] == str(qr)
    manifest = (tmp_path / "blank_qr_out_manifest.json").read_text()
    assert '"role": "protected-qr-mark"' in manifest


def test_f04_blocked_svg_sidecar_preserves_existing_png(tmp_path):
    source = tmp_path / "art.png"
    Image.new("RGB", (30, 30), "gray").save(source)
    output = tmp_path / "out.png"
    output.write_bytes(b"previous")
    (tmp_path / "out_cut.svg").mkdir()

    with pytest.raises(IsADirectoryError):
        prep_for_glowforge(str(source), str(output), settings=ProcessingSettings(circle_cut=True, svg_cut=True))
    assert output.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".gf-*"))


def test_workflow_manifest_keeps_sidecar_roles(tmp_path):
    import json
    from glowforge_it.workflow import WorkflowOptions

    source = tmp_path / "blank.png"
    output = tmp_path / "out.png"
    Image.new("L", (40, 40), 255).save(source)
    prep_for_glowforge(
        str(source), str(output), width_in=1.0, height_in=1.0, workflow=WorkflowOptions(material_mode="darkening"),
        settings=ProcessingSettings(no_border=True, stamp_text="ORDER-42", svg_linework=True, tone_layers=2, manifest=True), quiet=True,
    )
    outputs = json.loads((tmp_path / "out_manifest.json").read_text())["outputs"]
    roles = {name: entry.get("role") for name, entry in outputs.items()}
    assert roles["out_stamp.png"] == "personalization-stamp"
    assert roles["out_linework.svg"] == "centerline-style-linework"
    assert roles["out_tone01of2.png"] == roles["out_tone02of2.png"] == "registered-exclusive-tone-layer"


def test_workflow_runs_without_optional_reportlab(tmp_path, monkeypatch):
    """reportlab is an optional extra; only --proof-sheet may require it."""
    import importlib.metadata
    from glowforge_it import contracts
    from glowforge_it.workflow import WorkflowOptions

    real = importlib.metadata.version

    def missing_reportlab(name):
        if name == "reportlab":
            raise importlib.metadata.PackageNotFoundError(name)
        return real(name)

    monkeypatch.setattr(contracts, "version", missing_reportlab)
    source = tmp_path / "a.png"
    Image.new("L", (40, 40), 255).save(source)
    result = prep_for_glowforge(
        str(source), str(tmp_path / "o.png"), workflow=WorkflowOptions(svg_operations=True, material_mode="darkening"), quiet=True,
    )
    assert result["workflow_summary"]["runtime"]["reportlab"] is None


def _circle(svg):
    import re
    return [float(v) for v in re.search(r'cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', svg).groups()]


def test_svg_cut_circle_registers_with_the_raster_mask_to_sub_pixel():
    """Roadmap 3B: vector and raster agree far better than 0.001 in (0.3 px at 300 DPI)."""
    from glowforge_it.imaging import transform_image
    from glowforge_it.workflow import WorkflowOptions, layout, render_operations

    for size in ((1200, 1200), (1201, 900)):
        out = transform_image(Image.new("L", size, 128), ProcessingSettings(circle_cut=True, no_border=True))
        ys, xs = np.nonzero(np.asarray(out.getchannel("A")))
        want = ((xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2, (xs.max() + 1 - xs.min()) / 2)
        legacy = _circle(render_svg_document(out, circle_cut=True))
        options = WorkflowOptions(svg_operations=True, material_mode="darkening")
        unified = _circle(render_operations(out, options, layout(options, out.size), circle_cut=True))
        assert legacy == pytest.approx(want, abs=1e-6)
        assert unified == pytest.approx(want, abs=1e-6)


def test_svg_heart_centroid_registers_with_the_raster_mask():
    """Extents differ by design (a raster covers every pixel cell the outline touches), so
    compare area centroids: within 0.3 px, i.e. the roadmap's 0.001 in at 300 DPI."""
    from glowforge_it.geometry import heart_cut_points
    from glowforge_it.imaging import transform_image

    out = transform_image(Image.new("L", (1200, 1200), 128), ProcessingSettings(heart_cut=True, no_border=True))
    ys, xs = np.nonzero(np.asarray(out.getchannel("A")))
    x, y = np.array(heart_cut_points(*out.size)).T
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    area = cross.sum() / 2
    centroid = (((x + x1) * cross).sum() / (6 * area), ((y + y1) * cross).sum() / (6 * area))
    assert centroid == pytest.approx((xs.mean() + 0.5, ys.mean() + 0.5), abs=0.3)
