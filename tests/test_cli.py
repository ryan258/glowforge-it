"""Argument types, parser validation, settings resolution, and the launcher."""

import argparse
import os
import re

import pytest
from PIL import Image

from glowforge_it.cli import (
    build_parser,
    main,
    non_negative_int_type,
    odd_int_type,
    positive_float_type,
    positive_inches_type,
    positive_int_type,
    threshold_type,
)
from glowforge_it.imaging import transform_image
from glowforge_it.settings import PRESETS, ProcessingSettings, resolve_settings


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
    assert odd_int_type("0") == 0  # explicit "off", not an error
    with pytest.raises(argparse.ArgumentTypeError):
        odd_int_type("-1")
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


def test_positive_inches_type():
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


def test_presets_exist():
    assert "photo-high-detail" in PRESETS
    assert len(PRESETS) >= 15


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


def test_cli_parser_error_cases():
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
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    Image.new("RGB", (20, 20), "white").save(in_dir / "sample.png")

    exit_code = main(["--input", str(in_dir), "-o", str(out_dir), "--preset", "line-art"])
    assert exit_code == 0
    [produced] = out_dir.glob("*.png")
    assert re.fullmatch(r"sample_png_r[0-9a-f]{12}\.png", produced.name)


def test_f08_preset_stages_can_be_switched_off():
    """--preset ai-art --denoise 0 --sharpen-radius 0 is a valid ablation."""
    args = build_parser().parse_args(
        ["--preset", "ai-art", "--denoise", "0", "--sharpen-radius", "0", "--sharpen-percent", "0"]
    )
    settings = resolve_settings(args)
    assert settings.denoise_radius == 0
    assert settings.sharpen_radius == 0
    assert settings.sharpen_percent == 0

    # A disabled unsharp mask must leave the image alone rather than raise.
    flat = Image.new("L", (8, 8), 200)
    assert transform_image(flat, settings=ProcessingSettings(sharpen_radius=0, sharpen_percent=0, no_border=True)).size == (8, 8)


def test_silhouette_render_mode_resolves_explicit_threshold():
    args = build_parser().parse_args(
        ["--render-mode", "silhouette", "--silhouette-threshold", "90"]
    )
    settings = resolve_settings(args)
    settings.validate()
    assert settings.render_mode == "silhouette"
    assert settings.silhouette_threshold == 90


def test_screen_render_modes_resolve_explicit_parameters():
    ordered = build_parser().parse_args(
        ["--render-mode", "ordered", "--ordered-matrix-size", "8"]
    )
    ordered_settings = resolve_settings(ordered)
    ordered_settings.validate()
    assert ordered_settings.render_mode == "ordered"
    assert ordered_settings.ordered_matrix_size == 8

    halftone = build_parser().parse_args(
        ["--render-mode", "halftone", "--halftone-cell-px", "6", "--halftone-angle", "45"]
    )
    halftone_settings = resolve_settings(halftone)
    halftone_settings.validate()
    assert halftone_settings.halftone_cell_px == 6
    assert halftone_settings.halftone_angle == 45

    hatch = build_parser().parse_args(
        ["--render-mode", "hatch", "--hatch-spacing-px", "5", "--hatch-angle", "30", "--hatch-cross"]
    )
    hatch_settings = resolve_settings(hatch)
    hatch_settings.validate()
    assert hatch_settings.render_mode == "hatch"
    assert hatch_settings.hatch_spacing_px == 5
    assert hatch_settings.hatch_angle == 30
    assert hatch_settings.hatch_cross is True

    edge = build_parser().parse_args(
        ["--render-mode", "edge", "--edge-threshold", "40"]
    )
    edge_settings = resolve_settings(edge)
    edge_settings.validate()
    assert edge_settings.render_mode == "edge"
    assert edge_settings.edge_threshold == 40

    contour = build_parser().parse_args(
        ["--render-mode", "contour", "--contour-levels", "12"]
    )
    contour_settings = resolve_settings(contour)
    contour_settings.validate()
    assert contour_settings.render_mode == "contour"
    assert contour_settings.contour_levels == 12

    layers = build_parser().parse_args(["--tone-layers", "3"])
    layer_settings = resolve_settings(layers)
    layer_settings.validate()
    assert layer_settings.tone_layers == 3

    stamp = build_parser().parse_args(
        ["--stamp-text", "ORDER-42", "--stamp-position", "top-right", "--stamp-size-px", "18", "--stamp-margin-px", "20"]
    )
    stamp_settings = resolve_settings(stamp)
    stamp_settings.validate()
    assert stamp_settings.stamp_text == "ORDER-42"
    assert stamp_settings.stamp_position == "top-right"
    assert stamp_settings.stamp_size_px == 18
    assert stamp_settings.stamp_margin_px == 20

    qr = build_parser().parse_args(
        ["--qr-text", "HELLO-42", "--qr-position", "top-left", "--qr-module-px", "5", "--qr-margin-px", "16"]
    )
    qr_settings = resolve_settings(qr)
    qr_settings.validate()
    assert qr_settings.qr_text == "HELLO-42"
    assert qr_settings.qr_position == "top-left"
    assert qr_settings.qr_module_px == 5
    assert qr_settings.qr_margin_px == 16
