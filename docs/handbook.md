# Glowforge Engraving Optimization Handbook

This handbook provides instructions on getting the most out of the Glowforge Image Optimizer. It covers fundamental laser processing concepts, strategies for cleaning up AI-generated art, material-specific presets, and the circular coaster cut workflow.

---

## 1. Fundamentals of Laser Optimization

Engraving continuous-tone raster images (like photos) directly on a Glowforge often leads to unpredictable results. This tool transforms images into 300-DPI, 1-bit Atkinson-dithered bitmaps to achieve high-fidelity prints:

* **True 1-Bit Bitmaps:**skip the slow and variable automatic cloud conversion. Because every pixel in the image is either pure black (`0`) or pure white (`255`), the Glowforge fires the laser on a binary basis (on for black, off for white), matching your screen preview exactly.
* **Atkinson Error Diffusion:** Atkinson dithering limits error diffusion to a tight local region, preserving sharp contrast lines while generating clean, hand-stippled gradients.
* **Kerf Bleed Compensation:** High contrast adjustments and heavy unsharp masking create microscopic white halos around fine details. This compensates for the physical width of the laser beam (the kerf, ~0.2mm), preventing small text and dense lines from bleeding together.

---

## 2. Advanced AI Image Optimization

AI-generated images (e.g. Midjourney, DALL-E) frequently contain high-frequency noise, compression artifacts, and soft gradients. If not cleaned up, these artifacts will dither into messy speckles. Use these features to mitigate artifacts:

### Noise Reduction (`--denoise`)
Apply a median filter using `--denoise <odd_int>` (e.g., `--denoise 3`). This removes high-frequency "salt-and-pepper" noise and JPEG artifacts while preserving structural edges.

### Custom Clean Solids (`--clean-solids`)
AI images often have backgrounds that look white but are actually off-white (e.g., value 245). This causes the laser to fire randomly.
* Use `--clean-solids` to snap near-solids to pure values.
* Customize the boundaries using `--clean-solids-black <val>` (default: 35) and `--clean-solids-white <val>` (default: 220). Any pixel darker than the black limit snaps to pure black, and any pixel lighter than the white limit snaps to pure white.

### Enhancing Contrast & Sharpening
Expose detail on softer AI images by increasing contrast with `--contrast <float>` (default: 1.5) and tweaking the sharpening parameters (`--sharpen-radius`, `--sharpen-percent`, `--sharpen-threshold`).

---

## 3. Engraving Presets Reference

The tool includes 16 built-in presets using the `--preset <name>` flag. You can override individual preset values by passing the corresponding CLI arguments.

| Preset Name | Target Material / Style | Key Characteristics |
| :--- | :--- | :--- |
| `photo-high-detail` | High-fidelity photographs | Denoise=3, high contrast, heavy sharpening for fine detail. |
| `photo-soft` | Artistic, soft portraiture | Lower contrast and minimal sharpening for soft transitions. |
| `vector-graphic` | Rasterized SVG, logos, text | Snaps solids aggressively, high contrast. |
| `ai-art` | AI generated illustrations | Median denoise, clean solids, strong edge sharpening. |
| `ai-art-detailed` | Complex, high-fidelity AI art | Extra denoise=5, extra contrast, max sharpening. |
| `line-art` | Sketches, ink drawings, lineart | Heavy contrast boost, low black threshold to clear smudges. |
| `sketch` | Pencil drawings | Moderate contrast, high percent sharpening to catch soft lines. |
| `wood-hard` | Walnut, cherry, oak | High contrast, lower black threshold for deep engraving. |
| `wood-soft` | Basswood, balsa, draftboard | Moderate contrast, prevents deep charring. |
| `acrylic` | Cast acrylic sheets | High contrast, snaps solids, sharp edges. |
| `leather` | Engraved leather sheets | Low contrast, soft sharpening, denoise=3 to prevent burning. |
| `glass` | Etched glass panels | High contrast, high sharpening. |
| `stamp` | Reverse-engraved rubber stamps | Max contrast, aggressive solids snapping for deep relief. |
| `high-contrast` | Hard graphical stippling | Locks boundaries, high contrast, clean solids. |
| `low-res-enhance` | Low-resolution, pixelated files | Strong denoise and high sharpening percentage. |
| `coaster` | Circular wooden coasters | Enables the circular cutout mask and cutout border. |

---

## 4. Wooden Coaster Workflow

The `coaster` preset (or individual `--circle-cut` flag) is designed to streamline coaster production:

### How it Works
1. **Circular Masking:** Everything outside the center circle of the image is masked out to true transparent (`alpha = 0`) in an `RGBA` PNG. The Glowforge app ignores transparent pixels, preventing background burns.
2. **Circular Cut Path:** It draws a 1px opaque black circular border exactly on the outer circle boundary.
3. **Double Operation:** In the Glowforge UI:
   * Set the **engraved pattern** inside the circle to **Engrave**.
   * Set the **1px black circular border** to **Cut** (the laser will trace the circle and cut out the wooden coaster).

> [!TIP]
> **Sizing your Coaster:**
> For a standard 4-inch coaster, run:
> `gf --input input/design.png --preset coaster -w 4`
> The script will size the circle to exactly 4 inches (1200 pixels at 300 DPI) and append `_w4h4` to the output file.

---

## Appendix: CLI Argument Reference

| Flag / Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--help` | N/A | N/A | Display the help message and exit. |
| `--input` | Paths | `input` | Space-separated list of folders or files to process. |
| `-o`, `--output` | Path | `output` | Folder where processed images will be saved. |
| `--preset` | Enum | `None` | Use a pre-configured preset (see presets table). |
| `-w`, `--width` | Float (`> 0`) | `None` | Target physical width in inches (scales proportionally at 300 DPI). |
| `-h`, `--height` | Float (`> 0`) | `None` | Target physical height in inches (scales proportionally at 300 DPI). |
| `-b`, `--black-threshold` | Int (`0-255`) | `0` | Lock pixels darker than this value to pure black. |
| `-W`, `--white-threshold` | Int (`0-255`) | `255` | Lock pixels lighter than this value to pure white. |
| `-d`, `--dither-threshold` | Int (`0-255`) | `128` | Decision boundary where midtones round to black or white. |
| `-c`, `--clean-solids` | Boolean | `False` | Snaps near-blacks and near-whites to pure solids. |
| `--clean-solids-black` | Int (`0-255`) | `35` | Lower limit for snapping solid black. |
| `--clean-solids-white` | Int (`0-255`) | `220` | Upper limit for snapping solid white. |
| `-i`, `--invert` | Boolean | `False` | Inverts the image colors. |
| `--nb`, `--no-border` | Boolean | `False` | Disables the automatic 1px cutout border. |
| `--denoise` | Odd Int (`>= 3`)| `0` | Median filter size for removing noise. |
| `--contrast` | Float (`> 0`) | `1.5` | Contrast scaling multiplier. |
| `--sharpen-radius` | Float (`> 0`) | `2.0` | Radius for Unsharp Mask filter. |
| `--sharpen-percent` | Int (`> 0`) | `150` | Sharpening intensity percentage. |
| `--sharpen-threshold` | Int (`>= 0`)| `3` | Minimum difference in brightness before sharpening is applied. |
| `--circle-cut` | Boolean | `False` | Apply a circular cutout mask and drawing border. |
