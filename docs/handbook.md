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
4. Optionally inverts grayscale values (`--invert`, legacy mode only). This is a *tonal* flip only: it does not mirror, rotate, or otherwise move pixels.
5. Resizes to the requested physical dimensions at 300 DPI. If only width or height is given, it preserves aspect ratio. If both are given, `--fit` chooses how to handle a different source aspect ratio (`stretch`, `contain`, or `cover`). For `--fit contain`, the artwork is scaled proportionally and placed onto white layout padding after dithering, ensuring padding never receives contrast or error diffusion.
6. Optionally snaps near-black/near-white values with `--clean-solids`, then applies hard black and white thresholds. `--clean-solids-black`/`--clean-solids-white` are the *snapping* boundaries; `-b`/`-W` are the hard thresholds.
7. Applies contrast and unsharp masking.
7.5. For explicit material modes (`--material-mode darkening` or `lightening`), applies versioned levels and gamma curves (`--tone-black`, `--tone-white`, `--tone-gamma`) via a lookup table. Transparent pixels remain no-burn.
8. Converts the grayscale image to a 1-bit Atkinson dither. When an explicit material mode is active, source endpoints (0 and 255) are strictly preserved even under extreme dither thresholds. For `--fit contain`, the dithered image is placed onto the target white canvas; layout padding is always white.
8.5. For shape masks, applies a circle/heart transparency mask. For `--trim`, calculates burn-mask bounds and crops empty outer rows/columns from the raster, recording the crop offset in companion metadata and SVG.
9. Adds a 1-pixel black bitmap border by default (suppressed when `--no-border`, `--svg-cut`, `--svg-operations`, or `--jig` is active).
10. Writes output files: 300-DPI PNG engraving, optional unified SVG (`_operations.svg` with red cuts, blue scores, and embedded PNG), optional finish preview (`_finish.png`), optional client approval PDF (`_proof.pdf`), and versioned metadata (`_manifest.json` and `_workflow.json`).

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

### Legacy PNG plus SVG cut sidecar

```bash
gf --input input/design.png --preset coaster --svg-cut -w 4 -h 4
```

This writes a PNG plus a sibling file ending in `_cut.svg`. The PNG remains the raster engraving. In the SVG, the bitmap border is omitted and the circle/heart is drawn as a blue vector stroke.

### Unified multi-operation SVG and maker workflow

For complete jobs with distinct print operations, opt in to `--svg-operations`:

```bash
gf --input input/design.png --preset coaster -w 4 -h 4 \
  --svg-operations --score-marks --material-mode darkening
```

This emits `_operations.svg` using the unified maker palette: embedded monochrome PNG for engraving, red (`#ff0000`) for vector cuts, and blue (`#0000ff`) for vector scores (including top-left L score marks for alignment).

Key maker workflow capabilities:
- **Ablation Polarity & Tone Curves:** `--material-mode darkening` (burn darkens substrate) or `lightening` (burn lightens substrate, e.g. slate, dark acrylic). Controlled by `--tone-black`, `--tone-white`, and `--tone-gamma`.
- **Deterministic Maple Finish Preview:** `--preview-finish` writes `_finish.png` showing simulated burn on wood grain. Configure spread with `--preview-spread-mm` and seed with `--preview-seed`.
- **One-Page Client Approval Proof:** `--proof-sheet` writes `_proof.pdf` with side-by-side source and simulated finish, material details, SHA-256 revision hash, and printable sign-off lines. Pass `--client` and `--order` for metadata tracking.
- **Registered Pocket Jigs:** `--jig circle` or `--jig rectangle` with measured `--blank-width`, `--blank-height`, `--pocket-clearance`, `--jig-margin`, and `--kerf`. Add `--jig-rows` and `--jig-columns` for multi-pocket grids.
- **Empty-Bounds Trimming & Orientation Advice:** `--trim` crops empty outer burn mask bounds while preserving placement in companion SVG. `--optimize-orientation --engraving-lpi 225` evaluates 0° vs 90° scan rows against bed dimensions without altering artwork.

See the dedicated [Maker Workflow Guide](maker-workflow.md) for detailed contracts, geometric formulas, and step-by-step procedures.

## 5. Batch and output behavior

- `--input` accepts one or more images and folders. Supported extensions are PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. Animated GIF input uses its first frame.
- Folder traversal is sorted and preserves subfolders in the output. An output directory inside an input folder is rejected to avoid processing generated results again.
- The default source/output limit is 20,000,000 pixels per image. `--max-pixels` changes it.
- Optional `--machine` checks nominal dimensions (`performance`, `aura`, `spark`). It is a preflight hint only; usable area may be smaller in the app.
- Filenames include the input basename/extension, preset, changed image settings, requested dimensions, and workflow configuration hash (`_mw<hash>`). When no explicit `--preset` is passed on the CLI, files matching `*--[mode].<ext>` automatically infer that preset. Existing outputs are overwritten by default; choose `--existing skip` or `--existing error` to preserve prior work.
- When `--manifest` or any maker workflow flag is used, companion manifests (`_manifest.json`) and workflow records (`_workflow.json`) are written. With `--existing skip`, verified reuse checks that source and output hashes match and all companion files exist.
- Staged publication writes to temporary sibling files (`.gf-*`) and atomically replaces them, rolling back changes if any artifact fails during batch execution.

## 6. CLI reference

`-h` means height, so request help with `--help`.

| Option | Meaning |
| --- | --- |
| `--input PATH [PATH ...]` | Source images or folders; default `input/`. |
| `-o, --output DIR` | Destination folder; default `output/`. |
| `-p, --preset NAME` | Select an image preset from section 3. |
| `--recipe PATH` | Path to custom user recipe profile (`.toml` or `.json`). |
| `--material LABEL` | Descriptive run label; defaults to `medium maple plywood`; no machine effect. |
| `--material-thickness IN` | Descriptive thickness in inches; default `1/8` (`0.125`). |
| `-w, --width IN`; `-h, --height IN` | Target physical dimension at 300 DPI. |
| `--fit MODE` | `stretch`, `contain`, or `cover` when both dimensions are set. |
| `-b, --black-threshold N`; `-W, --white-threshold N` | Force dark/light values to solid black/white (0–255). |
| `-d, --dither-threshold N` | Atkinson decision threshold, 0–255. |
| `-c, --clean-solids`; `--no-clean-solids` | Enable/disable near-solid snapping. |
| `--clean-solids-black N`; `--clean-solids-white N` | Near-black and near-white boundaries. |
| `-i, --invert`; `--no-invert` | Invert grayscale values (tonal only; legacy mode only). |
| `--nb, --no-border` | Disable the black bitmap edge. |
| `--denoise N` | Median-filter size: `0` (off) or an odd number of at least 3. |
| `--contrast N`; `--sharpen-radius N`; `--sharpen-percent N`; `--sharpen-threshold N` | Contrast and unsharp-mask options. |
| `--circle-cut`; `--heart-cut` | Apply a raster transparency mask. These are mutually exclusive. |
| `--svg-cut` | Add legacy vector-outline SVG sidecar (blue stroke); requires a shape mask. |
| `--manifest` | Emit companion versioned JSON job manifest (`_manifest.json`). |
| `--dry-run` | Preview planned destinations, dimensions, and memory without writing files or creating folders. |
| `--json` | Emit structured machine-readable JSON batch result summary. |
| `--max-memory SIZE` | Preflight memory budget (e.g. `500MB`, `1GB`) to reject over-budget jobs before allocation. |
| `--prompt TEXT` / `--model TEXT` | Optional AI provenance metadata to record in the job manifest. |
| `--machine performance\|aura\|spark` | Optional nominal bed-area preflight. |
| `--max-pixels N` | Maximum source/output pixels per image; default 20,000,000. |
| `--existing overwrite\|skip\|error` | Existing-output policy; default `overwrite`. |
| `--svg-operations` | Opt in to unified SVG: embedded monochrome raster, red cuts, blue scores. |
| `--score-marks` | Add an intentional blue L-shaped orientation score at top left. |
| `--material-mode legacy\|darkening\|lightening` | Substrate ablation polarity: `darkening` (light wood/substrate) or `lightening` (slate/dark acrylic). |
| `--tone-black N`; `--tone-white N` | Tonal curve clipping boundaries (0–255). |
| `--tone-gamma N` | Tonal gamma exponent (> 0). |
| `--preview-finish` | Emit deterministic simulated maple PNG (`_finish.png`) from the exact burn mask. |
| `--preview-seed N` | Random seed for procedural wood grain (default 0). |
| `--preview-spread-mm N` | Simulated physical dot blur in mm (0–2 mm). |
| `--proof-sheet` | Emit single-page customer approval PDF (`_proof.pdf`) with embedded Vera font and sign-off lines. |
| `--client TEXT`; `--order TEXT` | Client name and order reference for the approval proof (max 240 chars each). |
| `--jig circle\|rectangle` | Generate registered pocket jig SVG with centered artwork. |
| `--blank-width IN`; `--blank-height IN` | Measured blank dimensions for jig pocket. |
| `--pocket-clearance IN` | Per-side physical clearance around blank. |
| `--kerf IN` | Full laser cut width compensation. |
| `--jig-margin IN`; `--jig-gap IN` | Margin around jig canvas and gap between pocket blanks. |
| `--jig-rows N`; `--jig-columns N` | Pocket grid counts (1–400 pockets total). |
| `--trim` | Crop empty exterior rows/columns from final burn mask; companion SVG preserves placement. |
| `--optimize-orientation` | Compare 0° and 90° scan rows and bed feasibility; does not rotate artwork. |
| `--engraving-lpi N` | Machine lines per inch for scan row estimation (required with `--optimize-orientation`). |
| `--orientation-constraint free\|grain\|reading` | Orientation lock: `grain` (material grain direction) or `reading` (text legibility). |
| `--version` | Display program version number (`0.2.0rc1`) and exit. |

## 7. Current boundaries and next product steps

This repository currently provides local raster image preprocessing, unified multi-operation SVG bundling, deterministic wood previews, client approval proofs, pocket jigs, and trimming/orientation advice. Software checks and automated regression gates pass locally. However, actual web-app import behavior, physical laser calibration, in-material burn results, and an interactive audition UI remain open milestones. The prioritized delivery plan and next steps are tracked in [roadmap.md](../roadmap.md), with exploratory concepts cataloged in [UPDATE-IDEAS.md](UPDATE-IDEAS.md).
