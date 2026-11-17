# Glowforge Image Prep

A local command-line tool for preparing raster artwork for Glowforge engraving. Compare image recipes at the intended size, export 300-DPI engraving PNGs, and optionally produce vector cut outlines, pocket jigs, finish previews, and proof PDFs. The default renderer is Atkinson dithering.

This is an **artwork preparation tool**, not a laser-control or material-safety system. It does not choose power, speed, focus, passes, or material settings, and it cannot promise a particular burn result. Review every design and operation in the Glowforge app and follow the makerspace’s machine and material procedures.

**Development version: 0.2.0rc2.dev1.** The last repository tag is `v0.2.0-rc.1`. App import and physical burn evidence are pending. See the [remediation record](docs/review-remediation.md) for software validation history and current release checks.

## Project stock context

The project’s default material context is **medium maple plywood at 1/8 inch**. The CLI prints the stock label and thickness for each batch. Change the descriptive stock name with `--material` and thickness with `--material-thickness` (inches; decimals or fractions such as `0.125` or `1/4`). These values do not alter image processing or select machine settings. Glowforge’s Proofgrade listing describes Medium Maple Plywood as approximately 1/8 inch and Thick as approximately 1/4 inch; local stock labels may differ, so check the actual sheet label and measure before use. Plywood cores and adhesives vary. Confirm compatibility with the supplier and current Glowforge guidance ([material settings FAQ](https://support.glowforge.com/hc/en-us/articles/4605501879963-print-settings-faq), [Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished)).

## Requirements and setup

Use Python 3.11 or newer. Install from a local checkout to get `gf` and `glowforge-it`:

```bash
git clone https://github.com/ryan258/glowforge-it.git
cd glowforge-it
uv tool install -e .
```

For PDF proofs, use `uv tool install -e '.[proof]'` in the install step. With an active Python environment, the corresponding pip commands are `python -m pip install -e .` and `python -m pip install -e '.[proof]'`.

The two commands differ in one default: `gf` adds `--clean-solids`, `glowforge-it`
leaves it off. Pass `--no-clean-solids` to `gf` to match.

To run without installing, `uv run main.py ...` reads the pinned dependencies from the
inline script metadata in `main.py`. For `--proof-sheet`, use `uv run --with reportlab main.py ...`.

## Quick start

Run these commands from the checkout using the included [synthetic coaster artwork](docs/examples/coaster-source.png). Open `output/quickstart/audition/coaster-source_audition.png` after the second command to compare the two recipes. The third command exports `line-art`, candidate 2, with the exact pixels that were auditioned. The last command verifies the resulting PNG and source against its manifest and checks the current engine.

```bash
gf --input docs/examples/coaster-source.png -o output/quickstart/audition --audition photo-soft line-art -w 2 -h 2 --dry-run
gf --input docs/examples/coaster-source.png -o output/quickstart/audition --audition photo-soft line-art -w 2 -h 2
gf --export-audition output/quickstart/audition/coaster-source_audition.json --candidate 2 -o output/quickstart/line-art
gf --verify-manifest output/quickstart/line-art/*_manifest.json --verify-current-engine
```

Use the selected PNG for engraving. To make a PNG with a separate SVG containing the raster and a circular vector cut outline, run:

```bash
gf --input docs/examples/coaster-source.png -o output/quickstart/cut --preset line-art --circle-cut --svg-cut --manifest -w 4 -h 4 --machine performance
```

Import the `_cut.svg` for that cut-and-engrave job. Inspect alignment and operation assignments in the Glowforge app before printing. [File upload guidance](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes).

Relative paths start at your **current working directory**. For your own artwork, pass its path to `--input`. Bare `gf` reads `./input` and writes `./output`.

## Maker workflow

The six first-version maker features are available: unified operation SVGs, explicit darkening/lightening curves, deterministic maple previews, one-page client proofs, measured single/grid pocket jigs, and placement-preserving trim. See the [maker workflow guide](docs/maker-workflow.md) for commands, geometry contracts, recipes, and app/physical acceptance steps.

```bash
gf --input docs/examples/coaster-source.png -o output/quickstart/proof --circle-cut -w 4 -h 4 \
  --svg-operations --material-mode darkening --proof-sheet --trim
```

Workflow jobs include versioned metadata and hashed manifests. Unified operation SVGs use red cuts and blue scores. Legacy `--svg-cut` uses blue cuts. Follow the [first-burn checklist](docs/first-burn-checklist.md#generate-the-synthetic-acceptance-pack) to generate a fresh verified pack and record app import and physical observations when available.

## Output behavior

- Supported inputs are PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. Animated GIFs use the first frame. Preflight dimensions account for EXIF orientation, including rotated TIFFs.
- High-bit-depth grayscale uses recognized sample ranges or finite minimum/maximum scaling. PNG color-key transparency is matched against original samples before scaling, so transparent pixels stay background and nearby opaque shades remain opaque even when they round to the same 8-bit value. NaN/infinity and constant images outside a recognized range are rejected during pixel processing, before publication; header-only dry-run does not inspect these samples. See the [handbook](docs/handbook.md#2-what-the-pipeline-does) for the normalization rules.
- Folder inputs are traversed in stable, sorted order (skipping hidden files such as macOS `._*` sidecars and temporary files) and their subfolder structure is mirrored under the output folder.
- PNGs are written at 300 DPI. Without explicit dimensions, pixel dimensions are preserved; with one dimension, the other is scaled proportionally.
- When both dimensions are supplied, `--fit stretch` (default) changes the aspect ratio (a warning is printed when the change exceeds 2%), `--fit contain` pads with white, and `--fit cover` center-crops. `contain` padding is always white, including with `--invert`.
- Ordinary output is a 1-bit black-and-white PNG. The default `--render-mode atkinson` uses error-diffused dot density; `silhouette` uses solid thresholded regions; `ordered` uses a tiled Bayer screen; `halftone` uses variable-radius circular screen cells; `hatch` uses directional line width, with optional crosshatching; `edge` extracts Sobel luminance transitions; and `contour` draws tone-band boundaries. Shape masks need transparency, so circle and heart PNGs use RGBA. `--svg-cut` omits the bitmap outline and draws the cut outline as a vector in the SVG sidecar.
- `--svg-linework` optionally writes a separate `_linework.svg` generated by thinning and tracing the final binary mask. It is centerline-style inspection/editing artwork, not a cut path, operation assignment, or replacement for the PNG. It suits clean line art or `--render-mode silhouette`; a trace of more than 250,000 skeleton points or 50,000 paths (dither dots, halftone, texture) fails with a message instead of writing a multi-megabyte SVG.
- `--tone-layers 2|3|4` optionally writes registered, exclusive tone-band PNG sidecars (`_tone01of3.png`, etc.) alongside the primary mask. They share the same canvas and dimensions; pure white is no burn in every layer. A common trim retains all layer content. They omit bitmap borders to avoid repeated burns; the primary mask retains its selected border behavior. Layer order and material/operation assignment still require owner review.
- `--stamp-text` and `--qr-text` write separate protected personalization masks. Stamp text accepts one line of printable ASCII. Both masks reject overlap with primary and tone-layer burn pixels or placement outside the usable circle or heart. QR also checks the text mask and reserves its full rectangle, including white modules and the four-module quiet zone. It supports version 1/L and 1–17 UTF-8 bytes. For a shape placement error, use the suggested margin or choose a different corner. Import the accepted masks separately in the app.
- Output names follow `<name>_<ext>_<recipe><dims>.png`, where `<recipe>` is `dithered` when every setting equals the library defaults (the `glowforge-it` command with no options) and `r` plus a 12-hex digest of the resolved settings, SVG options, and workflow for custom configurations, including every plain `gf` run because `gf` turns `--clean-solids` on. They do not contain an input-content hash or the material label, so different files with the same name can map to the same output path across runs. Existing outputs are overwritten by default; select `--existing skip` or `--existing error` to change that behavior.
- Filename preset auto-detection: when no explicit `--preset` is passed on the CLI, files matching `*--[mode].<ext>` (such as `fox--line-art.png` or `owl--photo-soft.png`) automatically apply that recognized preset mode for that job. The inferred preset fills only settings still at their defaults; recipe and CLI values win.
- The default per-image pixel limit is 20,000,000 for source, output, and expanded denoise and halftone intermediates. Raise it explicitly with `--max-pixels` only when your machine and available memory can handle the larger image.
- `--dry-run` reports destinations, pixel/physical dimensions, and estimated working memory without writing outputs or creating folders. Add `--json` for a structured plan.
- `--audition PRESET [PRESET ...]` renders each named preset at the requested final dimensions, then writes a numbered `_audition.png` contact sheet and `_audition.json` recipe/coverage record. Labels have consistent-width columns, measured wrapping and a separately wrapped header, including for narrow artwork. The sheet is a display proof only; it does not emit production engraving files. Audition rejects production sidecar options, supports at most 16 candidates, budgets the full wrapped sheet, and verifies source, recipe, runtime and sheet hashes before reuse.
- `--export-audition PATH --candidate NAME_OR_NUMBER` exports a saved candidate as a full-resolution PNG and manifest. It restores the original dimension arguments, resolved settings and polarity, finds the source relative to the record, checks source/contact-sheet hashes and the current engine, and checks rendered pixels against the audition before publication. Rendering overrides are rejected; output folder, existing-file policy, resource limits, machine preflight, provenance, dry-run and JSON/quiet output remain available. One `--input` file can relocate the source if its hash still matches. Older audition records without exact export data must be regenerated.
- `--max-memory 500MB` limits the estimated working buffers for orientation and compositing, denoise scratch space, dither arrays, rotated halftone canvases, vector tracing, sidecar masks, previews, proofs, and audition sheets. This estimate applies per image. PNG preflight skips compressed pixels and rejects copied metadata over 1 MiB.
- `--manifest` writes a companion JSON record with source/output hashes, dimensions, resolved recipe, material context, and optional `--prompt`/`--model` provenance. Text, QR, tone-layer and linework exports always include this record, even with `--no-manifest`; active maker workflows also require it. Source paths are relative to the manifest; keep that directory relationship when moving jobs, or pass `source_path` to the Python verifier.
- Manifest-backed `--existing skip` verifies source/output hashes, complete artifacts, recipe, requested prompt/model provenance, engine source, and runtime. Repeat the original prompt/model to reuse a job or use `--existing overwrite` to replace the record. Keep `--manifest` when reusing or replacing a name with a manifest. Choose a different output location for a plain export of that name. Regenerate older sidecar sets that lack a required manifest. Ordinary PNG and legacy cut-SVG jobs without a manifest use existence-only skip. With `skip` or `error`, a file that appears between planning and publication is preserved and the job asks you to rerun.
- Every export renders from a private disk snapshot. Source changes after planning or before publication fail the job; source and proof hashes describe the bytes actually rendered. Direct exports protect the source against destination aliases too.
- Publication writes a `.gf-publish-*.json` journal before changing job artifacts. An unresolved journal blocks export, dry-run planning, and reuse in that output directory. Use the [recovery procedure](docs/handbook.md#recover-an-interrupted-publication) to preview and resolve it. A committed cleanup warning preserves the new artifacts and names the journal.
- Finish previews and PDFs include text and QR masks, with a notice that they remain separate engraving imports. Tone-layer jobs reject finish previews/PDFs because layer assignment is unresolved. Jigs reject unreplicated text, QR, tone-layer and linework sidecars. Trimming retains the QR quiet zone and uses a common offset for all engraving masks.
- `--verify-manifest PATH` checks an archive’s source/output hashes without rendering. Its optional flags are `--verify-current-engine`, `--json`, and `--quiet`. The engine check compares the engine source fingerprint, Python, and dependency versions. Quiet mode still prints failures to stderr. Older manifests may verify as archives. To reuse output or export an audition from an older engine, use the recorded environment or regenerate the job with the current engine. Record physical results and approval separately.
- `--json` emits structured validation and usage errors as well as batch results (exit 2 for usage/validation, 1 for job/verification failure, 0 for success). Help and version requests retain their normal text output.
- `--recipe PATH` loads user profile settings from a `.toml` or `.json` file following documented precedence (`defaults -> preset -> recipe -> explicit overrides`).
- `--machine` checks an approximate nominal area: Performance 19.5 × 11 in, Aura 12 × 12 in, Spark 8.5 × 11 in. The usable area may be smaller depending on the design and print settings; the app is authoritative ([printable-area guidance](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area), [Craft Series specifications](https://glowforge.com/b/tech-specs/craft)).

## CLI reference

Use `gf --help` (or `uv run main.py --help`) for the current option list. `-h` is retained as the height flag, so help uses `--help`.

Python callers pass a `ProcessingSettings` to `run_batch(inputs, output_dir, settings)`, `prep_for_glowforge(input, output, settings)` or `transform_image(img, settings)`; omit it for defaults. Dimensions, destinations and workflow options stay separate keyword arguments. Field names match recipe and manifest keys (`black_thresh`, `denoise_radius`, …); defaults live in `settings.py`. Direct transformation/export accept `max_pixels` and `max_memory`; a custom manifest must be adjacent to its artifacts. See the [API migration guide](docs/api-migration.md).

For batch and audition, pass an iterable of file/folder paths: lists, tuples and generators can mix strings and `pathlib.Path` objects. The shared planner materializes those paths once, retaining directory containment and subfolder mirroring regardless of quiet or JSON logging.

Candidate numbers start at 1 in contact-sheet order. Exact names also work. See the [handbook](docs/handbook.md#exporting-a-selected-candidate) for replay and relocation details.

| Option | Purpose |
| --- | --- |
| `--input PATH [PATH ...]` | One or more input images or folders; defaults to `input/`. |
| `-o, --output DIR` | Destination folder; defaults to `output/`. |
| `-p, --preset NAME` | Image-preparation preset. Presets do not select material, power, speed, or pass settings. |
| `--audition PRESET ...` | Compare named presets in a mode-agnostic contact-sheet proof; do not combine with `--preset`. |
| `--export-audition PATH` | Export a saved audition candidate using its recorded source, dimensions, settings and pixel identity. |
| `--candidate NAME_OR_NUMBER` | Candidate name or 1-based sheet number; requires `--export-audition`. |
| `--recipe PATH` | Path to custom user recipe profile (`.toml` or `.json`). |
| `--material LABEL` | Descriptive stock label shown in the batch log; defaults to `medium maple plywood`. It does not change processing. |
| `--material-thickness IN` | Descriptive stock thickness in inches; default `0.125` (1/8). Accepts decimal or fraction notation such as `0.25` or `1/4`. It does not change processing. |
| `-w, --width IN` / `-h, --height IN` | Target dimension at 300 DPI. One dimension preserves aspect ratio. |
| `--fit MODE` | `stretch`, `contain`, or `cover`; applies when both dimensions are specified. |
| `--render-mode MODE` | `atkinson` (default), `silhouette`, `ordered`, `halftone`, `hatch`, `edge`, or `contour`; all produce binary burn masks. |
| `--silhouette-threshold N` | Burn values at or below `N` when `--render-mode silhouette` is selected. |
| `--ordered-matrix-size N` | Bayer matrix size (`2`, `4`, or `8`) for `--render-mode ordered`. |
| `--halftone-cell-px N` | Variable-cell halftone grid size in output pixels; minimum `2`. |
| `--halftone-angle DEGREES` | Rotate the variable-cell halftone screen from `0` up to but not including `180` degrees. |
| `--hatch-spacing-px N` | Directional hatch line spacing in output pixels; minimum `2`. |
| `--hatch-angle DEGREES` | Hatch line angle from `0` up to but not including `180` degrees. |
| `--hatch-cross` / `--no-hatch-cross` | Add or remove a perpendicular hatch family. |
| `--edge-threshold N` | Sobel edge strength threshold (`1`–`255`) for `--render-mode edge`. |
| `--contour-levels N` | Tone-band count (`2`–`64`) for `--render-mode contour`. |
| `-b, --black-threshold N` / `-W, --white-threshold N` | Force dark/light grayscale values to solid black/white. Values range from 0 to 255. |
| `--svg-linework` / `--no-svg-linework` | Write or omit the centerline-style `_linework.svg` sidecar; it is not a cutline. |
| `--tone-layers 0\|2\|3\|4` | Write 2–4 registered exclusive tone-band PNG sidecars; `0` disables them. |
| `--stamp-text TEXT` | Write a collision-checked personalization mask from one line of printable ASCII. Use `--stamp-position`, `--stamp-size-px`, and `--stamp-margin-px` to place it. |
| `--qr-text TEXT` | Write a collision-checked version-1/L QR mask for 1–17 UTF-8 bytes. Use `--qr-position`, `--qr-module-px`, and `--qr-margin-px` to place it. |
| `-d, --dither-threshold N` | Change the Atkinson midpoint decision boundary. |
| `-c, --clean-solids` / `--no-clean-solids` | Snap near-black and near-white pixels to solids. The `gf` command enables this by default. |
| `--clean-solids-black N` / `--clean-solids-white N` | Set the snapping boundaries. |
| `-i, --invert` / `--no-invert` | Invert grayscale values (tonal only; legacy mode only). |
| `--nb, --no-border` / `--border` | Omit or keep the default 1-pixel bitmap border; `--border` overrides a recipe that disables it. |
| `--denoise N` | Median-filter size; `0` turns denoising off, otherwise odd and at least 3. |
| `--contrast N`, `--sharpen-radius N`, `--sharpen-percent N`, `--sharpen-threshold N` | Adjust image contrast and unsharp masking. `--sharpen-radius 0` or `--sharpen-percent 0` turns sharpening off, so a preset stage can be explicitly disabled. |
| `--circle-cut` / `--heart-cut` | Apply a centered shape mask. The default black bitmap outline engraves; it is not a cut path. |
| `--svg-cut` | Legacy SVG sidecar with blue cut outline; requires a shape mask. |
| `--recover-publication PATH` | Recover one interrupted job or clear a committed cleanup journal. Preview with `--dry-run`. Output options are `--json` and `--quiet`. |
| `--verify-manifest PATH` | Check source/output hashes in an archived manifest; no rendering. |
| `--verify-current-engine` | With manifest verification, also require the current engine source, Python and libraries. |
| `--manifest` | Emit companion versioned JSON job manifest (`_manifest.json`) adjacent to output; mandatory for text, QR, tone layers, linework and active workflows, even with `--no-manifest`. |
| `--dry-run` | Preview planned destinations, dimensions, and memory without writing files or creating folders. |
| `--json` | Emit structured machine-readable JSON batch result summary. |
| `--quiet` | Suppress progress and summary logs; errors and failure messages still print to stderr (unless `--json`) and set the exit code. |
| `--max-memory SIZE` | Preflight memory budget (e.g. `500MB`, `1GB`) to reject over-budget jobs before pixel allocation. |
| `--prompt TEXT` / `--model TEXT` | Optional AI provenance metadata to record in the job manifest. |
| `--machine MODEL` | Optional nominal bed-area preflight for `performance`, `aura`, or `spark`. |
| `--max-pixels N` | Source/output pixel guard; defaults to 20,000,000. |
| `--existing POLICY` | `overwrite` (default), `skip`, or `error`. For PNG plus SVG, the policy applies to the complete output set. |
| `--svg-operations` | Opt in to unified SVG: embedded monochrome raster, red cuts, blue scores. |
| `--score-marks` | Add an intentional blue L-shaped orientation score at top left. |
| `--material-mode MODE` | Substrate ablation polarity: `darkening` (light wood/substrate) or `lightening` (slate/dark acrylic). |
| `--tone-black N` / `--tone-white N` | Tonal curve clipping boundaries (0–255). |
| `--tone-gamma N` | Tonal gamma exponent (> 0). |
| `--preview-finish` | Emit deterministic simulated maple PNG (`_finish.png`) from the exact burn mask. |
| `--preview-seed N` | Random seed for procedural wood grain (default 0). |
| `--preview-spread-mm N` | Simulated physical dot blur in mm (0–2 mm). |
| `--proof-sheet` | Emit single-page customer approval PDF (`_proof.pdf`) with embedded Vera font and sign-off lines. |
| `--client TEXT` / `--order TEXT` | Client name and order reference for approval proof (max 240 chars each). |
| `--jig SHAPE` | Generate registered pocket jig SVG (`circle` or `rectangle`). |
| `--blank-width IN` / `--blank-height IN` | Measured blank dimensions for jig pocket. |
| `--pocket-clearance IN` | Per-side physical clearance around blank. |
| `--kerf IN` | Full laser cut width compensation. |
| `--jig-margin IN` / `--jig-gap IN` | Margin around jig canvas and gap between pocket blanks. |
| `--jig-rows N` / `--jig-columns N` | Pocket grid counts (1–400 pockets total). |
| `--trim` | Crop empty exterior rows/columns from final burn mask; companion SVG preserves placement. |
| `--version` | Display program version number and exit. |

## Presets

Presets are starting points for image processing only. They are not empirically validated recipes for a specific sheet, Glowforge model, or operation. Make small proof tests and use the machine profile approved by your makerspace.

| Preset | Image use |
| --- | --- |
| `photo-high-detail`, `photo-soft` | Photo/portrait starting points |
| `vector-graphic`, `line-art`, `sketch`, `high-contrast`, `stamp` | Graphics, line work, drawings, or stencil-like art |
| `ai-art`, `ai-art-detailed`, `low-res-enhance` | AI-generated or lower-resolution source cleanup |
| `wood-hard`, `wood-soft`, `acrylic`, `leather`, `glass` | Contrast/sharpening starting points for named art/material workflows; they do not validate material compatibility or machine settings |

## Documentation

- [Review remediation](docs/review-remediation.md): corrections, validation commands and open decisions.
- [API migration](docs/api-migration.md): pre-1.0 signature, recipe and reuse changes.
- [First-burn checklist](docs/first-burn-checklist.md): record app observations and measured results against an exact revision.
- [Maker workflow guide](docs/maker-workflow.md): unified SVGs, ablation polarity, maple previews, client proofs, pocket jigs, and trimming.
- [Engraving handbook](docs/handbook.md): pipeline, presets, sizing, cutout, and maker workflow.
- [30 best commands](docs/best-commands.md): examples and what each command actually produces.
- [ELI5 guide](docs/eli5.md): simple explanation of grayscale, dithering, and cut paths.
- [101 project ideas](docs/101-ways-to-make-fun-and-profit.md): inspiration list with explicit notes about what this CLI does and does not create.
- [101 art directions for laser artwork](docs/101-art-styles-that-work-surprisingly-well-with-examples.md): source-art prompts paired with image-preparation starting points.
- [Changelog](CHANGELOG.md): completed milestones, engine hardening, and modularization history.
- [Project roadmap](roadmap.md): staged work, backlog ideas, open risks and the evidence boundary.
- [Cow image prompts](docs/cow-prompts.md): optional source-art prompts; generated artwork still needs inspection and fitting.
