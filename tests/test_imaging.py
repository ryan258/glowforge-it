"""Image-to-image transformation: normalisation, tone, fit, dither, masks."""

import io
import os

import numpy as np
import pytest
from PIL import Image, ImageDraw

from glowforge_it.imaging import transform_image


def test_transparent_png_handling():
    # Create an RGBA image where all pixels are transparent black (0, 0, 0, 0)
    img = Image.new('RGBA', (4, 4), (0, 0, 0, 0))
    processed = transform_image(img, no_border=True)
    # The transparent black pixels should be composited onto white, 
    # and therefore be white (True) in the final output.
    pixels = np.array(processed)
    assert np.all(pixels == True)


def test_exif_orientation_handling():
    # Create a 2x4 image
    img = Image.new('RGB', (2, 4), color='red')
    # Set EXIF orientation to 6 (needs 90 degrees CW rotation to correct)
    exif = img.getexif()
    exif[274] = 6
    
    # Save to buffer and reload to preserve EXIF
    buf = io.BytesIO()
    img.save(buf, format='JPEG', exif=exif)
    buf.seek(0)
    loaded_img = Image.open(buf)
    
    # Run transformation
    processed = transform_image(loaded_img)
    # Swapped dimensions (height becomes width, width becomes height)
    assert processed.size == (4, 2)


def test_dithering_correctness():
    # Create a gray image
    img = Image.new('L', (8, 8), 128)
    processed = transform_image(img)
    assert processed.mode == '1'
    pixels = np.array(processed)
    assert pixels.dtype == bool


def test_denoising_effect():
    # Create an image with high-frequency noise (single-pixel speckle)
    # 5x5 image of 255 (white) with one gray pixel at center
    img = Image.new('L', (5, 5), 255)
    img.putpixel((2, 2), 120)
    
    # Without denoise, the 120 pixel might be dithered or preserved
    # With denoise_radius=3 (median filter), the 120 pixel should be smoothed out by neighbors (all 255)
    processed = transform_image(img, denoise_radius=3, no_border=True)
    pixels = np.array(processed)
    assert np.all(pixels == True) # Single speckle is completely smoothed out to white!


def test_custom_clean_solids_limits():
    # Create a 4x4 image with near-black (40) and near-white (210) pixels
    img = Image.new('L', (4, 4), 40)
    img.putpixel((0, 0), 210)
    
    # With default limits (35 and 220), 40 is not < 35, and 210 is not > 220, so they are not snapped.
    # With custom limits (50 and 200), 40 < 50 (snaps to black/0), and 210 > 200 (snaps to white/255)
    processed = transform_image(
        img, 
        clean_solids=True, 
        clean_solids_black=50, 
        clean_solids_white=200, 
        no_border=True
    )
    pixels = np.array(processed)
    # Output should be pure black (False) for 40 -> 0, except for pixel (0, 0) which is 210 -> 255 (True)
    assert pixels[0, 0] == True
    assert np.all(pixels[1:, 1:] == False)


def test_golden_image():
    # Generate a synthetic image
    img = Image.new('RGBA', (16, 16), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw a black square
    draw.rectangle([4, 4, 8, 8], fill=(0, 0, 0, 255))
    # Draw a transparent square with black background
    draw.rectangle([9, 9, 12, 12], fill=(0, 0, 0, 0))
    # Draw a gray gradient
    for i in range(16):
        for j in range(16):
            if i >= 13:
                img.putpixel((i, j), (i * 15, i * 15, i * 15, 255))
                
    # Define the path for golden image
    golden_dir = os.path.join(os.path.dirname(__file__), "data")
    golden_path = os.path.join(golden_dir, "golden_dithered.png")
    
    # Process the image
    processed = transform_image(img, black_thresh=10, white_thresh=245, dither_thresh=128)
    
    # The fixture is committed; a missing one means the checkout is broken. A test run
    # never writes the expectation it asserts against - regeneration is an explicit act.
    if os.environ.get("GF_UPDATE_GOLDEN") == "1":
        processed.save(golden_path)
        pytest.fail(f"Golden image rewritten at {golden_path} - inspect it, then commit it.")
    assert os.path.exists(golden_path), (
        f"Golden fixture missing at {golden_path}. "
        "Rerun with GF_UPDATE_GOLDEN=1 to regenerate it, then inspect and commit it."
    )

    # Load and compare pixel-for-pixel using NumPy arrays
    golden = Image.open(golden_path)
    assert processed.size == golden.size
    assert processed.mode == golden.mode
    assert np.array_equal(np.array(processed), np.array(golden))


def test_circle_cutout_mask():
    # Create a 16x16 image
    img = Image.new('RGB', (16, 16), (255, 0, 0))
    processed = transform_image(img, circle_cut=True, no_border=True)
    
    # Verify the output is in RGBA mode
    assert processed.mode == 'RGBA'
    
    # Center pixel (8, 8) is inside circle -> opaque (alpha=255)
    # Corner pixel (0, 0) is outside circle -> transparent (alpha=0)
    assert processed.getpixel((8, 8))[3] == 255
    assert processed.getpixel((0, 0))[3] == 0


def test_heart_cutout_mask():
    # Create a 16x16 image
    img = Image.new('RGB', (16, 16), (255, 0, 0))
    processed = transform_image(img, heart_cut=True, no_border=True)
    
    # Verify the output is in RGBA mode
    assert processed.mode == 'RGBA'
    
    # Center pixel (8, 8) is inside heart -> opaque (alpha=255)
    # Bottom-left corner pixel (0, 15) is outside heart -> transparent (alpha=0)
    assert processed.getpixel((8, 8))[3] == 255
    assert processed.getpixel((0, 15))[3] == 0


def test_fit_modes():
    # 100x50 source (2:1 aspect ratio)
    img = Image.new("L", (100, 50), 0)  # black

    # contain mode into a 1x1 inch square (300x300 px) -> 300x150 image with top/bottom white padding
    contained = transform_image(img, width_in=1.0, height_in=1.0, fit_mode="contain", no_border=True)
    assert contained.size == (300, 300)
    arr_c = np.array(contained)
    # top padding should be white (True), middle should be black (False)
    assert arr_c[0, 150] == True
    assert arr_c[150, 150] == False

    # cover mode into a 1x1 inch square (300x300 px) -> fills canvas without white padding
    covered = transform_image(img, width_in=1.0, height_in=1.0, fit_mode="cover", no_border=True)
    assert covered.size == (300, 300)
    arr_cov = np.array(covered)
    assert np.all(arr_cov == False)

    with pytest.raises(ValueError, match="Unsupported fit mode"):
        transform_image(img, width_in=1.0, height_in=1.0, fit_mode="invalid")


def test_f05_cover_fit_allocates_no_oversized_intermediate(monkeypatch):
    """A 20000x1 source into 300x300 used to request 6,000,000 x 300 pixels."""
    budget = 300 * 300
    requested = []
    original = Image.Image.resize

    def spy(self, size, *args, **kwargs):
        # Assert before delegating: if the bug returns, the test must not actually try
        # to allocate 6,000,000 x 300 pixels and take the runner down with it.
        assert size[0] * size[1] <= budget, f"resize requested {size[0]}x{size[1]}, budget {budget}"
        requested.append(size)
        return original(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", spy)
    out = transform_image(
        Image.new("L", (20000, 1), 128),
        width_in=1.0, height_in=1.0, fit_mode="cover", no_border=True,
    )
    assert out.size == (300, 300)
    assert requested


def test_f06_colour_key_transparency_composites_to_white():
    """RGB and L sources carrying a tRNS colour key were burned solid black."""
    for mode, colour, key in (("RGB", (0, 0, 0), (0, 0, 0)), ("L", 0, 0)):
        buf = io.BytesIO()
        Image.new(mode, (4, 4), colour).save(buf, format="PNG", transparency=key)
        buf.seek(0)
        processed = transform_image(Image.open(buf), no_border=True)
        assert np.all(np.array(processed) == True), mode


def test_f09_contain_padding_stays_white_under_invert():
    """Padding is layout background, not artwork; inverting the art must not blacken it."""
    source = Image.new("L", (100, 50), 0)  # black artwork
    out = transform_image(
        source, width_in=1.0, height_in=1.0, fit_mode="contain", invert=True, no_border=True
    )
    pixels = np.array(out)
    assert pixels[0, 150] == True     # top padding: white
    assert pixels[150, 150] == True   # inverted black artwork: white
    assert out.size == (300, 300)


def test_contain_padding_survives_tonal_processing():
    """Contrast, thresholds and dithering must not turn layout padding into engraving."""
    out = transform_image(
        Image.new("L", (100, 50), 255),
        width_in=1.0, height_in=1.0, fit_mode="contain",
        invert=True, contrast=0.5, sharpen_percent=0, no_border=True,
    )
    pixels = np.array(out)
    # 100x50 into 300x300 leaves 75 rows of padding top and bottom.
    assert not (~pixels[:75, :]).any(), int((~pixels[:75, :]).sum())
    assert not (~pixels[225:, :]).any(), int((~pixels[225:, :]).sum())
