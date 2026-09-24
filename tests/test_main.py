import os
import io
import re
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
    process_directory,
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
    
    # The fixture is committed; a missing one means the checkout is broken,
    # not that we should silently regenerate and pass.
    if not os.path.exists(golden_path):
        processed.save(golden_path)
        pytest.fail(f"Golden image was missing. Regenerated at {golden_path} - "
                    "inspect it, then commit it.")

    # Load and compare pixel-for-pixel using NumPy arrays
    golden = Image.open(golden_path)
    assert processed.size == golden.size
    assert processed.mode == golden.mode
    assert np.array_equal(np.array(processed), np.array(golden))

def test_presets_exist():
    from main import PRESETS
    assert "photo-high-detail" in PRESETS
    assert "coaster" in PRESETS
    assert "coaster-heart" in PRESETS
    # Ensure at least 16 presets (plus coaster-heart = 17)
    assert len(PRESETS) >= 17

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



# --- process_directory: filename + output-path construction ---

def _run_batch(tmp_path, images, **overrides):
    """Run process_directory over {relpath: PIL image} and return sorted output relpaths."""
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    for rel, img in images.items():
        dest = in_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest)

    kwargs = dict(
        black_thresh=0, white_thresh=255, dither_thresh=128,
        clean_solids=False, clean_solids_black=35, clean_solids_white=220,
        invert=False, width_in=None, height_in=None, no_border=False,
        denoise_radius=0, contrast=1.5, sharpen_radius=2.0,
        sharpen_percent=150, sharpen_threshold=3,
        circle_cut=False, heart_cut=False, preset_name=None,
    )
    kwargs.update(overrides)
    assert process_directory(str(in_dir), str(out_dir), **kwargs)
    return sorted(
        str(p.relative_to(out_dir)) for p in out_dir.rglob("*.png")
    )

def test_batch_default_naming(tmp_path):
    outputs = _run_batch(tmp_path, {"pic.png": Image.new("RGB", (8, 8), "gray")})
    assert outputs == ["pic_png_dithered.png"]

def test_batch_mirrors_subdirectories(tmp_path):
    outputs = _run_batch(tmp_path, {
        "top.png": Image.new("RGB", (8, 8), "gray"),
        "nested/deep/inner.png": Image.new("RGB", (8, 8), "gray"),
    })
    assert outputs == [
        os.path.join("nested", "deep", "inner_png_dithered.png"),
        "top_png_dithered.png",
    ]

def test_batch_tags_non_default_settings(tmp_path):
    outputs = _run_batch(
        tmp_path,
        {"pic.png": Image.new("RGB", (8, 8), "gray")},
        invert=True, no_border=True, black_thresh=20,
    )
    assert outputs == ["pic_png_b20_inv_nb.png"]

def test_batch_tags_preset_and_overrides(tmp_path):
    outputs = _run_batch(
        tmp_path,
        {"pic.png": Image.new("RGB", (8, 8), "gray")},
        preset_name="ai-art", denoise_radius=3, clean_solids=True,
        contrast=1.6, sharpen_radius=2.0, sharpen_percent=150,
        black_thresh=20,
    )
    # Preset values are baseline; only black_thresh deviates from ai-art.
    assert outputs == ["pic_png_prai-art_b20.png"]

def test_batch_dimension_suffix_respects_exif(tmp_path):
    # 200x400 stored, EXIF orientation 6 -> displays as 400x200 (landscape).
    img = Image.new("RGB", (200, 400), "gray")
    exif = img.getexif()
    exif[274] = 6
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    img.save(in_dir / "rot.jpg", exif=exif)

    outputs = _run_batch(tmp_path, {}, width_in=2.0)
    # 2in wide at 300 DPI on a 2:1 landscape source -> 1in tall, not 4in.
    assert outputs == ["rot_jpg_dithered_w2h1.png"]
    with Image.open(tmp_path / "out" / outputs[0]) as out:
        assert out.size == (600, 300)

def test_dependency_pins_match_script():
    """requirements.txt and main.py's PEP 723 header must not drift apart."""
    root = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(root, "main.py")) as f:
        header = f.read().split("# ///")[1]
    with open(os.path.join(root, "requirements.txt")) as f:
        pinned = {line.strip() for line in f if line.strip()}

    script_deps = set(re.findall(r'"([^"]+==[^"]+)"', header))
    assert script_deps, "PEP 723 header has no pinned dependencies"
    # requirements.txt may add test-only extras (pytest), but every runtime
    # dependency must be pinned identically in both places.
    assert script_deps <= pinned, f"main.py pins {script_deps - pinned}, requirements.txt does not"

    floor = re.search(r'requires-python = ">=(\d+)\.(\d+)"', header)
    assert floor, "PEP 723 header has no requires-python"
    assert (int(floor.group(1)), int(floor.group(2))) >= (3, 11), \
        "numpy 2.4.x needs Python >= 3.11; the CI matrix must not go lower"


def test_positive_inches_type():
    from main import positive_inches_type
    assert positive_inches_type("1/8") == 0.125
    assert positive_inches_type("1/4") == 0.25
    assert positive_inches_type("0.5") == 0.5
    with pytest.raises(argparse.ArgumentTypeError):
        positive_inches_type("-0.1")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_inches_type("0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_inches_type("1/0")
    with pytest.raises(argparse.ArgumentTypeError):
        positive_inches_type("invalid")


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


def test_svg_document_rendering():
    from main import render_svg_document
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


def test_machine_bed_preflight(tmp_path):
    from main import output_geometry
    img_path = tmp_path / "test.png"
    Image.new("RGB", (300, 300), "white").save(img_path)

    # Spark bed is 8.5 x 11. 12 x 12 exceeds nominal bed.
    with pytest.raises(ValueError, match="exceeds the nominal spark area"):
        output_geometry(str(img_path), width_in=12.0, height_in=12.0, max_pixels=20_000_000, machine="spark")

    # Within bounds passes without error
    suffix = output_geometry(str(img_path), width_in=5.0, height_in=5.0, max_pixels=20_000_000, machine="spark")
    assert suffix == "_w5h5"


def test_existing_output_policies(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    img = Image.new("RGB", (30, 30), "gray")
    img.save(in_dir / "pic.png")

    kwargs = dict(
        black_thresh=0, white_thresh=255, dither_thresh=128,
        clean_solids=False, clean_solids_black=35, clean_solids_white=220,
        invert=False, width_in=None, height_in=None, no_border=False,
        denoise_radius=0, contrast=1.5, sharpen_radius=2.0,
        sharpen_percent=150, sharpen_threshold=3,
        circle_cut=False, heart_cut=False, preset_name=None,
    )
    # First pass writes output
    assert process_directory(str(in_dir), str(out_dir), existing="overwrite", **kwargs)

    # Second pass with 'skip' policy succeeds
    assert process_directory(str(in_dir), str(out_dir), existing="skip", **kwargs)

    # Second pass with 'error' policy fails
    assert not process_directory(str(in_dir), str(out_dir), existing="error", **kwargs)


def test_cli_parser_error_cases():
    from main import main
    # Material empty
    with pytest.raises(SystemExit) as exc:
        main(["--material", "   "])
    assert exc.value.code != 0

    # Mutually exclusive circle and heart
    with pytest.raises(SystemExit) as exc:
        main(["--circle-cut", "--heart-cut"])
    assert exc.value.code != 0

    # Black threshold > white threshold
    with pytest.raises(SystemExit) as exc:
        main(["-b", "200", "-W", "100"])
    assert exc.value.code != 0

    # Clean solids black > white
    with pytest.raises(SystemExit) as exc:
        main(["--clean-solids-black", "200", "--clean-solids-white", "100"])
    assert exc.value.code != 0

    # svg-cut without cutout shape
    with pytest.raises(SystemExit) as exc:
        main(["--svg-cut"])
    assert exc.value.code != 0


def test_cli_main_success(tmp_path):
    from main import main
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    Image.new("RGB", (20, 20), "white").save(in_dir / "sample.png")

    exit_code = main(["--input", str(in_dir), "-o", str(out_dir), "--preset", "line-art"])
    assert exit_code == 0
    assert (out_dir / "sample_png_prline-art.png").exists()
