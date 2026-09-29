"""Protected personalization text-mask tests."""

import pytest
from PIL import Image, ImageDraw

from glowforge_it.personalization import render_text_stamp
from glowforge_it.imaging import transform_image
from glowforge_it.settings import ProcessingSettings


@pytest.mark.parametrize("shape", ["circle_cut", "heart_cut"])
def test_text_stamp_must_fit_inside_shape(shape):
    image = transform_image(Image.new("L", (300, 300), 255), settings=ProcessingSettings(no_border=True, **{shape: True}))
    with pytest.raises(ValueError, match="outside the usable shape"):
        render_text_stamp(image, "ORDER-42")
    stamp, record = render_text_stamp(image, "OK", margin_px=130)
    assert record["shape_checked"] is True
    assert stamp.size == image.size


def test_text_stamp_is_a_separate_binary_mask_with_recorded_bounds():
    image = Image.new("1", (300, 120), 1)
    stamp, record = render_text_stamp(image, "ORDER-42", size_px=24, margin_px=12)

    assert stamp.mode == "1"
    assert stamp.size == image.size
    assert stamp.getbbox()
    assert record["overlap_checked"] is True
    assert record["position"] == "bottom-left"


def test_text_stamp_rejects_existing_burn_overlap():
    blank = Image.new("1", (300, 120), 1)
    _, record = render_text_stamp(blank, "ORDER-42", size_px=24, margin_px=12)
    image = Image.new("1", blank.size, 1)
    ImageDraw.Draw(image).rectangle(record["bounds_px"], fill=0)

    with pytest.raises(ValueError, match="overlap"):
        render_text_stamp(image, "ORDER-42", size_px=24, margin_px=12)


def test_text_stamp_rejects_characters_the_font_would_draw_as_boxes():
    """Pillow's bundled font is ASCII-only: José, Привет and emoji all came out as identical empty boxes."""
    canvas = Image.new("L", (600, 200), 255)
    for text in ("José", "Привет", "李雷", "Hi \U0001F600"):
        with pytest.raises(ValueError, match="ASCII only"):
            render_text_stamp(canvas, text, size_px=40)
    stamp, _ = render_text_stamp(canvas, "Jose & Zoe-42 #7", size_px=40)
    assert stamp.getbbox() is not None
