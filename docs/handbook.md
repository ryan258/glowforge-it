# Glowforge Image Preparation Handbook

This guide explains what this repository does, how its raster pipeline behaves, and how to prepare files for review in the Glowforge app. It covers artwork preprocessing; it does not control the laser or replace material compatibility checks, machine settings, proof cuts, or supervision.

## 1. Project and material context

The default makerspace stock context is **medium maple plywood at 1/8 inch**. The CLI reports the label and thickness for each batch. Change them with `--material` and `--material-thickness` (for example, `--material-thickness 1/4`). These values describe the stock; they do not change pixels or choose power, speed, focus, or passes.

Check the stock label and measure the sheet. Glowforge’s own Proofgrade Maple Plywood listing uses Medium for approximately 1/8 inch and Thick for approximately 1/4 inch. “Medium” may mean something different for local stock. Plywood cores and adhesives vary; confirm the actual material with the supplier, its safety data, and the makerspace operator. Glowforge warns that settings for a similarly named material may not be safe or effective for non-Proofgrade stock ([Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished), [Print Settings FAQ](https://support.glowforge.com/hc/en-us/articles/4605501879963-print-settings-faq)).

The presets below change image processing only. They are not machine recipes. Use the material and operation profile approved for the specific Glowforge, and make a small proof test when required by the makerspace. Follow the current manual and never leave a print unattended ([Glowforge manuals](https://glowforge.com/manual), [Working With Manual Mode](https://support.glowforge.com/hc/en-us/articles/360033633574-Working-With-Manual-Mode)).

## 2. What the pipeline does

The CLI validates settings and resource limits, then takes a stable source snapshot. For each snapshot it applies these steps in order:

1. Applies EXIF orientation so a camera image is processed in its displayed orientation. Preflight and rendering use the same displayed dimensions for rotated TIFFs.
2. Composites transparency over the no-burn source endpoint, then converts to grayscale. The endpoint is normally white and changes to black for `--invert` or explicit lightening mode.
3. Optionally median-filters noise (`--denoise`). The pixel and memory budgets account for the enlarged filter canvas before rendering.
4. Optionally inverts grayscale values (`--invert`, legacy mode only). This is a *tonal* flip only: it does not mirror, rotate, or otherwise move pixels.
5. Resizes to the requested physical dimensions at 300 DPI. If only width or height is given, it preserves aspect ratio. If both are given, `--fit` chooses how to handle a different source aspect ratio (`stretch`, `contain`, or `cover`). For `--fit contain`, the artwork is scaled proportionally and placed onto white layout padding after dithering, ensuring padding never receives contrast or error diffusion.
6. Optionally snaps near-black/near-white values with `--clean-solids`, then applies hard black and white thresholds. `--clean-solids-black`/`--clean-solids-white` are the *snapping* boundaries; `-b`/`-W` are the hard thresholds.
7. Applies contrast and unsharp masking.
7.5. For explicit material modes (`--material-mode darkening` or `lightening`), applies versioned levels and gamma curves (`--tone-black`, `--tone-white`, `--tone-gamma`) via a lookup table. Transparent pixels remain no-burn.
8. Renders the grayscale image to a 1-bit burn mask. `--render-mode atkinson` (the default) uses error diffusion; `silhouette` applies `--silhouette-threshold` directly; `ordered` uses a Bayer matrix; `halftone` uses variable-radius circular screen cells; `hatch` uses directional line width with optional crosshatching; `edge` keeps Sobel luminance transitions; and `contour` draws tone-band boundaries. Atkinson explicitly preserves source endpoints (0 and 255) in material modes; other renderers retain their own pattern semantics. For `--fit contain`, the rendered image is placed onto the target white canvas; layout padding is always white.
9. Applies a circle/heart transparency mask when selected and adds a 1-pixel black bitmap border by default (suppressed with `--no-border`, `--svg-cut`, `--svg-operations`, or `--jig`). The border is burn content and precedes trimming.
9.5. Renders requested tone layers from the same source and places text/QR on the original canvas, checking overlap across masks. `--trim` crops all engraving masks to a shared content rectangle, retaining the QR quiet zone and recording the common offset. The operations SVG preserves original-canvas placement of the primary artwork; sidecars remain separate imports.
10. Writes output files: 300-DPI PNG engraving, optional legacy cut SVG, optional centerline-style `_linework.svg` derived from the final mask, optional registered exclusive tone-band PNGs from `--tone-layers`, optional collision-checked `_stamp.png`/`_qr.png` personalization masks, optional unified SVG (`_operations.svg` with red cuts, blue scores, and embedded PNG), optional finish preview (`_finish.png`), optional client approval PDF (`_proof.pdf`), and versioned metadata (`_manifest.json` and `_workflow.json`). The linework SVG is inspection/editing artwork, tone layers are aligned artwork masks, and personalization sidecars are protected add-ons; none is an app-operation proof.

Atkinson dithering sends one eighth of each pixel’s quantization error to six nearby pixels. Its dot pattern is a visual starting point; silhouette mode intentionally avoids dot density, ordered mode makes the screen periodic, halftone mode makes tone legible through circular dot area, hatch mode makes tone legible through line width and directional density, edge mode isolates contrast boundaries, and contour mode isolates quantized tone boundaries. The material, machine, print step, and app settings control the physical result.

High-bit-depth grayscale is normalized after orientation and before compositing/filtering. Unsigned 16-bit samples use 0–65535. Integer-mode (`I`) samples use 0–255 when their maximum is at most 255, or 0–65535 when their maximum is at most 65535, provided the minimum is nonnegative. Float-mode (`F`) samples within 0–1 use that range. Other finite, varying integer/float images scale from their own minimum to maximum. NaN/infinity and constant images outside a recognized range are rejected rather than silently creating a black mask. A constant within a recognized range retains its value on that scale. These are pixel-dependent checks; dry-run does not decode samples and cannot establish their validity.

For grayscale PNG color-key transparency, the alpha mask is derived from the original sample values before normalization. An opaque neighboring shade remains opaque even if both values round to the same 8-bit gray. Fully transparent areas stay no-burn across renderers and material modes. The optional bitmap border is drawn separately.

The ordered, halftone, and hatch parameters describe displayable artwork patterns, not guaranteed physical dot or line sizes. Inspect the output at the requested final dimensions and use a small approved proof before relying on fine dots, lines, or gaps.

### Auditioning presets at final dimensions

Use `--audition` when comparing image-preparation recipes before selecting a production export:

```bash
gf --input input/design.png -o output/audition \
  --audition photo-soft line-art stamp \
  --width 4 --height 4 --fit contain
```

The command applies every candidate to the full requested output dimensions, then writes one `_audition.png` contact sheet and one `_audition.json` record per source. The record includes each resolved recipe, original dimension arguments, full-resolution pixel hash, physical size, burn-mask coverage, and bounds. Consistent-width columns keep numbered labels readable for narrow artwork; headers and labels wrap by measured width, with the resulting sheet included in memory preflight. The contact sheet is a display proof with labels; it is not machine artwork and does not claim a material result.

### Exporting a selected candidate

Use the candidate's sheet number or name:

```bash
gf --export-audition output/audition/design_audition.json --candidate 2 -o output/selected
```

Numbers start at 1 in sheet order. An exact candidate name takes precedence if a Python-created label is itself numeric. Unknown selections list the available numbers and names. The command re-renders the original source using the exact recorded settings, original width/height arguments and workflow polarity. It does not resize a contact-sheet tile. Neither the `gf` clean-solids default nor a filename-inferred preset changes the saved candidate.

The exporter checks the current engine/runtime, original source hash and contact-sheet hash, then verifies the rendered candidate's pixel hash before staging output. It writes a production PNG plus a required manifest whose recipe records the candidate name and `audition_pixels_sha256`. Active recorded polarity workflows also retain their normal workflow sidecar. Source changes between selection, planning and publication are rejected. Existing-output policies, collision checks, resource limits and recoverable publication still apply.

The source is resolved relative to the audition JSON, so the working directory does not matter. If the source was moved, supply one `--input` file; its bytes must match the recorded source hash. Keep the contact sheet adjacent to the record. Older records without the original dimension arguments and pixel hashes need a new audition before direct export; the tool does not guess missing settings.

Rendering, size, recipe and production-sidecar overrides are rejected to preserve the selected pixels. You can still choose output location, existing-file policy, machine/resource preflight, prompt/model provenance, dry-run and JSON/quiet output. Dry-run checks records, hashes, destinations and resource bounds without rendering or creating output directories; the pixel comparison runs during export. Selection leaves the audition files unchanged and never records approval.

### Choosing a fit mode

- `stretch` fills the target size and can distort proportions; a warning is printed when the change exceeds 2%.
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

The `gf` command enables `--clean-solids` by default. When launching `uv run main.py` directly, clean-solids is disabled unless you pass `-c`.

## 4. Coaster masks and vector cut outlines

A bitmap outline is engraved artwork, not a cut path. Glowforge’s documentation describes SVG/PDF vectors as the route for cut and score paths, while PNG/JPG are for engraving ([Upload Your Own Design File](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [Simplify Strokes](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes)).

### PNG-only shape mask

```bash
gf --input input/design.png --circle-cut -w 4 -h 4
```

This creates a 4 × 4 inch transparent circle mask and, by default, an opaque 1-pixel bitmap edge. The bitmap edge will engrave. The heart preset works similarly:

```bash
gf --input input/design.png --heart-cut -w 4 -h 4
```

### Legacy PNG plus SVG cut sidecar

```bash
gf --input input/design.png --circle-cut --svg-cut -w 4 -h 4
```

This writes a PNG plus a sibling file ending in `_cut.svg`. The PNG remains the raster engraving. In the SVG, the bitmap border is omitted and the circle/heart is drawn as a blue vector stroke.

### Unified multi-operation SVG and maker workflow

For complete jobs with distinct print operations, opt in to `--svg-operations`:

```bash
gf --input input/design.png --circle-cut -w 4 -h 4 \
  --svg-operations --score-marks --material-mode darkening
```

This emits `_operations.svg` using the unified maker palette: embedded monochrome PNG for engraving, red (`#ff0000`) for vector cuts, and blue (`#0000ff`) for vector scores (including top-left L score marks for alignment).

Key maker workflow capabilities:
- **Ablation Polarity & Tone Curves:** `--material-mode darkening` (burn darkens substrate) or `lightening` (burn lightens substrate, e.g. slate, dark acrylic). Controlled by `--tone-black`, `--tone-white`, and `--tone-gamma`.
- **Deterministic Maple Finish Preview:** `--preview-finish` writes `_finish.png` showing simulated burn on wood grain. Configure spread with `--preview-spread-mm` and seed with `--preview-seed`.
- **One-Page Client Approval Proof:** `--proof-sheet` writes `_proof.pdf` with side-by-side source and simulated finish, material details, SHA-256 revision hash, and printable sign-off lines. Pass `--client` and `--order` for metadata tracking.
- **Registered Pocket Jigs:** `--jig circle` or `--jig rectangle` with measured `--blank-width`, `--blank-height`, `--pocket-clearance`, `--jig-margin`, and `--kerf`. Add `--jig-rows` and `--jig-columns` for multi-pocket grids.
- **Empty-Bounds Trimming:** `--trim` crops empty outer burn mask bounds while preserving placement in companion SVG.

See the dedicated [Maker Workflow Guide](maker-workflow.md) for detailed contracts, geometric formulas, and step-by-step procedures.

## 5. Batch and output behavior

- `--input` accepts one or more images and folders. Supported extensions are PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. Animated GIF input uses its first frame.
- Folder traversal is sorted and preserves subfolders in the output. An output directory inside an input folder is rejected to avoid processing generated results again.
- The default source/output limit is 20,000,000 pixels per image. `--max-pixels` changes it.
- Optional `--machine` checks nominal dimensions (`performance`, `aura`, `spark`). It is a preflight hint only; usable area may be smaller in the app.
- Filenames are `<name>_<ext>_<recipe><dims>.png`: `<recipe>` is `dithered` only when every setting equals the library defaults (the `glowforge-it` command with no options), otherwise `r` plus a 12-hex digest (every plain `gf` run, since `gf` enables `--clean-solids`) of the resolved settings, SVG options and workflow; `<dims>` is the requested size such as `_w4h4`. The manifest records the readable recipe. When no explicit `--preset` is passed on the CLI, files matching `*--[mode].<ext>` automatically infer that preset; the inferred preset fills only settings you have not changed from their defaults, so recipe and CLI values still win. Existing outputs are overwritten by default; choose `--existing skip` or `--existing error` to preserve prior work.
- `--manifest` writes `_manifest.json`. Text, QR, tone layers and linework require it automatically, including with `--no-manifest`. An active maker workflow additionally writes `_workflow.json` and requires the manifest. Verified `--existing skip` checks source/output hashes, complete artifacts, recipe, requested prompt/model provenance, engine source fingerprint, Python and dependency versions. Changing or omitting earlier provenance requires explicit overwrite; repeat the original values to reuse. Older sidecar sets without the manifest are incomplete. Only ordinary PNG/legacy cut-SVG jobs without a manifest use existence-only skip. Archive-only verification uses `--verify-manifest PATH`; add `--verify-current-engine` for engine matching.
- Keep `--manifest` when reusing or replacing a job with that name and an existing manifest. To write a plain export of the same source and recipe, choose a different output location.
- Staged publication writes a recovery journal before changing artifacts. An unresolved journal blocks export, dry-run planning, and reuse in that job directory.

### Recover an interrupted publication

Use the `.gf-publish-*.json` path printed in the error or cleanup warning. After the writer stops, replace `JOURNAL` with that path and preview the recovery. Keep the quotes, especially when the path contains spaces.

```bash
gf --recover-publication "JOURNAL" --dry-run
```

Review the proposed actions, then apply them by dropping `--dry-run`:

```bash
gf --recover-publication "JOURNAL"
```

Recovery restores the previous artifacts of an interrupted job or removes newly created artifacts when there was no previous generation. For a committed journal, recovery clears its remaining temporary files after verifying the complete published job. If a published artifact is changed or missing, recovery retains the journal and backups for inspection. Recovery checks the canonical job directory and the recorded artifact, backup, and staging hashes.

Use `--json` for structured actions or `--quiet` for silent success. The journal path identifies the job. Recovery accepts only these output flags and `--dry-run` alongside that path.

On macOS and Linux, publication and applied recovery take an exclusive advisory lock on the job directory. Recovery preview takes a shared lock. The lock requires no separate file and covers publication or recovery. Rendering happens before the lock. If a process stops before the journal is in place, the directory can contain unlisted `.gf-stage-*` or `.gf-journal-*` temporary files. The recovery command works from a named journal and applies to one job after a process interruption. Keep independent backups for storage failures.

## 6. CLI reference

`-h` means height, so request help with `--help`.

| Option | Meaning |
| --- | --- |
| `--input PATH [PATH ...]` | Source images or folders; default `input/`. |
| `-o, --output DIR` | Destination folder; default `output/`. |
| `-p, --preset NAME` | Select an image preset from section 3. |
| `--audition PRESET ...` | Compare named presets in a mode-agnostic contact-sheet proof; do not combine with `--preset`. |
| `--export-audition PATH` | Export a saved audition candidate as a full-resolution PNG and required manifest. |
| `--candidate NAME_OR_NUMBER` | Candidate name or 1-based contact-sheet number; requires `--export-audition`. |
| `--recipe PATH` | Path to custom user recipe profile (`.toml` or `.json`). |
| `--material LABEL` | Descriptive run label; defaults to `medium maple plywood`; no machine effect. |
| `--material-thickness IN` | Descriptive thickness in inches; default `1/8` (`0.125`). |
| `-w, --width IN`; `-h, --height IN` | Target physical dimension at 300 DPI. |
| `--fit MODE` | `stretch`, `contain`, or `cover` when both dimensions are set. |
| `--render-mode MODE` | `atkinson` (default), `silhouette`, `ordered`, `halftone`, `hatch`, `edge`, or `contour`; all produce binary burn masks. |
| `--silhouette-threshold N` | Burn values at or below `N` when `--render-mode silhouette` is selected (0–255). |
| `--ordered-matrix-size N` | Bayer matrix size (`2`, `4`, or `8`) for `--render-mode ordered`. |
| `--halftone-cell-px N` | Variable-cell halftone grid size in output pixels; minimum `2`. |
| `--halftone-angle DEGREES` | Rotate the variable-cell halftone screen (`0` to `<180` degrees). |
| `--hatch-spacing-px N` | Directional hatch line spacing in output pixels; minimum `2`. |
| `--hatch-angle DEGREES` | Hatch line angle (`0` to `<180` degrees). |
| `--hatch-cross` / `--no-hatch-cross` | Add or remove a perpendicular hatch family. |
| `--edge-threshold N` | Sobel edge strength threshold (`1`–`255`) for `--render-mode edge`. |
| `--contour-levels N` | Tone-band count (`2`–`64`) for `--render-mode contour`. |
| `-b, --black-threshold N`; `-W, --white-threshold N` | Force dark/light values to solid black/white (0–255). |
| `--svg-linework` / `--no-svg-linework` | Write or omit centerline-style `_linework.svg` sidecar; it is not a cutline. |
| `--tone-layers 0\|2\|3\|4` | Write 2–4 registered exclusive tone-band PNG sidecars; `0` disables them. |
| `--stamp-text TEXT` | Write a collision-checked personalization mask from one line of printable ASCII. Use `--stamp-position`, `--stamp-size-px`, and `--stamp-margin-px` to place it. |
| `--qr-text TEXT` | Write a collision-checked version-1/L QR mask for 1–17 UTF-8 bytes. Use `--qr-position`, `--qr-module-px`, and `--qr-margin-px` to place it. |
| `-d, --dither-threshold N` | Atkinson decision threshold, 0–255. |
| `-c, --clean-solids`; `--no-clean-solids` | Enable/disable near-solid snapping. |
| `--clean-solids-black N`; `--clean-solids-white N` | Near-black and near-white boundaries. |
| `-i, --invert`; `--no-invert` | Invert grayscale values (tonal only; legacy mode only). |
| `--nb, --no-border` / `--border` | Omit or keep the default 1-pixel bitmap border; `--border` overrides a recipe that disables it. |
| `--denoise N` | Median-filter size: `0` (off) or an odd number of at least 3. |
| `--contrast N`; `--sharpen-radius N`; `--sharpen-percent N`; `--sharpen-threshold N` | Contrast and unsharp-mask options. |
| `--circle-cut`; `--heart-cut` | Apply a raster transparency mask. These are mutually exclusive. |
| `--svg-cut` | Add legacy vector-outline SVG sidecar (blue stroke); requires a shape mask. |
| `--manifest` | Emit companion versioned JSON job manifest (`_manifest.json`); required for text, QR, tone layers, linework and active workflows, even with `--no-manifest`. |
| `--dry-run` | Preview planned destinations, dimensions, and memory without writing files or creating folders. |
| `--json` | Emit structured machine-readable JSON batch result summary. |
| `--quiet` | Suppress progress and summary logs, including successful manifest verification; failures still print their reasons to stderr (unless `--json`) and set the exit code. |
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
| `--recover-publication PATH` | Recover an interrupted job or clear a committed cleanup journal. Preview with `--dry-run`. |
| `--verify-manifest PATH` | Check archived source and output hashes. Optional flags are `--verify-current-engine`, `--json`, and `--quiet`. |
| `--verify-current-engine` | With manifest verification, also require the current engine source, Python and libraries. |
| `--version` | Display program version number and exit. |

## 7. Current boundaries and next product steps

The CLI provides raster preparation, contact-sheet audition and exact candidate export, operation SVGs, simulated wood finishes, review PDFs, pocket jigs, and trimming. See the [remediation record](review-remediation.md) for software validation and the [first-burn checklist](first-burn-checklist.md) for recording app import and physical observations. Exact-pixel inspection and interactive audition are tracked in the [roadmap](../roadmap.md).
