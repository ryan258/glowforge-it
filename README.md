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

The carefully processed, 1-bit laser-ready files will be generated in the `output/` directory with `_dithered` appended to the filename. All output files are automatically given a 1px solid black border to provide a clean, contiguous shape boundary for the Glowforge cut-out operation.

## Configuration & Tuning

The script is highly configurable depending on the aesthetic you want and the artifacts you are trying to overcome (especially useful for AI-generated images).

You can pass these arguments via the terminal:

```bash
gf --clean-solids --black-threshold 20 --white-threshold 240 --dither-threshold 110
```

### Available Arguments:

| Argument             | Description                                                                                                                                                                                                         | Default                                                                |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :--------------------------------------------------------------------- |
| `--invert`           | Inverts the image immediately upon loading. Useful if you want the design to be engraved as a negative (light areas burn dark).                                                                                     | `False`                                                                |
| `--clean-solids`     | A flag that deeply scrubs AI-generated gradient artifacts. It aggressively snaps "almost black" to true black and "almost white" to true white right after loading the image.                                       | `False` _(Note: The `gf` wrapper script automatically includes this!)_ |
| `--black-threshold`  | `0-255` cutoff. Any pixels darker than this value are locked to pure solid black and completely bypassing the dithering algorithm. Use this to prevent white error-diffusion from "bleeding" into solid black text. | `0`                                                                    |
| `--white-threshold`  | `0-255` cutoff. Any pixels lighter than this value are locked to pure solid white, keeping skies and backgrounds completely clean.                                                                                  | `255`                                                                  |
| `--dither-threshold` | The midpoint target point (`0-255`) where the Atkinson algorithm decides if a mid-tone pixel should round to black or white. Moving this up makes the overall image darker; moving it down makes it lighter.        | `128`                                                                  |
| `--input`            | Define a custom folder path to read input images from.                                                                                                                                                              | `input`                                                                |
| `--output`           | Define a custom folder path to save the processed files to.                                                                                                                                                         | `output`                                                               |

## Tips for AI Images

If your source art was generated by AI, it will likely contain millions of hidden, multi-colored anti-aliased pixels that look solid black or white to the human eye, but create messy stippling when laser dithered.

Always use the `--clean-solids` flag (which the `gf` command does for you by default) or raise the `--black-threshold` slightly (e.g. `--black-threshold 15`) to force intended solids back to pure, un-dithered blocks.
