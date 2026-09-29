"""Deterministic vector linework sidecar tests."""

import numpy as np
import pytest
from PIL import Image, ImageDraw

from glowforge_it.vector import render_centerline_svg, skeletonize, trace_skeleton


def test_skeleton_preserves_a_thin_line_and_traces_a_path():
    image = Image.new("1", (32, 32), 1)
    ImageDraw.Draw(image).line((4, 16, 27, 16), fill=0, width=1)

    skeleton = skeletonize(image)
    paths = trace_skeleton(skeleton)

    assert skeleton.dtype == bool
    assert int(skeleton.sum()) == 24
    assert paths
    assert len(max(paths, key=len)) == 24


def test_centerline_svg_is_aligned_vector_only_output():
    image = Image.new("L", (12, 8), 255)
    image.putpixel((3, 4), 0)
    svg = render_centerline_svg(image, source_label="test & source.png")

    assert 'width="0.040000in"' in svg
    assert 'height="0.026667in"' in svg
    assert 'data-source="test &amp; source.png"' in svg
    assert 'data-role="centerline-style-linework"' in svg
    assert '<path ' in svg
    assert '<image ' not in svg


def test_linework_refuses_art_that_traces_to_too_many_paths():
    """Dither-like dots become one path each; fail loudly instead of writing a multi-MB SVG."""
    image = Image.new("1", (20, 20), 1)
    for x in range(1, 20, 3):
        for y in range(1, 20, 3):
            image.putpixel((x, y), 0)
    assert render_centerline_svg(image, max_paths=100)
    with pytest.raises(ValueError, match="paths .*limit 10"):
        render_centerline_svg(image, max_paths=10)


def test_an_isolated_pixel_is_drawn_not_dropped():
    """A bare `M x y` renders nothing; the dot needs a zero-length segment for the round cap."""
    image = Image.new("L", (12, 8), 255)
    image.putpixel((3, 4), 0)
    assert '<path d="M 3.500 4.500 L 3.500 4.500" />' in render_centerline_svg(image)
