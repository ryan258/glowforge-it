# Glowforge Image Preparation Handbook

This guide explains what this repository does, how its raster pipeline behaves, and how to prepare files for review in the Glowforge app. It covers artwork preprocessing; it does not control the laser or replace material compatibility checks, machine settings, proof cuts, or supervision.

## 1. Project and material context

The default makerspace stock context is **medium maple plywood at 1/8 inch**. The CLI reports the label and thickness for each batch. Change them with `--material` and `--material-thickness` (for example, `--material-thickness 1/4`). These values describe the stock; they do not change pixels or choose power, speed, focus, or passes.

Check the stock label and measure the sheet. Glowforge’s own Proofgrade Maple Plywood listing uses Medium for approximately 1/8 inch and Thick for approximately 1/4 inch. “Medium” may mean something different for local stock. Plywood cores and adhesives vary; confirm the actual material with the supplier, its safety data, and the makerspace operator. Glowforge warns that settings for a similarly named material may not be safe or effective for non-Proofgrade stock ([Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished), [Print Settings FAQ](https://support.glowforge.com/hc/en-us/articles/4605501879963-print-settings-faq)).

The presets below change image processing only. They are not machine recipes. Use the material and operation profile approved for the specific Glowforge, and make a small proof test when required by the makerspace. Follow the current manual and never leave a print unattended ([Glowforge manuals](https://glowforge.com/manual), [Working With Manual Mode](https://support.glowforge.com/hc/en-us/articles/360033633574-Working-With-Manual-Mode)).

## 2. What the pipeline does

For each source image, the CLI applies these steps in order:

1. Applies EXIF orientation so a camera image is processed in its displayed orientation.
2. Composites transparency over white, then converts to grayscale.
3. Optionally median-filters noise (`--denoise`).
4. Optionally inverts grayscale values (`--invert`). This is a *tonal* flip only: it does not mirror, rotate, or otherwise move pixels. To reverse artwork for a mirror-back or rubber-stamp print, flip it horizontally in an image editor before running the CLI.
5. Resizes to the requested physical dimensions at 300 DPI. If only width or height is given, it preserves aspect ratio. If both are given, `--fit` chooses how to handle a different source aspect ratio (`stretch`, `contain`, or `cover`). For `--fit contain`, the artwork is scaled proportionally and placed onto white layout padding after dithering, ensuring padding never receives contrast or error diffusion.
6. Optionally snaps near-black/near-white values with `--clean-solids`, then applies hard black and white thresholds. `--clean-solids-black`/`--clean-solids-white` are the *snapping* boundaries; `-b`/`-W` are the hard thresholds. They are separate controls.
7. Applies contrast and unsharp masking.
8. Converts the grayscale image to a 1-bit Atkinson dither. Dithering always runs; there is no threshold-only or grayscale output mode. High thresholds or `--clean-solids` can leave large solid areas, but the dither stage still processes every pixel. For `--fit contain`, the dithered image is then placed onto the target white canvas; layout padding is always white, including with `--invert`.
9. Adds a 1-pixel black bitmap border by default, or applies a circle/heart transparency mask. Shape masks require RGBA PNG output.
10. Writes a PNG at 300 DPI. With `--svg-cut`, it also writes an SVG containing the raster image and a vector outline.

Atkinson dithering sends one eighth of each pixel’s quantization error to six nearby pixels. Its dot pattern is a visual starting point; the material, machine, print step, and app settings control the physical result.

### Choosing a fit mode

- `stretch` fills the target size and can distort proportions.
- `contain` preserves the whole image and pads the unused area with white. The padding is always white, including with `--invert`.
- `cover` preserves proportions and center-crops the excess.

These modes matter only when both `--width` and `--height` are specified. For a centered circle or heart, square dimensions are usually the clearest choice. For example, `-w 4 -h 4` requests a 4 × 4 inch canvas; it does not guarantee the finished piece is exactly 4 inches after app placement, kerf, or cut settings.

## 3. Image presets

Presets choose starting image-processing values. Explicit CLI options override their values. None of these settings changes laser power or validates that the named material is laser-safe.

| Preset | Values set in code | Intended artwork starting point |
| --- | --- | --- |
| `photo-high-detail` | denoise 3; contrast 1.8; sharpen radius 1.5; percent 200 | Detailed photos |
| `photo-soft` | contrast 1.2; radius 1; percent 100 | Softer photo tones |
| `vector-graphic` | clean solids; black 50; white 200; contrast 2 | High-contrast raster graphics |
| `ai-art` | denoise 3; clean solids; contrast 1.6; radius 2; percent 150 | AI artwork |
| `ai-art-detailed` | denoise 5; clean solids; contrast 1.8; radius 2.5; percent 200 | Detailed AI artwork |
| `line-art` | clean solids; contrast 2.5; black threshold 20 | Drawings and line art |
| `sketch` | contrast 1.3; radius 1; percent 250; threshold 1 | Pencil and charcoal scans |
| `wood-hard` | contrast 1.7; black threshold 10; radius 2 | Image contrast starting point for dark/hardwood work |
| `wood-soft` | contrast 1.4; white threshold 245; denoise 3 | Image contrast starting point for lighter/softer wood work |
| `acrylic` | clean solids; contrast 2; radius 1.5; percent 180 | Artwork on acrylic; material compatibility must be confirmed separately |
| `leather` | contrast 1.3; denoise 3; radius 1; percent 120 | Artwork on compatible leather |
| `glass` | contrast 1.9; radius 2; percent 170 | Glass artwork; verify your machine can engrave the material |
| `stamp` | clean solids; black 60; white 190; contrast 3 | High-contrast stamp artwork |
| `high-contrast` | clean solids; black 15; white 240; contrast 2.5 | Stencil-like or strongly separated tones |
| `low-res-enhance` | denoise 3; contrast 1.6; radius 1.5; percent 220 | Lower-resolution sources |
| `coaster` | circular mask | Circle-shaped transparent PNG |
| `coaster-heart` | heart mask | Heart-shaped transparent PNG |

The `gf` wrapper enables `--clean-solids` by default. When launching `uv run main.py` directly, clean-solids is disabled unless you pass `-c`.

## 4. Coaster masks and vector cut outlines

A bitmap outline is engraved artwork, not a cut path. Glowforge’s documentation describes SVG/PDF vectors as the route for cut and score paths, while PNG/JPG are for engraving ([Upload Your Own Design File](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [Simplify Strokes](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes)).

### PNG-only shape mask

```bash
gf --input input/design.png --preset coaster -w 4 -h 4
```

This creates a 4 × 4 inch transparent circle mask and, by default, an opaque 1-pixel bitmap edge. The bitmap edge will engrave. The heart preset works similarly:

```bash
gf --input input/design.png --preset coaster-heart -w 4 -h 4
```

### PNG plus SVG cut sidecar

```bash
gf --input input/design.png --preset coaster --svg-cut -w 4 -h 4
```

This writes a PNG plus a sibling file ending in `_cut.svg`. The PNG remains the raster engraving. In the SVG, the bitmap border is omitted and the circle/heart is drawn as a vector stroke. The SVG embeds the PNG so the art and outline share a common canvas and physical dimensions.

Before any print, upload the SVG into the Glowforge app and inspect the import. Confirm the raster art appears as an engraving step, the outline appears as the intended vector operation, the dimensions and position are correct, and the selected stock/material and settings are appropriate. Glowforge’s general documentation supports mixed raster/vector files, but this project has not yet been verified against a live Glowforge device. A vector cut can go through the material; use a proof/test and follow the maker space’s operation procedure.

`--svg-cut` requires a circle or heart mask. It does not automatically create nests, holes, tabs, kerf offsets, labels, or multi-piece layouts.

## 5. Batch and output behavior

- `--input` accepts one or more images and folders. Supported extensions are PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. Animated GIF input uses its first frame.
- Folder traversal is sorted and preserves subfolders in the output. An output directory inside an input folder is rejected to avoid processing generated results again.
- The default source/output limit is 20,000,000 pixels per image. `--max-pixels` changes it. A large raster can require substantial memory even below the limit.
- Optional `--machine` checks nominal dimensions, allowing rotation. It is a preflight hint only. Performance is listed at 19.5 × 11 inches, Aura at 12 × 12 inches, and Spark at 8.5 × 11 inches; real printable area may be reduced by print operation and settings. The app is authoritative ([printable area](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area), [Craft Series specifications](https://glowforge.com/b/tech-specs/craft)).
- Filenames include the input basename/extension, preset, changed image settings, and requested dimensions. When no explicit `--preset` is passed on the CLI, files matching `*--[mode].<ext>` (e.g. `fox--line-art.png` or `owl--photo-soft.png`) automatically infer and apply that preset mode for that job. They do not contain a content hash or material label, so different source content with the same basename/settings can map to the same path across runs. The default is `--existing overwrite`; use `skip` or `error` when preserving existing files matters. For PNG/SVG output, the policy applies to both files and reports incomplete sidecar pairs.
- Each individual file is written through a temporary sibling and renamed into place, avoiding a half-written PNG or SVG on ordinary write errors. The PNG and SVG pair is not a single cross-file transaction; if a run reports an error, inspect both outputs before reuse.

## 6. CLI reference

`-h` means height, so request help with `--help`.

| Option | Meaning |
| --- | --- |
| `--input PATH [PATH ...]` | Source images or folders; default `input/`. |
| `-o, --output DIR` | Destination folder; default `output/`. |
| `-p, --preset NAME` | Select an image preset from section 3. |
| `--recipe PATH` | Path to custom user recipe profile (`.toml` or `.json`). |
| `--material LABEL` | Descriptive run label; defaults to `medium maple plywood`; no image or machine effect. |
| `--material-thickness IN` | Descriptive thickness in inches; default `1/8` (`0.125`); decimals and fractions are accepted. No image or machine effect. |
| `-w, --width IN`; `-h, --height IN` | Target physical dimension at 300 DPI. |
| `--fit MODE` | `stretch`, `contain`, or `cover` when both dimensions are set. |
| `-b, --black-threshold N`; `-W, --white-threshold N` | Force dark/light values to solid black/white. |
| `-d, --dither-threshold N` | Atkinson decision threshold, 0–255. |
| `-c, --clean-solids`; `--no-clean-solids` | Enable/disable near-solid snapping. |
| `--clean-solids-black N`; `--clean-solids-white N` | Near-black and near-white boundaries. |
| `-i, --invert`; `--no-invert` | Invert grayscale values (tonal only; it does not mirror the image). |
| `--nb, --no-border` | Disable the black bitmap edge. |
| `--denoise N` | Median-filter size: `0` (off) or an odd number of at least 3. |
| `--contrast N`; `--sharpen-radius N`; `--sharpen-percent N`; `--sharpen-threshold N` | Contrast and unsharp-mask options. A `0` radius or percent turns sharpening off, which is how you ablate a preset stage. |
| `--circle-cut`; `--heart-cut` | Apply a raster transparency mask. These are mutually exclusive. |
| `--svg-cut` | Add a vector-outline SVG sidecar; requires a shape mask. |
| `--manifest` | Emit companion versioned JSON job manifest (`_manifest.json`) adjacent to output. |
| `--dry-run` | Preview planned destinations, dimensions, and memory without writing files or creating folders. |
| `--json` | Emit structured machine-readable JSON batch result summary. |
| `--max-memory SIZE` | Preflight memory budget (e.g. `500MB`, `1GB`) to reject over-budget jobs before pixel allocation. |
| `--prompt TEXT` / `--model TEXT` | Optional AI provenance metadata to record in the job manifest. |
| `--machine performance\|aura\|spark` | Optional nominal bed-area preflight. |
| `--max-pixels N` | Maximum source/output pixels per image; default 20,000,000. |
| `--existing overwrite\|skip\|error` | Existing-output policy; default `overwrite`. |
| `--version` | Display program version number (`0.2.0rc1`) and exit. |

## 7. Current boundaries and next product steps

This repository currently focuses on single-image preprocessing and folder batches. It includes TOML/JSON recipe files, metadata manifests, dry-run plans, and manifest-backed output verification. It does not yet provide preview UI, material test-card generation, multi-design sheet nesting, crop tools, additional dithering styles, or machine-calibrated settings. The prioritized delivery plan and next steps are tracked in [roadmap.md](../roadmap.md), with speculative concepts cataloged in [UPDATE-IDEAS.md](UPDATE-IDEAS.md).
