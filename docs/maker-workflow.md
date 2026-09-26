# Maker workflow: first useful version

The six MW01–MW06 slices are available locally. This document describes software behavior, not physical calibration or acceptance in the Glowforge app. Generate a reproducible synthetic review set with:

```bash
.venv/bin/python scripts/maker_demo.py
```

The script writes a proof, finish PNG, import SVG, and a separate 2 × 3 pocket jig under `output/maker-demo/`. Its 2.02-inch blank dimensions and kerf are **example values, not measurements of your stock**. It never uploads or prints.

## One file with multiple operations

```bash
gf --input input/art.png -o output/job --circle-cut -w 4 -h 4 \
  --svg-operations --score-marks --material-mode darkening
```

`--svg-operations` writes `_operations.svg` with an embedded monochrome engraving raster, unfilled red (`#ff0000`) cut paths, and optional unfilled blue (`#0000ff`) score marks. Circle/heart options supply cut paths; without a shape, no outer cut path is invented. The score is one L-shaped orientation mark at the upper left; it is intentional scored content, not a nonprinting guide. On a jig it sits within the reserved margin. Inspect it before enabling Score.

Legacy `--svg-cut` remains blue-cut and keeps its existing filename/default behavior. Do not combine it with `--svg-operations`, `--trim`, or `--jig`. This opt-in palette is the only palette change in this version.

Colors separate steps; they do not guarantee operation assignments or order. Review Engrave, Score, Cut and their order in the app. Ordinary artwork suggests engraving, then score, then cut. Jig operation is a separate two-phase workflow below. [Glowforge's step-order guidance](https://support.glowforge.com/hc/en-us/articles/20546433415451-setting-the-order-of-your-print-steps) explains grouping and manual ordering.

## Explicit ablation polarity and curves

```bash
gf --input input/art.png -o output/lightening --no-border \
  --material-mode lightening --tone-black 10 --tone-white 245 --tone-gamma 1.2
```

`legacy` is the unchanged default. `darkening` targets dark marks on a light substrate; `lightening` targets light marks on a dark substrate. These modes express appearance polarity only. They select no laser settings and do not imply that any named material is suitable.

Processing order: EXIF orientation → transparency compositing → denoise → legacy invert (legacy only) → resize/fit → existing solid cleanup/thresholds → contrast → sharpening → explicit levels/gamma/polarity → Atkinson dithering → no-burn padding → shape mask/border.

The versioned `burn-v1` curve is:

```text
L = clamp((luminance - tone_black) / (tone_white - tone_black), 0, 1)
L = L ** (1 / tone_gamma)
darkening engraving intensity = 255 * L
lightening engraving intensity = 255 * (1 - L)
```

Black engraving pixels mean burn for both modes; white means no burn. Explicit endpoints stay endpoints even with an extreme dither threshold. Contain padding and fully transparent source pixels remain no-burn. Partial transparency composites onto the polarity's no-burn source endpoint. Shape-masked pixels are excluded by alpha. An intentional bitmap border remains burn content.

Combining an explicit material mode with legacy `--invert` is rejected. Curves require an explicit material mode; there are no automatically calibrated slate/glass profiles. Use `--contrast 1 --sharpen-radius 0 --no-clean-solids` when isolating the tonal curve for a ramp test. Gamma > 1 raises desired luminance; its effect on burn coverage depends on polarity.

## Reproducible maple preview and client proof

```bash
gf --input input/art.png -o output/review --circle-cut -w 4 -h 4 \
  --svg-operations --material-mode darkening --preview-finish \
  --preview-seed 17 --preview-spread-mm 0.05 \
  --proof-sheet --client 'Client name' --order 'Order reference'
```

`--preview-finish` writes `_finish.png`. `maple-v1` uses seeded procedural grain at 300 DPI and a caramel mark color. `--preview-spread-mm` is Gaussian blur radius in physical millimeters, bounded to 0–2 mm, applied only to the displayed burn coverage. The source for the preview is the exact final engraving mask, before optional lossless trimming. The preview preserves shape transparency. No preview pixels enter the engraving output.

The preview profile, seed, scale, polarity, spread, pixel hash and simulation label are recorded. The PNG also embeds the simulation label and revision as text metadata. The visible label is on the PDF and this guide. Preview grain is illustrative, not measured wood texture. Compare physical samples before claiming realism. Maple preview rejects lightening and inverted artwork instead of displaying a misleading finish.

`--proof-sheet` implies the finish PNG and produces a single US Letter PDF with source/finish, artwork dimensions, descriptive material/thickness, optional client/order, full revision/source hashes, and blank approval/name/date/revision lines. Images retain their aspect ratio. The PDF is a review copy, not a placement template. Its preview shows engraving; optional vector score marks must also be reviewed in the SVG. A jig proof shows one blank and labels the grid quantity.

The SHA-256 revision binds source bytes, resolved recipe, engraving bytes, full mask, geometry, SVG when present, and appearance profile/pixels. The proof and all companion files are hashed in the manifest. Changes require a new proof revision; generation always records `customer_approved: false`. Sign-off lines are printable fields, not digital signatures. Sending the PDF or recording actual approval remains a separate owner action.

Client/order text is limited to 240 characters, embedded in the local PDF and metadata but excluded from literal filenames. The embedded Vera font supports Latin and many European characters; unsupported glyphs or metadata too long for the page fail before publication rather than silently clipping or substituting boxes.

## Registered pocket jig: one blank, then a grid

Start with **actual measurements** and verify one pocket physically before increasing rows/columns:

```bash
gf --input input/art.png -o output/jig-one --machine performance \
  --circle-cut -w 3.9 -h 3.9 --jig circle \
  --blank-width 4 --blank-height 4 --pocket-clearance 0.01 \
  --jig-margin 0.25 --kerf 0.006 --trim --no-border
```

All geometry arguments are inches. `--blank-width`/`--blank-height`, `--pocket-clearance` and `--jig-margin` are required. Clearance is **per side**. Kerf is the measured full cut width, default zero (uncompensated). The model is:

```text
finished pocket size = measured blank size + 2 * per-side clearance
laser path size       = finished pocket size - full kerf
pitch                 = finished pocket size + jig gap
```

`--jig rectangle` supports rectangular blanks. Circles require equal measured dimensions plus square artwork and `--circle-cut` so engraving stays on the blank. Artwork cannot exceed the measured blank. Pocket cuts replace artwork cut outlines in jig output: the second phase must never recut the blank.

Once the single pocket fits, add `--jig-rows 2 --jig-columns 3 --jig-gap 0.25`. The grid is bounded to 400 pockets and checked against the chosen nominal machine bed. Gap is material remaining between finished pockets; negative clearances, impossible kerf, overlaps, and out-of-bounds layouts are rejected. Fractional pixel vector coordinates retain measured geometry. Manifest/workflow metadata records finished pocket sizes, compensated path sizes, canvas, centers, and artwork offsets in the same coordinate system.

1. Import the single SVG and check dimensions, groups, centers and operation assignments.
2. Ignore engraving. Cut the pockets (and optional orientation score) in jig stock.
3. Secure the jig; remove pocket waste and insert blanks. Do not move the jig or imported design.
4. Ignore cuts and score. Enable engraving and review focus/material settings for the blanks.
5. Measure fit and repeat placement with machine and stock recorded before production.

A circular pocket does not constrain rotation. Add a physical orientation stop or use a consistent mark for asymmetric art. This first version does not implement keyed/double-sided jigs, nesting, or claims of measured placement accuracy. Margins are margins around the jig canvas, not a promised position relative to the physical machine origin.

## Trimming

```bash
gf --input input/art.png -o output/trim --no-border --trim --machine performance
```

`--trim` crops only empty exterior rows/columns of the final burn mask. Remaining pixels are unchanged. Its SVG keeps the original canvas, cutlines and placement offsets. The standalone PNG has smaller physical dimensions and loses placement context; use the SVG for registered placement. With no burn content, PNG is a 1×1 white sentinel, SVG contains no engraving image, and metadata/CLI reports `NO ENGRAVE`. Intentional bitmap borders count as content and prevent trimming unless explicitly disabled. Unified SVG/jig mode omits the old bitmap border because cuts have their own vectors.

## Recipes, planning, publication and reuse

New options can live in the existing TOML/JSON recipe under `workflow`:

```toml
material = "medium maple plywood"
material_thickness_in = 0.125
no_border = true

[workflow]
material_mode = "darkening"
svg_operations = true
preview_finish = true
preview_seed = 17
tone_gamma = 1.0
```

CLI values override workflow recipe values. Python callers pass `WorkflowOptions(...)` as `workflow=` to `run_batch`. All new options are opt-in, and any active workflow automatically emits `_workflow.json` and the normal `_manifest.json`. The workflow configuration is part of the filename's recipe digest; use `--existing error` when preserving a prior source revision because the filename is not a source-content hash.

Dry-run lists every artifact and bounds memory for masks, preview/proof buffers, and repeated SVG images without creating files. Pixel-dependent trim bounds, previews and row counts are resolved during rendering, not header-only dry-run. All new artifacts participate in source/destination collision checks, existing-output policy, content-hash reuse checks, and the same recoverable publication transaction as PNG/SVG. Missing or changed companions fail `--existing skip`; failed PDF generation leaves the previous complete output set intact.

## Acceptance record

Software checks cover explicit polarity endpoints and monotonic ramp coverage, no-burn padding/transparency, deterministic preview and unchanged engraving pixels, XML palette/portable embedded raster, pixel-exact crop offsets, registered grid/kerf, resource guards, blank jobs, revision binding, tamper rejection and publication failure preservation. PDF review includes one-page rendering, embedded font, long/absent metadata and portrait/landscape samples.

**Glowforge app acceptance remains pending.** The browser check on 2026-09-25 reached the owner sign-in page; no design was uploaded or printed. Use the demo SVG after sign-in and record:

| Check | Expected / record |
|---|---|
| Physical size | Proof SVG: 2 × 2 in; jig SVG dimensions from its workflow JSON |
| Raster | One engraving group, portable embedded image, expected orientation |
| Vector groups | Red cuts separate from blue L score; no duplicate cut paths |
| Assignments/order | Explicitly select operations; record actual imported order before reordering |
| Registration | Raster/circle centered; cropped raster retains its original offset; six jig centers match |
| Empty bounds | Compare app bounds and settings with untrimmed control |
| Physical acceptance | One measured pocket fit, repeated placement error, actual tonal ramp and maple appearance |

Digital geometry is not evidence of physical accuracy. This implementation does not establish machine/material settings, customer approval, or calibrated production time.
