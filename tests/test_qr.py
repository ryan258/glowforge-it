"""Constrained protected QR sidecar tests."""

import pytest
from PIL import Image, ImageDraw

from glowforge_it.qr import render_qr_stamp
from glowforge_it.imaging import transform_image
from glowforge_it.settings import ProcessingSettings


@pytest.mark.parametrize("point", [(12, 12), (32, 32)])
def test_qr_reserves_quiet_zone_and_white_modules(point):
    image = Image.new("1", (180, 180), 1)
    qr, _ = render_qr_stamp(image, "hello", position="top-left")
    assert qr.getpixel(point) != 0  # Quiet zone or white finder-ring module.
    image.putpixel(point, 0)
    with pytest.raises(ValueError, match="overlap"):
        render_qr_stamp(image, "hello", position="top-left")


@pytest.mark.parametrize("shape", ["circle_cut", "heart_cut"])
def test_qr_including_quiet_zone_must_fit_inside_shape(shape):
    image = transform_image(Image.new("L", (300, 300), 255), settings=ProcessingSettings(no_border=True, **{shape: True}))
    with pytest.raises(ValueError, match="outside the usable shape"):
        render_qr_stamp(image, "hello")
    qr, record = render_qr_stamp(image, "hello", module_px=2, margin_px=121)
    assert record["shape_checked"] is True
    assert qr.size == image.size


def test_version_one_qr_stamp_is_binary_and_recorded():
    image = Image.new("1", (300, 300), 1)
    qr, record = render_qr_stamp(image, "HELLO-42", module_px=4, margin_px=12)

    assert qr.mode == "1"
    assert qr.size == image.size
    assert record["version"] == 1
    assert record["error_correction"] == "L"
    assert record["overlap_checked"] is True


def test_qr_payload_and_overlap_are_rejected_safely():
    blank = Image.new("1", (300, 300), 1)
    with pytest.raises(ValueError, match="17 UTF-8 bytes"):
        render_qr_stamp(blank, "123456789012345678", module_px=4)

    image = Image.new("1", blank.size, 1)
    ImageDraw.Draw(image).rectangle((170, 170, 290, 290), fill=0)
    with pytest.raises(ValueError, match="overlap"):
        render_qr_stamp(image, "HELLO", module_px=4, margin_px=12)
