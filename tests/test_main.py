import os
import io
import argparse
import pytest
from PIL import Image, ImageDraw, ImageOps
import numpy as np

from main import (
    threshold_type,
    positive_float_type,
    odd_int_type,
    positive_int_type,
    non_negative_int_type,
    transform_image,
)

def test_threshold_type_valid():
    assert threshold_type("0") == 0
    assert threshold_type("128") == 128
    assert threshold_type("255") == 255

def test_threshold_type_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        threshold_type("-1")
    with pytest.raises(argparse.ArgumentTypeError):
        threshold_type("256")
    with pytest.raises(argparse.ArgumentTypeError):
        threshold_type("abc")

def test_positive_float_type_valid():
    assert positive_float_type("1.5") == 1.5
    assert positive_float_type("0.1") == 0.1

def test_positive_float_type_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_float_type("0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_float_type("-1.2")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_float_type("abc")

def test_odd_int_type_valid():
    assert odd_int_type("3") == 3
    assert odd_int_type("5") == 5

def test_odd_int_type_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        odd_int_type("0")
    with pytest.raises(argparse.ArgumentTypeError):
        odd_int_type("4")
    with pytest.raises(argparse.ArgumentTypeError):
        odd_int_type("abc")

def test_positive_int_type_valid():
    assert positive_int_type("1") == 1
    assert positive_int_type("150") == 150

def test_positive_int_type_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int_type("0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int_type("-5")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int_type("abc")

def test_non_negative_int_type_valid():
    assert non_negative_int_type("0") == 0
    assert non_negative_int_type("3") == 3

def test_non_negative_int_type_invalid():
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int_type("-1")
    with pytest.raises(argparse.ArgumentTypeError):
        non_negative_int_type("abc")

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
    os.makedirs(golden_dir, exist_ok=True)
    golden_path = os.path.join(golden_dir, "golden_dithered.png")
    
    # Process the image
    processed = transform_image(img, black_thresh=10, white_thresh=245, dither_thresh=128)
    
    if not os.path.exists(golden_path):
        # Save it as reference if it doesn't exist
        processed.save(golden_path)
        pytest.skip("Golden image created. Run test again to verify.")
    else:
        # Load and compare pixel-for-pixel using NumPy arrays
        golden = Image.open(golden_path)
        assert processed.size == golden.size
        assert processed.mode == golden.mode
        
        processed_data = np.array(processed)
        golden_data = np.array(golden)
        assert np.array_equal(processed_data, golden_data)
