# Maker workflow: first useful version

The six MW01–MW06 slices are available locally. Use the [first-burn checklist](first-burn-checklist.md#generate-the-synthetic-acceptance-pack) to generate and verify a fresh pack with legacy circle and heart SVGs, a unified trim comparison, a proof PDF and finish PNG, and a 2 × 3 pocket jig.

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

Processing order: EXIF orientation → transparency compositing → denoise → legacy invert (legacy only) → resize/fit → existing solid cleanup/thresholds → contrast → sharpening → explicit levels/gamma/polarity → selected binary renderer → no-burn padding → shape mask/border.

The versioned `burn-v1` curve is:

```text
L = clamp((luminance - tone_black) / (tone_white - tone_black), 0, 1)
L = L ** (1 / tone_gamma)
darkening engraving intensity = 255 * L
lightening engraving intensity = 255 * (1 - L)
```

Black engraving pixels mean burn for both modes; white means no burn. Atkinson preserves explicit endpoints even with an extreme dither threshold; other modes apply their documented pattern semantics. Contain padding and fully transparent source pixels remain no-burn. Partial transparency composites onto the polarity's no-burn source endpoint. Shape-masked pixels are excluded by alpha. An intentional bitmap border remains burn content.

Combining an explicit material mode with legacy `--invert` is rejected. Curves require an explicit material mode; there are no automatically calibrated slate/glass profiles. Use `--contrast 1 --sharpen-radius 0 --no-clean-solids` when isolating the tonal curve for a ramp test. Gamma > 1 raises desired luminance; its effect on burn coverage depends on polarity.

## Reproducible maple preview and client proof

```bash
gf --input input/art.png -o output/review --circle-cut -w 4 -h 4 \
  --svg-operations --material-mode darkening --preview-finish \
  --preview-seed 17 --preview-spread-mm 0.05 \
  --proof-sheet --client 'Client name' --order 'Order reference'
```

`--preview-finish` writes `_finish.png`. `maple-v1` uses seeded procedural grain at 300 DPI and a caramel mark color. `--preview-spread-mm` is Gaussian blur radius in physical millimeters, bounded to 0–2 mm, applied only to the displayed burn coverage. The preview uses the union of primary artwork and requested text/QR masks on the original canvas, before optional lossless trimming. The PDF labels these sidecars as separate imports; the operations SVG embeds only the primary artwork. Tone layers cannot be combined with a finish preview or PDF because their material/operation assignments are not known. The preview preserves shape transparency. No preview pixels enter the engraving output.

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

Once the single pocket fits, add `--jig-rows 2 --jig-columns 3 --jig-gap 0.25`. The grid is bounded to 400 pockets and checked against the chosen nominal machine bed (accepting a jig canvas that fits when rotated, matching the artwork preflight). Gap is material remaining between finished pockets; negative clearances, impossible kerf, overlaps, and out-of-bounds layouts are rejected. Fractional pixel vector coordinates retain measured geometry. Manifest/workflow metadata records finished pocket sizes, compensated path sizes, canvas, centers, and artwork offsets in the same coordinate system.

1. Import the single SVG and check dimensions, groups, centers and operation assignments.
2. Ignore engraving. Cut the pockets (and optional orientation score) in jig stock.
3. Secure the jig; remove pocket waste and insert blanks. Do not move the jig or imported design.
4. Ignore cuts and score. Enable engraving and review focus/material settings for the blanks.
5. Measure fit and repeat placement with machine and stock recorded before production.

A circular pocket does not constrain rotation. Add a physical orientation stop or use a consistent mark for asymmetric art. This first version rejects text/QR, tone-layer and linework sidecars in jig jobs because they are not replicated. It does not implement keyed/double-sided jigs, nesting, or claims of measured placement accuracy. Margins are margins around the jig canvas, not a promised position relative to the physical machine origin.

## Trimming

```bash
gf --input input/art.png -o output/trim --no-border --trim --machine performance
```

`--trim` uses the union of all engraving-mask bounds, expanded to preserve any QR quiet zone. Primary, tone-layer, text and QR masks receive the same crop and recorded offset. Remaining pixels are unchanged. Its SVG keeps the original canvas, cutlines and placement offsets. The standalone PNG has smaller physical dimensions and loses placement context; use the SVG for registered placement. With no burn content across the entire job, PNG is a 1×1 white sentinel, SVG contains no engraving image, and metadata/CLI reports `NO ENGRAVE`. A blank primary with a text/QR sidecar is still an engraving job; its separate mask must be imported. Intentional bitmap borders count as content and prevent trimming unless explicitly disabled. Unified SVG/jig mode omits the old bitmap border because cuts have their own vectors.

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

CLI values override workflow recipe values. Python callers pass `WorkflowOptions(...)` as `workflow=` to `run_batch`. All new options are opt-in, and any active workflow automatically emits `_workflow.json` and the normal `_manifest.json`. Text, QR, tone-layer and linework jobs also require a manifest, even without an active workflow or with `--no-manifest`. The workflow configuration is part of the filename's recipe digest; use `--existing error` when preserving a prior source revision because the filename is not a source-content hash.

Dry-run lists every artifact and estimates memory for masks, preview/proof buffers, and repeated SVG images without creating files. Rendering resolves pixel-dependent trim bounds, previews, and sample validity. All artifacts participate in collision checks, existing-output policy, manifest verification, and [job recovery](handbook.md#recover-an-interrupted-publication). Missing or changed companions fail `--existing skip`. Failed PDF generation leaves the previous complete output set intact. Repeat the original prompt/model for reuse. Changing or clearing them requires explicit overwrite. Regenerate older sidecar sets that lack a manifest.

## Acceptance record

Software tests cover polarity ramps, no-burn padding and transparency, deterministic preview pixels, SVG structure, trim offsets, jig geometry, resource guards, blank jobs, revision binding, tamper rejection, and publication recovery. The October review record describes earlier visual PDF checks for one-page layout, embedded fonts, long or missing metadata, and portrait or landscape source panels. Record fresh visual results alongside the revision tested. See the [remediation record](review-remediation.md) and [first-burn checklist](first-burn-checklist.md).

**Glowforge app import and physical acceptance remain pending.** The September 25, 2026 browser check reached the owner sign-in page. Use the [case table](first-burn-checklist.md#app-import-no-burn) to record the actual size, registration, and operation assignments for each SVG you import. Record physical results against the same job when a measured sample is available.
