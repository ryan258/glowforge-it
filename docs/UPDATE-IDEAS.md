# Project Review and Enhancement Roadmap

This document records the current product boundary, the corrections made in each dated pass (see the status log below), and a sequenced proposal for turning the repository into a dependable production tool for Glowforge artists and makerspace professionals. “High value” below means it improves correctness, confidence, repeatability, or creative range; it does not mean the feature has been validated by customers or a live machine.

## 1. Current project, from zero to hero

### What it is today

`glowforge-it` is a local Python CLI that prepares raster artwork for engraving. The current command flow is:

1. `gf` wrapper runs `uv run main.py` and adds `--clean-solids`. `main.py` is now a compatibility launcher: it carries the inline `uv` dependency metadata and re-exports the package surface.
2. `glowforge_it.cli` parses paths, a preset, and explicit option overrides. Defaults resolve first, preset values replace matching defaults, and explicit CLI options win.
3. `transform_image` applies EXIF orientation, composites transparency over white, converts to grayscale, optionally median-filters and resizes, applies invert/solid snapping/thresholds/contrast/unsharp masking, and runs Atkinson error diffusion.
4. The result gets a bitmap border, circle mask, or heart mask; the writer stores a 300-DPI PNG. Optional `--svg-cut` writes a sidecar with an embedded raster and vector outline.
5. `glowforge_it.planning` walks supported formats in sorted order, mirrors subfolders, builds filenames, applies size/machine preflight, checks path protection and the destination namespace, and manages existing output paths. `glowforge_it.batch` then executes the validated plan.

`ProcessingSettings` centralizes resolved CLI settings before passing compatibility keyword arguments into the processing functions. This removes repeated precedence logic, though options are still expanded through several long signatures — a typed shared settings object is E15 and is not done.

As of the 2026-09-25 modularization the implementation lives in a package beside the launcher:

```text
glowforge_it/
  settings.py     defaults, presets, ProcessingSettings, resolve_settings
  geometry.py     circle/heart outlines, sizing and machine preflight
  imaging.py      normalize, tone, fit, dither, masks (image in, image out)
  publication.py  staging, replacement, rollback, RecoveryError
  export.py       PNG/SVG rendering and one image's output set
  planning.py     discovery, identities, destination namespace, path protection
  batch.py        execute a validated plan, aggregate the outcome
  cli.py          argument parsing, CLI validation, entry point
```

Imports run one way only — `cli -> batch -> planning/export -> imaging/publication -> geometry -> settings` — and `tests/test_compat.py` fails if a module ever imports something at or above its own layer. `main.py` keeps the `uv` script metadata and re-exports the public names, so `gf`, existing tests and review probes are unaffected.

This was a behavior-preserving extraction: an 87-value baseline (output pixel hashes across 18 option combinations, shape geometry, SVG documents, sizing suffixes and preflight errors, batch filenames, published file hashes, failure-path exit codes and parser rejections) is identical before and after. No signatures changed and `run_batch` still returns a boolean.

### Product target and boundary

The default project stock context is **medium maple plywood at 1/8 inch**. `--material` and `--material-thickness` change only the descriptive batch log; the latter accepts fractions such as `1/4`. These values are not an image recipe, machine profile, safety check, or power/speed setting. Verify the exact local sheet label and measured thickness. Glowforge’s Proofgrade maple listing calls Medium approximately 1/8 inch and Thick approximately 1/4 inch; makerspace naming may differ ([Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished)). The supplier and makerspace remain authoritative for stock compatibility and operation settings.

This utility prepares artwork; Glowforge’s app controls the print steps and laser settings. PNG is a raster image; the optional SVG mixes an embedded raster with an outline vector. Glowforge documentation describes raster images as engrave content and vectors as cut/score-capable, but actual sidecar import, alignment, and operation assignment still need to be demonstrated on the makerspace machine ([uploading designs](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [vector stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes)).

### Current strengths

- Explicit presets and one-off controls for contrast, thresholds, denoise, sharpening, inversion, size, and cutout masks.
- EXIF orientation handling; transparent image compositing; PNG, JPEG, BMP, WebP, TIFF, and GIF input.
- Atkinson dithering and deterministic output naming for the same settings.
- Optional approximate machine-area check and per-image pixel guard.
- Output-path protection against writing a folder’s results back into that input folder.
- Temporary sibling files and rename for individual output writes; skip/error/overwrite policy for existing output sets.
- Optional circle/heart vector-outline SVG sidecar.
- Dependency pins in inline script metadata and `requirements.txt`; CI matrix starts at Python 3.11.
- User-facing README, handbook, command examples, ELI5 guide, idea list, and AI image prompts.

### Current limitations and risks

- Presets have not been measured against a controlled set of this makerspace’s maple sheets, Glowforge models, engraving modes, or approved stock settings. They describe pixels only.
- The current SVG sidecar is not yet confirmed in the actual Glowforge app. Its PNG/SVG pair is written as two individually atomic files, not one transaction; an error between writes can leave a partial pair.
- `--machine` uses nominal dimensions and allows rotation. Real usable area can shrink with operation/settings, and the approximate check does not add an explicit edge margin. The app is authoritative ([printable-area guidance](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area)).
- Output filenames encode image settings but not source content, the `--material` label, app settings, or code version. Matching names can be overwritten by default.
- `--fit contain` and `cover` only matter when both dimensions are set. The default `stretch` can distort a non-matching aspect ratio.
- The standard PNG is 1-bit; circle/heart PNG requires RGBA transparency. Animated GIFs use the first frame. HEIC is not supported.
- Batch processing writes one output per source image; it does not nest, tile, make a contact sheet, generate text or QR artwork, create a material test card, or split passthrough jobs.
- The CLI is primarily for command-line users. It has no interactive preview, local GUI, custom preset file, watch mode, installer package, or settings replay.
- Existing tests and CI configuration are present. As of the 2026-09-25 pass the suite runs clean on macOS/Python 3.13; Glowforge app import has still never been verified.

## 1b. Status log

### 2026-09-25 — Stage 1, trustworthy engine (F01–F12 from the project review)

Done. **Superseded in part by the follow-up entry below** — read both. F01–F09 each have a
regression test that fails against `674eb11` and passes now; F10–F12 are documentation,
fixture and CI changes verified by inspection. The F03, F04 and F09 rows below describe the
first attempt; the follow-up entry records the gaps an independent review found in them.

| ID | Status | Change |
|---|---|---|
| F01 | done | `plan_batch` resolves every source and destination before any write; a destination matching a source's resolved path or inode (symlink or hard link) aborts the batch. |
| F02 | done | Destination namespace is keyed by NFC + casefold when the output filesystem folds case, probed at runtime. Ambiguous destinations fail before publication. |
| F03 | done | Every destination folder must resolve inside the output root, so a symlinked subfolder cannot redirect writes into the source tree. |
| F04 | done | `publish_generation` moves the previous files aside, replaces all destinations, and attempts to restore each one if any destination fails. Recovery itself can fail; see the follow-up entry and `RecoveryError`. Rollback, not a crash-proof transaction — see E02/E10. |
| F05 | done | `--fit cover` resamples straight from a source crop via `Image.resize(box=...)`; no oversized intermediate. |
| F06 | done | Colour-key `tRNS` on RGB and L sources now composites to white alongside RGBA/LA/PA and palette alpha. |
| F07 | done | Output-root creation and `os.walk` failures are structured batch errors with a deterministic exit status. |
| F08 | done | `--denoise 0`, `--sharpen-radius 0` and `--sharpen-percent 0` explicitly disable those stages, so preset ablation works. |
| F09 | done | Inversion runs before layout, so `--fit contain` padding is always white. Documented as a layout background, not artwork. |
| F10 | done | Corrected the no-dither, mirror-vs-invert, stamp-order and burn-colour claims in the handbook, README, 101-ideas and best-commands guides. |
| F11 | done | README quick start runs from a clean checkout with `./gf`; cwd semantics stated in README, `gf` and `install_alias.sh`; installer states it is zsh-only. |
| F12 | done | 12 negative-path regressions added; the golden fixture is never rewritten by a test run (`GF_UPDATE_GOLDEN=1` regenerates it); CI matrix adds macOS. |

### 2026-09-25 — Stage 1 follow-up, from the independent review

An independent review of the pass above found four behavioural gaps the green suite did not
cover, plus two weak tests. All six are closed; each was reproduced first.

| Finding | Status | Change |
|---|---|---|
| Destination could still enter an input tree when the input sits *under* the output root (P1) | done | Every resolved destination folder is now checked against all selected input directories as well as the output root. The symlink arrangement `out/nested -> out/source/nested` with input `out/source` exited 0 and wrote into the source tree; it now exits 1 and writes nothing. |
| File/directory conflicts survived planning (P2) | done | Required output directories are part of the plan. An output file that another job needs as a folder, or an existing non-directory on a destination path, is a planning error. Previously this published one of two outputs and then failed. |
| `contain` padding still became engraving pixels (P2) | done | Padding is laid down *after* dithering rather than before tonal processing, so contrast, thresholds, sharpening and error diffusion cannot reach it. The probe case (white source, invert, contrast 0.5) went from 3,184 black padding pixels to 0. |
| One failed restoration abandoned the rest (P2) | done | Recovery now attempts every file independently, keeps the backups it could not restore, and raises `RecoveryError` carrying a destination→backup map plus the original publication error. |
| F04 tests never reached the rollback path | done | Added injected-failure tests that fail the *second* publication and assert the exact previous bytes, plus an incomplete-recovery test. The directory-preflight tests are retained. |
| F05 test performed the allocation it guards | done | The resize spy asserts the budget before delegating to Pillow, so a regression reports rather than allocating 6,000,000 × 300. |

Acceptance-note corrections from the same review:

- F05's extreme-aspect-ratio CLI case **exits 0** with one bounded output. An earlier note
  claiming all reproduction scenarios now exit 1 was wrong for F05.
- The added regressions target F01–F09 individually. F10–F12 are documentation, fixture and
  CI changes, verified by inspection and by the suite running clean, not by one test each.
- `run_batch` still returns a boolean and prints a summary line. A structured per-item result
  is E14 and is not done.
- Planning does create the output directory and a temporary case-probe file inside it. The
  guarantee is "no image outputs were published", which is what the message now says.

Not started: E10–E56 (job manifests, replay, dry-run, packaging, visual proofing, physical evidence, UI, agent adapter, production expansion). Nothing in either pass touched hardware, the Glowforge app, or any network service.

### 2026-09-25 — Stage 1.5, modularization

Behavior-preserving extraction of `main.py` (1,298 lines) into the `glowforge_it/` package
described in section 1. No Stage 2 features, no signature changes, no new `BatchResult`.

| Exit criterion | Evidence |
|---|---|
| Launch commands and cwd semantics intact | `./gf` from an unrelated directory still resolves `input/`/`output/` against the caller's cwd and applies the wrapper's `--clean-solids`; `python main.py` runs as a script; the `uv` script metadata is unchanged and asserted by a test |
| Targeted checks pass per module | 56 tests across `test_imaging` (13), `test_planning` (16), `test_cli` (16), `test_export` (3), `test_publication` (3), `test_compat` (5) |
| Review probes produce the same outcomes | The independent Stage 1 probe script returns the identical corrected results |
| Clear responsibilities, no circular imports | One-way layering, enforced by a test rather than a convention |
| No unrelated behavioral change | An 87-value extraction baseline is identical before and after |

Deferred on purpose: `dither.py` stays inside `imaging.py` until there is more than one
algorithm (E23); presets stay in `settings.py`; packaging and a `src/` layout stay with E16.

## 2. Corrections and foundations in earlier implementation passes

| Area | Change | Remaining acceptance evidence |
| --- | --- | --- |
| CLI architecture | Added `ProcessingSettings` resolution for defaults → preset → explicit overrides and exposed the new options through the CLI. | Targeted CLI tests for precedence, flags, invalid combinations, and wrapper overrides. |
| Fit and sizing | Added `stretch`, `contain`, and `cover`; EXIF-oriented geometry, source/output pixel guards, nominal machine-area checks, and more precise dimension suffixes. | Verify physical size and fit behavior with representative images and app import. |
| Dither memory | Replaced the expanded Python float lists with packed numeric storage and changed pre-dither threshold storage to 8-bit integers. | Measure peak memory and output equivalence on small, full-bed, and high-detail artwork. |
| Output handling | Added temporary-file replacement, output-directory self-ingestion protection, supported WebP/TIFF/GIF inputs, and overwrite/skip/error policies. | Test permissions, corrupt inputs, duplicate names, symlinks, interruption, and partial SVG pairs. |
| Shape output | Shared circle/heart geometry with an optional SVG containing raster art and a vector outline. | Import the sidecar into the actual Glowforge app, check positioning/size and operation assignments, and run a supervised proof only after stock approval. |
| Documentation | Replaced unsupported claims about kerf compensation, guaranteed burns, auto-cuts, and complete project generation; documented default material context and CLI limits. | Review all public examples when CLI options or material assumptions change. |

## 3. Priority plan

### P0 — Prove the real production path

1. **Validate SVG import and operation assignment.** On the target makerspace machine, import a generated circle and heart sidecar. Record whether the PNG and vector path stay aligned and how the app classifies them. Adjust the SVG structure if the app drops or rescales embedded raster content. Do not treat an SVG file or successful upload as evidence of a safe cut.
2. **Build a makerspace material acceptance card.** Confirm the actual maple stock name, supplier, measured thickness, core/adhesive documentation, machine model, and operator-approved material profile. The image tool must not invent power/speed values. Only publish profiles after supervised testing and approval.
3. **Close output-pair failure paths.** Stage PNG and SVG together, preflight both destinations, and recover cleanly if either write/replace fails. Do not leave a stale SVG that looks paired with a newly replaced PNG. Add recovery instructions for partial output sets.
4. **Test the destructive and failure paths.** Add focused tests for overwrite/skip/error, duplicate output paths, unsupported/corrupt images, source/output pixel limits, invalid dimensions, SVG requirements, and rollback/cleanup. Keep tests scoped and include pixel-level checks of geometry and fit modes.
5. **Add release evidence.** CI should report Python versions, dependency pins, and focused test results. Keep app/device/material evidence explicitly separate from CI; a green test run cannot prove a burn or a material is safe.

### P1 — Make work reproducible and easier to judge

6. **Settings manifest.** Write an adjacent JSON record with normalized resolved settings, preset, material label, original and oriented dimensions, output dimensions, input SHA-256, application version/commit, and output filenames. Exclude absolute user paths by default. Write atomically and provide a replay command only after schema versioning and validation exist.
7. **Visual preset audition.** Add `--preview` or `--audition` to produce labeled small previews for chosen presets/thresholds. Make the preview watermarked as a preview and do not present it as a machine simulation. Preserve a direct path to the exact full-resolution output selected.
8. **Material test-card generator.** Generate artwork-only grids, grayscale ramps, line-width targets, and size labels. The app/operator applies approved machine settings to the cells. Include stock/model/settings note fields and a blank for measured result; never infer power/speed from the PNG.
9. **Batch summary and diagnostics.** Report counts processed/skipped/failed, elapsed time, destination and failed filename/reason. Add `--quiet` and structured/JSON summary output for scripted workflows. Avoid dumping giant arrays or continuing after unsafe preflight errors.
10. **Safe output mode.** Offer `--existing error` as an opt-in documented production choice (and consider making it the default in a future major version). Add a preview/dry-run that reports planned paths, sizes, material label, and machine-area checks without writing images.
11. **Crop and framing controls.** Add an explicit crop anchor/subject-safe fit, transparent-margin trim, and center-of-interest offset. Keep current stretch/contain/cover semantics, and show crop guides in preview to avoid silently removing faces or text.
12. **Improve type and error boundaries.** Separate argument/preset validation, image transform, geometry, SVG rendering, and batch I/O into modules once the CLI grows. Use stable error categories for unsupported file, decode failure, image too large, invalid settings, output collision, and write failure.

### P2 — Expand creative and production capability

13. **Dithering choices.** Add a `--dither` selector for current Atkinson, Floyd–Steinberg, ordered/Bayer, and plain threshold. Document how each pattern differs and preserve deterministic output. Keep black/white output policy explicit.
14. **Halftone screens.** Add adjustable cell size and angle for variable-radius dot screens. Provide preview examples because an attractive on-screen pattern may close up at small physical sizes.
15. **Hatch and engraving textures.** Add horizontal/diagonal/crosshatch options that map luminance to line spacing or density. Reuse shared grayscale and output stages; test aliasing and small-detail loss.
16. **Photo to line-art modes.** Offer edge extraction/sketch conversion with tunable levels, preview, and a clear separation between generated source art and final threshold/dither settings.
17. **Tone controls.** Add optional autocontrast, histogram equalization, gamma, and levels/curves. Keep these as mutually understandable steps with observable before/after previews; do not silently alter presets.
18. **Grayscale engraving mode.** Allow a cleaned grayscale PNG output for workflows where the app supports variable-power raster engraving. Make output mode explicit in filenames and metadata; verify on the actual machine before documenting how to assign the step.
19. **Layered tone separation.** Export two or three registered raster layers for distinct material or print steps. Require explicit registration marks and document manual step assignment; avoid claiming automatic multi-power behavior.
20. **Generalized cut shapes.** Add regular polygon, oval, rounded rectangle, star, and scalloped geometry via a shared path interface. Keep geometry shared between masks and vectors; validate bounds and centers at odd/even dimensions.
21. **Custom shape files.** Accept a user-supplied vector path or mask. Prefer a real vector-tracing pipeline or direct SVG geometry over a naïve raster edge detector, which can produce doubled/jagged contours. Always provide an outline preview.
22. **Holes and tabs.** Add vector hang holes and optional holding tabs with dimension units, min-wall checks, and SVG output. Require the maker to review the final cut path and kerf fit.
23. **Score and engrave layers.** Emit separate editable vector groups/colors for outline, holes, score marks, and raster art. Let the app/operator assign operations; do not hard-code undocumented color-to-operation assumptions.
24. **Kerf offsets.** Add real path-offset geometry with a measured kerf value, rather than scaling around a centroid. Show nominal and compensated dimensions and make the feature opt-in.
25. **Sheet layout and nesting.** Arrange identical or mixed pieces with user-entered stock dimensions, margins, gaps, grain direction, and rotation rules. Prevent overlap and report bounds. Export editable vectors and a preview; never assume the whole nominal bed is available.
26. **Long-job segmentation.** Add explicit slicing for compatible passthrough workflows with registration overlap and page labels. Keep the feature model-specific and require app review; a tall canvas alone is not a segmented job.
27. **More source formats.** Consider HEIC/HEIF as an optional extra dependency. Improve animated image handling by warning that only the first frame is used or asking which frame to extract. Preserve EXIF/color-profile behavior in documentation.

### P3 — Broaden access and daily workflow

28. **Local preview UI.** Build a local-only interface after the transformation API stabilizes: drag in a photo, compare before/after, adjust key settings, inspect dimensions and crop, then export. Do not upload source art to a service unless users explicitly request that behavior.
29. **User preset files.** Load validated TOML profiles for image parameters. Name profiles by use and stock only as human metadata; keep machine power/speed outside this CLI unless an owner-approved integration is designed.
30. **Watch mode.** Reprocess new files from one explicit input folder to a separate output folder. Add debounce, duplicate handling, visible state, and a stop/recovery path.
31. **Package installation.** Add `pyproject.toml` and a stable `gf` entry point, test installation in a clean environment, and retain the wrapper for repository users until migration is complete.
32. **Personalization overlays.** Support text, dates, and simple vector shapes with installed-font discovery, font licensing notes, and a fit/overflow preview. Keep text as editable vector where possible.
33. **Business workflow aids.** Add reusable job folders or project manifests for source proof, approved art, material note, output hashes, and customer revision tracking. Keep customer personal data local and opt-in.
34. **Accessibility and language.** Improve CLI help, error messages, keyboard access in any future UI, and examples for first-time makers. Any tactile/Braille product workflow requires a qualified standards-based process; image contrast alone is not accessibility.

## 4. Creative feature catalog

The numbered proposals above replace earlier shorthand items. This section maps the initial idea inventory into coherent feature groups so future work can be estimated and sequenced:

| Group | Proposal | Practical solution |
| --- | --- | --- |
| Artistic output | Alternate dithers, halftone, hatch, sketch/edge extraction, autocontrast/equalize, gamma, grayscale mode, layered tones | Add behind explicit flags, show visual samples, write metadata, and retain deterministic output. |
| Shapes and paths | More shapes, custom mask/path, holes, tabs, score groups, kerf offsets | Share one vector geometry model between preview and SVG; validate output bounds and operation assignment in the app. |
| Production | Nesting, contact sheets, test cards, segmentation | Build previews and dimensions first; treat bed capacity/settings as user/operator inputs. |
| Workflow | Settings sidecar, custom presets, watch mode, summary output, packaging, captions | Use versioned schemas, atomic files, local processing, predictable recovery, and accessible command-line and preview flows. |
| Input and framing | HEIC, animation frame choice, cropping/subject anchor, background removal | Keep optional dependencies optional; preview before destructive crop/removal and never imply AI output is exact. |

## 5. Sequencing recommendation

1. Complete focused CLI and failure-path checks for this implementation and confirm no unrelated Git changes were overwritten.
2. Validate SVG rendering/import on the actual machine and document the approved maple stock identity and workflow.
3. Add output-pair recovery, dry-run/preview, and settings manifest.
4. Build contact-sheet audition and material test-card tools so makers can choose image processing and record their own physical results.
5. Add alternate dither styles and generalized shapes based on real maker feedback.
6. Add nesting, local UI, personalization, and packaging after output contracts and manifests stabilize.
7. Revisit cloud or AI services only if local workflows show a clear need, with explicit privacy and cost choices.

## 6. Explicit non-goals for the current architecture

- Do not write G-code or directly control the Glowforge. The supported boundary is a design file reviewed in the vendor app.
- Do not turn an image preset into a power/speed recipe without model-specific, material-specific, supervised evidence and makerspace approval.
- Do not make sales, safety, cut-through, or quality guarantees from a prepared PNG or passing CI checks.
- Do not ship cloud AI background removal or remote previews by default. User artwork and client photos should stay local unless the user knowingly opts in.
- Do not build a plugin API before configuration and a second real extension need exist.
