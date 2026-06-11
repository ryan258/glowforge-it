# Glowforge Image Optimization

A Python batch-processing tool designed to prepare raster images for flawless, predictable engraving on a Glowforge laser cutter.

By converting continuous-tone grayscale images into true 1-bit Atkinson dithered bitmaps, you completely bypass the slow, unpredictable automated processing of the Glowforge cloud servers. You get pixel-perfect control over every burn.

## Why this instead of native Glowforge processing?

1. **Bypasses Cloud Processing:** The Glowforge app natively interprets gray pixels and applies its own slow, proprietary "black box" algorithm to determine laser pulses. Providing a strict 300 DPI 1-bit (pure black & pure white) file skips this auto-translation, giving you absolute, predictable control.
2. **Atkinson Dithering:** Unlike standard dithering that often muddies high-contrast lines, Atkinson Dithering perfectly preserves stark line-art while creating a beautiful, retro halftone/stipple effect for shaded areas.
3. **Kerf Bleed Compensation:** Calculates a heavy Unsharp Mask that creates microscopic "white halos" around dense black lines. This compensates for the 0.2mm physical beam width of the laser, preventing adjacent lines from bleeding into a puddle of scorched charcoal.
4. **Prevents Background Scorching:** Forces backgrounds to pure mathematical white, ensuring the laser never misfires in negative space due to faintly anti-aliased or off-white "ghost" pixels.

## Requirements & Setup

This tool is designed to work completely friction-free using the [uv](https://github.com/astral-sh/uv) Python package manager. It automatically provisions Python and grabs all dependencies (like `numpy` and `Pillow`) on the fly, so you don't even need to manage a virtual environment!

### 1 (Optional). Install Global Alias

For the easiest workflow, run the included setup script to install a `gf` terminal alias:

```bash
chmod +x gf install_alias.sh
./install_alias.sh
```

After reloading your terminal (`source ~/.zshrc`), you can simply type `gf` from this folder to process all images!

## Usage

Place any supported images (`.png`, `.jpg`, `.jpeg`, `.bmp`) you want to process in the `input/` directory.

Run the tool using the alias:

```bash
gf
```

_(If you chose not to install the alias, you can run `./gf` or `uv run main.py` directly)._

The carefully processed, 1-bit laser-ready files will be generated in the `output/` directory with `_dithered` appended to the filename (or `_invert` if the `--invert` flag was used). By default, output files are given a 1px solid black border to provide a clean, contiguous shape boundary for the Glowforge cut-out operation (disable with `--nb`).

## Configuration & Tuning

The script is highly configurable depending on the aesthetic you want and the artifacts you are trying to overcome (especially useful for AI-generated images).

You can run the script with a preset, or pass individual fine-tuning arguments:

```bash
gf --preset coaster -w 4
gf --clean-solids --black-threshold 20 --white-threshold 240 --dither-threshold 110
```

### Available Arguments:

| Argument | Description | Default |
| :--- | :--- | :--- |
| `-p, --preset` | Use a pre-configured engraving recipe (e.g. `photo-high-detail`, `ai-art`, `wood-hard`, `coaster`, etc.). There are 16 material and style presets built-in. | `None` |
| `-w, --width` | Target physical width in inches. Scales the image to match at 300 DPI. Appends `_w{W}h{H}` to the output filename. | `None` |
| `-h, --height` | Target physical height in inches. Scales the image to match at 300 DPI. Appends `_w{W}h{H}` to the output filename. | `None` |
| `-i, --invert` | Inverts the image values. Useful for engraving light-on-dark negatives. | `False` |
| `-c, --clean-solids` | Snaps near-blacks and near-whites to pure solids right after loading. Great for cleaning up AI gradients. | `False` _(Note: The `gf` script includes this by default)_ |
| `--clean-solids-black` | Snap threshold for near-black pixels when using `--clean-solids`. | `35` |
| `--clean-solids-white` | Snap threshold for near-white pixels when using `--clean-solids`. | `220` |
| `-b, --black-threshold` | Lock pixels darker than this value to pure solid black, bypassing dithering. | `0` |
| `-W, --white-threshold` | Lock pixels lighter than this value to pure solid white, bypassing dithering. | `255` |
| `-d, --dither-threshold` | Decision boundary (`0-255`) where midtones round to black or white. | `128` |
| `--nb, --no-border` | Disable the automatic 1px black border. | `False` |
| `--denoise` | Denoise the image using a median filter of the specified size (must be an odd integer `>= 3`). Great for smoothing out AI speckles. | `0` |
| `--contrast` | Contrast multiplier applied before dithering. | `1.5` |
| `--sharpen-radius` | Unsharp mask sharpening radius. | `2.0` |
| `--sharpen-percent` | Unsharp mask sharpening percentage. | `150` |
| `--sharpen-threshold` | Unsharp mask sharpening threshold. | `3` |
| `--circle-cut` | Apply a circular cutout mask (making everything outside transparent) and draw a 1px solid black cut line (e.g. for coaster shapes). | `False` |
| `--input` | Define custom folder path or list of specific images to read. | `input/` |
| `-o, --output` | Define custom folder path to save the processed files. | `output/` |

## Extended Documentation

For deeper details on engraving workflows, material presets, and how to get the best out of this tool:
- 📖 **[Glowforge Engraving Handbook](file:///Users/ryanjohnson/Projects/glowforge-it/docs/handbook.md)** — Comprehensive reference on dithering math, AI art cleanup, the 16 presets, and coaster cut setups.
- 🎨 **[Magic Laser Engraving Guide (ELI5)](file:///Users/ryanjohnson/Projects/glowforge-it/docs/eli5.md)** — A kid-friendly guide explaining dithering, engraving, and how to make custom coasters!

