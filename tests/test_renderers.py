"""Deterministic alternate binary renderers."""

import numpy as np
import pytest
from PIL import Image

from glowforge_it.imaging import transform_image
from glowforge_it.renderers import render_contour, render_edge, render_halftone, render_hatch, render_ordered
from glowforge_it.settings import ProcessingSettings


@pytest.mark.parametrize("angle", [0, 30, 45, 90, 135])
@pytest.mark.parametrize("cross", [False, True])
def test_white_hatch_never_burns(angle, cross):
    output = render_hatch(Image.new("L", (120, 120), 255), angle=angle, cross=cross)
    assert np.asarray(output).all()


@pytest.mark.parametrize("size", [(120, 120), (151, 91)])
@pytest.mark.parametrize("angle", [15, 45, 90, 135])
def test_angled_halftone_preserves_corner_artwork_and_registration(size, angle):
    source = Image.new("L", size, 255)
    width, height = size
    corners = [(0, 0), (width - 10, 0), (0, height - 10), (width - 10, height - 10)]
    for x, y in corners:
        source.paste(0, (x, y, x + 10, y + 10))
    output = render_halftone(source, cell_px=4, angle=angle)
    assert output.size == size
    burns = ~np.asarray(output)
    for x, y in corners:
        assert burns[y:y + 10, x:x + 10].any()
    assert not burns[20:height - 20, 20:width - 20].any()


def coverage(image):
    values = np.asarray(image.convert("L"))
    return float((values == 0).mean())


def test_ordered_bayer_screen_preserves_binary_endpoints_and_midtones():
    black = render_ordered(Image.new("L", (16, 16), 0), matrix_size=4)
    white = render_ordered(Image.new("L", (16, 16), 255), matrix_size=4)
    mid = render_ordered(Image.new("L", (16, 16), 128), matrix_size=4)

    assert black.mode == "1" and white.mode == "1" and mid.mode == "1"
    assert coverage(black) == 1.0
    assert coverage(white) == 0.0
    assert 0.0 < coverage(mid) < 1.0


def test_variable_cell_halftone_changes_density_without_grayscale_output():
    dark = render_halftone(Image.new("L", (32, 32), 32), cell_px=8)
    light = render_halftone(Image.new("L", (32, 32), 224), cell_px=8)
    angled = render_halftone(Image.new("L", (32, 32), 128), cell_px=8, angle=45)

    assert dark.mode == light.mode == angled.mode == "1"
    assert coverage(dark) > coverage(light) > 0.0
    assert coverage(angled) > 0.0
    assert set(np.asarray(angled.convert("L")).ravel()) <= {0, 255}


def test_directional_hatch_changes_line_coverage_and_crosshatch_density():
    dark = render_hatch(Image.new("L", (48, 48), 32), spacing_px=6, angle=30)
    light = render_hatch(Image.new("L", (48, 48), 224), spacing_px=6, angle=30)
    cross = render_hatch(Image.new("L", (48, 48), 128), spacing_px=6, angle=30, cross=True)

    assert dark.mode == light.mode == cross.mode == "1"
    assert coverage(dark) > coverage(cross) > coverage(light) >= 0.0
    assert set(np.asarray(cross.convert("L")).ravel()) <= {0, 255}


def test_transform_image_dispatches_screen_and_hatch_modes():
    source = Image.new("L", (24, 24), 128)
    for mode, kwargs in (
        ("ordered", {"ordered_matrix_size": 8}),
        ("halftone", {"halftone_cell_px": 6, "halftone_angle": 15}),
        ("hatch", {"hatch_spacing_px": 6, "hatch_angle": 30, "hatch_cross": True}),
    ):
        result = transform_image(
            source,
            settings=ProcessingSettings(render_mode=mode, contrast=1.0, sharpen_radius=0, sharpen_percent=0, no_border=True, **kwargs),
        )
        assert result.mode == "1"
        assert 0.0 < coverage(result) < 1.0


def test_edge_and_contour_renderers_keep_only_structural_marks():
    ramp = Image.new("L", (32, 32), 255)
    for x in range(32):
        ramp.paste(x * 8, (x, 0, x + 1, 32))

    edge_source = Image.new("L", (32, 32), 255)
    edge_source.paste(0, (16, 0, 32, 32))
    edge = render_edge(edge_source, threshold=24)
    contour = render_contour(ramp, levels=8)

    assert edge.mode == contour.mode == "1"
    assert 0.0 < coverage(edge) < 0.5
    assert 0.0 < coverage(contour) < 0.5
    assert coverage(render_edge(Image.new("L", (32, 32), 128), threshold=24)) == 0.0


def test_every_declared_render_mode_has_a_renderer():
    """settings.RENDER_MODES feeds validation and the CLI; the dispatch table must cover exactly it."""
    from glowforge_it.renderers import _RENDERERS
    from glowforge_it.settings import RENDER_MODES
    assert set(_RENDERERS) == set(RENDER_MODES)
