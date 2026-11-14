# Changelog

All notable changes to the `glowforge-it` project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased — 0.2.0rc2.dev1]

### Publication recovery

- Record a per-job journal before changing artifacts. Add `--recover-publication PATH` to preview or recover the previous generation after process interruption, with job-directory and hash checks. Recovery of a committed journal keeps the published generation and clears temporary files.
- Report post-commit cleanup as a successful job with the journal path. Require unresolved journals to be handled before planning or reusing output in that directory.
- Coordinate publication and recovery with a POSIX directory advisory lock. Recovery previews take a shared lock.
- Retain backups when a committed artifact is missing or changed. Recheck `--existing skip` and `--existing error` under the publication lock when a new output is expected.

### November review corrections

- Check case and Unicode aliases during source and output containment. Require an existing manifest-backed output to be reused or replaced with its manifest.
- Apply the same exact-export record validation to audition reuse and candidate selection. Give recovery and manifest verification explicit CLI option sets.
- Match rotated TIFF preflight and render geometry. Budget the expanded denoise canvas and filter scratch space. Preserve fully transparent areas as no-burn across renderers and material modes.
- Validate printable ASCII stamp text, UTF-8 QR payloads, SVG metadata characters, and recipe wrapper keys. Preserve isolated small marks in centerline traces.
- Add an executable quick start with synthetic source artwork, and include documentation, scripts, and test fixtures in the source archive.
- Keep manifest and audition source paths valid through output directory aliases. Reject special and symlink output files during planning. Return validation errors for oversized numeric recipe values.
- Generate and verify a fresh acceptance pack with legacy circle and heart, a unified trim comparison, PDF proof, and jig. Check expected documentation and fixtures in the distribution smoke script.
- Older manifests can still be checked as archives. Use their recorded engine/runtime for exact reuse or regenerate with the updated engine.

### Selected audition export

- Add `--export-audition PATH --candidate NAME_OR_NUMBER` and the Python `export_audition_candidate` entry point. Restore recorded source, original dimensions, resolved settings and polarity without reconstructing commands or copying recipes.
- Number sheet labels and record exact render arguments, source-relative paths and full-resolution pixel hashes. Validate source, contact sheet and engine identity, then compare rendered pixels before publication; always emit a production manifest and retain normal collision, resource, reuse and recovery checks.
- Leave audition files unchanged; reject rendering/sidecar overrides and explain when older records require regeneration. Add targeted selection and documentation coverage; broader software, distribution and app/physical gates remain open.

### October review corrections

- Preserve high-bit-depth PNG color-key transparency from original samples, including opaque shades that round to the same 8-bit gray; cover normalization and production/audition behavior across polarity modes.
- Keep manifest-verification failure reasons visible with quiet output while retaining silent success and structured JSON diagnostics.
- Materialize batch/audition input iterables as filesystem strings in shared planning; accept path objects, keep generators independent of logging, and retain source-tree protection and subfolder mirroring.
- Reject non-finite grayscale samples and constant images without a recognized scale before they can publish a misleading burn mask.
- Require manifests for text, QR, tone-layer and linework sidecars in planning and direct/batch export, even with `--no-manifest`; retain optional manifests for ordinary PNG and legacy cut-SVG jobs.
- Wrap audition headers and labels in consistent-width columns, and include their measured layout in memory preflight.
- Reject changed or cleared prompt/model provenance during manifest-backed skip; explicit overwrite records the new provenance.
- Validate direct-export settings before artifact-path expansion. Add focused regression coverage for all five follow-ups.

- Render production and audition jobs from stable source snapshots; reject changed inputs before publishing, and bind proofs/manifests to the rendered bytes.
- Preserve all tone layers and personalization in common trim bounds, including QR quiet zones. Pure-white pixels are no burn in every tone layer.
- Validate personalization against other engraving masks; include text/QR in simulated finishes, proofs and whole-job no-engrave status. Reject unsupported layer-preview and jig-sidecar combinations explicitly.
- Share artifact naming and resource contracts across planning and export; account for rotated halftone canvases, bounded tracing, glyph size, sidecars and audition sheets. Validate direct APIs and inferred settings before rendering.
- Report post-publication backup cleanup failures as successful writes with recoverable warnings.
- Return structured JSON for usage/validation failures; reject audition options whose artifacts are not represented and validate existing audition content before reuse.
- Distinguish archived hash verification from current-engine reuse, recording source fingerprint, Python and rendering-library versions. Add CLI manifest verification.
- Add clean wheel/sdist installation checks, an API migration guide and a tracked first-burn checklist; correct contradictory pipeline and feature documentation.
- The October 16 record at `35356d0` reports local full-suite and uv-based wheel/sdist checks for the remediation baseline. See [validation record](docs/review-remediation.md#validation-record) for the scope and open gates.
- Fix: stamp and QR rejection on circle/heart shapes now names the smallest margin that fits (the default corner positions cannot); 32-bit integer and float grayscale are scaled instead of clipped; argparse abbreviations are rejected so `--json` error handling cannot be bypassed; `--border` overrides a recipe's `no_border`; README states that plain `gf` runs get a recipe digest, not `dithered`.


### Maker workflow first versions

- **Breaking (pre-1.0 API cleanup):** `run_batch`, `prep_for_glowforge` and `transform_image` take a `ProcessingSettings` object instead of one keyword per option. `ProcessingSettings` fields now use the recipe/manifest spelling (`black_thresh`, `white_thresh`, `dither_thresh`, `denoise_radius`), so the alias layer is gone; recipes must use those keys and `material_thickness_in`. Removed `process_directory`, `output_geometry`, `write_svg_cut`, the `main.py` re-exports, and the `coaster`/`coaster-heart` presets (use `--circle-cut`/`--heart-cut`). Output names replace per-setting tags (`_b20_inv_nb`, `_prline-art`, `_mw…`) with one recipe digest (`_r<12 hex>`; all-default jobs keep `_dithered`), so existing outputs will not be matched by `--existing skip`. Removed `--optimize-orientation`, `--engraving-lpi` and `--orientation-constraint`. `gf` and `glowforge-it` now come only from the installed console scripts (`uv tool install -e .`); the repo `gf` wrapper and `install_alias.sh` are gone. ReportLab moved to the `proof` extra; QR encoding uses `segno`. Other CLI flags are unchanged. Audition now shares batch destination planning and returns `BatchResult`/`JobOutcome`: in `--audition --json`, `sheet_path`/`metadata_path` become `output_path`/`manifest_path` and the per-item `candidates` list is dropped (it remains in each `_audition.json`).
- Centralize processing defaults, validation, and serialization around `ProcessingSettings`; pass resolved settings through batch/export using the new signatures and canonical recipe keys described above. Share planning/proofing limits and path helpers, consolidate staging, and manage export image cleanup with `ExitStack`.
- Fix hatch burns on pure-white pixels and corner clipping in angled halftones. Omit repeated bitmap borders from exclusive tone layers. Require personalization to fit the usable shape and protect the full QR rectangle, including white modules and its quiet zone.
- Add `--audition` mode with full-resolution candidate rendering, labeled mode-agnostic contact sheets, physical-size/burn-coverage metadata, dry-run and existing-output handling.
- Add explicit `--render-mode silhouette` with a validated threshold, preserving the default Atkinson renderer and recording the selected mode in resolved recipes and output names.
- Add `ordered` Bayer and variable-cell `halftone` render modes with validated matrix/cell/angle parameters and binary output contracts.
- Add directional `hatch` and optional crosshatch rendering with validated spacing/angle parameters and binary output contracts.
- Add `edge` Sobel transition and `contour` tone-band render modes with validated thresholds/levels and binary output contracts.
- Add opt-in `_linework.svg` centerline-style sidecars generated by deterministic thinning/path tracing; keep them separate from cut paths and PNG burn artifacts.
- Add opt-in 2–4 layer registered exclusive tone-band PNG sidecars with manifest hashes and explicit layer roles; operation/material assignment remains owner-reviewed.
- Add collision-checked text and constrained version-1/L QR personalization sidecars (encoded with `segno`) with manifest roles and placement records; payloads never merge into the primary PNG implicitly.
- Add opt-in `--svg-operations` with red cuts, blue orientation scores and embedded engraving; retain legacy blue-cut defaults pending app acceptance.
- Add explicit darkening/lightening modes and versioned levels/gamma curves with no-burn padding/transparency.
- Add seeded maple finish previews and one-page approval PDFs with embedded font, revision identity and printable sign-off fields. ReportLab is an optional `proof` extra; `--proof-sheet` fails preflight with an install hint when it is missing.
- Add measured rectangular/circular pocket jigs and regular grids, shared artwork/pocket coordinates, per-side clearance and full-kerf compensation.
- Add burn-bounds trimming with placement-preserving SVGs and explicit empty-mask results.
- Include every new artifact in planning, memory estimates, existing-file policy, manifest verification and recoverable publication. Add synthetic review generator and targeted acceptance coverage.
- Glowforge import, physical fit and finish, and measured timing acceptance remain pending.

### Fixed
- A preset inferred from a `*--<preset>.<ext>` filename no longer overwrites recipe or CLI values; it fills only settings you did not set and that are still at their defaults. An explicit value that equals the default (`--contrast 1.5`, `-b 0`, `--no-clean-solids`) is now honored too: the CLI passes its explicit keys to `run_batch(explicit_keys=...)`. API callers that omit it get the default-only rule.
- `--audition` validation failures (for example combining it with `--trim`) exited 2 with no message; they now print `Validation error: ...` to stderr, and audition's other error lines moved from stdout to stderr like the batch path.
- `--fit stretch` with both dimensions now warns (stderr, and a `warnings` list on the job in `--json`) when it changes the artwork's proportions by more than 2%. The default stays `stretch`.
- `--svg-linework` fails with an explanatory message when tracing yields more than 50,000 paths (dot, halftone or textured art produced 17 MB SVGs with 300,000+ paths); `render_centerline_svg(max_paths=...)` raises the ceiling. The failed job publishes nothing.
- The SVG cut circle (`--svg-cut` and `--svg-operations`) is now registered to the raster mask: it was 0.5 px (0.04 mm) off-center and 1 px smaller in diameter. Circle and heart registration is asserted against the raster mask to 0.3 px (0.001 in).
- The package version is defined once, in `glowforge_it/settings.py`; `pyproject.toml` reads it.
- Jobs using any maker-workflow option no longer fail when the optional `reportlab` package is not installed; its version is recorded as `null` in `_workflow.json`. Only `--proof-sheet` requires it.
- Manifests written for workflow jobs keep the `role` of linework, tone-layer, stamp and QR outputs.
- The `gf` command's clean-solids default now ranks below presets and recipes (`clean_solids = false` in a recipe is honored); `--no-clean-solids` still works.
- Added help text for the maker-workflow options in `--help`. Documented `--quiet`; corrected the README `--tone-layers` table row; refreshed stale "CLI cannot do text/QR/settings sidecars" entries in the 101 ideas list.
- 16-bit grayscale PNG/TIFF sources are scaled to 8-bit instead of clipped: Pillow's `convert('L')` turned almost the whole image white (a mid-gray ramp burned 0.4% instead of 50%) with no warning. The proof sheet's source panel had the same problem.
- Published files now get the normal umask mode (typically 0644). They were created owner-only (0600) by the temp-file staging step.
- A recipe's `preset` is treated like `--preset`: it is no longer mixed with a preset inferred from the filename, and the manifest records the recipe's preset. The recipe file is also read once per run instead of three times.
- `--stamp-text` rejects characters the built-in font cannot draw. Pillow's bundled font is ASCII only, so accented Latin (`José`), Cyrillic, CJK and emoji were engraved as identical empty boxes.
- A failed attempt to move an existing output aside during publication no longer leaves a stray `.gf-prev-*` file.

### Planned
- **Stage 3 (Visual Proofing)**: 1:1 pixel inspection viewer, crop anchors and framing guides remain. CLI audition contact sheets and direct candidate export are available. See [roadmap.md](roadmap.md).

---

## [0.2.0rc1] - 2026-09-25

### Release Candidate 1 (Makerspace Trial)
- **Controlled First-User & First-Machine Validation**: Prepares reproducible CLI, typed validation, structured manifests, and cut sidecars for offline and on-machine verification prior to final `v0.2.0`.
- **Packaging Alignment**: Package metadata and CLI version set to `0.2.0rc1` (Git tag `v0.2.0-rc.1`).

### Added
- **Shared Typed Validation (2A)**: Implemented `ProcessingSettings.validate(...)` enforcing identical configuration invariants across both CLI commands and direct Python API invocations (`run_batch` / `process_directory`).
- **Structured Batch Outcomes & JSON (2A)**: Added `BatchResult` and `JobOutcome` dataclasses providing per-item status (`written`, `skipped`, `failed`), error categorization, execution timings, and dictionary/JSON serialization. Preserved full backwards-compatible boolean evaluation on `run_batch`. Added `--json` CLI flag for script pipelines.
- **Side-Effect-Free Dry Run (2B)**: Added `--dry-run` flag to preview planned destination paths, physical dimensions, and memory requirements with zero disk mutations (no directory creation, no filesystem case-folding probe files written).
- **Versioned Job Manifests (2C)**: Added `--manifest` flag to emit companion versioned JSON job manifests (`schema_version: "1.0"`) capturing source SHA-256, output SHA-256 hashes, physical dimensions, resolved recipe parameters, and optional AI prompt/model provenance. Manifests are staged and published with image/SVG files, with rollback on publication failure; this is not a crash-proof transaction.
- **Manifest Verification (2D)**: Added `verify_job_manifest(...)` to detect changed source images or modified output files against their recorded hashes. Automatic replay and immutable revisions remain future work.
- **Memory Budget & Resource Preflight (2E)**: Added `estimate_image_memory(...)` and `--max-memory` budget limits (supporting strings like `500MB`, `1GB`) to reject over-budget jobs during planning before allocating heavy image buffers.
- **User Recipe Profiles (2F)**: Added `load_recipe_file(...)` and `--recipe` CLI flag supporting custom `.toml` and `.json` configuration profiles with strict schema validation and precedence rules (`defaults -> preset -> recipe -> explicit overrides`).
- **Packaging & Console Script (2G)**: Added standard `pyproject.toml` configuration declaring console entry points (`glowforge-it`, `gf`), version declaration (`0.2.0rc1`), separated runtime and test dependencies, and added `--version` CLI flag.

### Fixed
- **Trial preflight and reuse**: PNG metadata inspection now skips pixel data, including when EXIF/XMP follows IDAT. Shared memory estimates cover simultaneous float64 dither arrays and padding. Dry-run results expose sizes and memory; blocked destination roots fail before rendering. Manifest validation returns errors for malformed records and unreadable files, resolves source paths relative to the manifest, and verifies hashes/recipe before manifest-backed skip. Direct API validation includes batch-level options; unknown recipe presets fail explicitly. Installed `gf` now matches the wrapper's clean-solids default.
- **EXIF-Oriented Memory Estimation (P1)**: Extracted `get_oriented_dimensions` and `resolve_target_dimensions` in [geometry.py](glowforge_it/geometry.py) to resolve header-level EXIF rotation tags prior to pixel decoding, ensuring estimation, planning, and rendering share identical geometry without memory budget bypass on rotated photographs.
- **Zero-Decode Budget Preflight (P2)**: Moved `max_memory` verification in `plan_batch` ahead of pixel decoding and avoided `ImageOps.exif_transpose` during planning/dry-runs.
- **Strict Manifest Verification (P2)**: Hardened `verify_job_manifest` to reject empty or missing schema definitions, require valid source and output records with hashes, detect unresolvable sources, and verify explicit source paths unconditionally.
- **Recipe Sidecar & Material CLI Support (P2)**: Included `svg_cut`, `manifest`, `material`, and `material_thickness_in` in `ProcessingSettings` and `resolve_settings`, setting CLI argument parser defaults to `None` so recipe-requested sidecars and materials are honored instead of silently dropped.
- **Strict Shared Type & Finiteness Validation (P2)**: Updated `ProcessingSettings.validate()` to strictly verify boolean types, reject boolean values on integer fields, and assert finite numeric values (rejecting `NaN` / `Inf`) before range comparisons.

---

## [Stage 1.5: Modular Monolith Extraction] - 2026-09-25

### Architecture & Modularization
- **Package Decomposition**: Extracted monolithic `main.py` (1,298 lines) into the structured [glowforge_it/](glowforge_it) package:
  - [settings.py](glowforge_it/settings.py): Defaults, presets, and `ProcessingSettings` resolution.
  - [geometry.py](glowforge_it/geometry.py): Circle and heart cut geometry, bed preflight, and physical sizing.
  - [imaging.py](glowforge_it/imaging.py): Pure image-to-image pipeline (orientation, normalization, tone adjustments, Atkinson dithering, and shape masks).
  - [publication.py](glowforge_it/publication.py): Atomic sibling staging, file replacement, rollback, and `RecoveryError`.
  - [export.py](glowforge_it/export.py): Raster PNG and SVG sidecar document generation.
  - [planning.py](glowforge_it/planning.py): Source discovery, destination namespace, path containment, and `PlannedJob`.
  - [batch.py](glowforge_it/batch.py): Plan execution and batch outcome reporting.
  - [cli.py](glowforge_it/cli.py): CLI argument parsing and input validation.
- **Compatibility Launcher**: Retained [main.py](main.py) as a 71-line wrapper with inline `uv` dependency metadata and public API re-exports, preserving `./gf`, direct python execution, and external script invocations.
- **Strict AST Architecture Guard**: Added [tests/test_compat.py](tests/test_compat.py) to statically enforce one-way layer dependencies (`cli -> batch -> planning/export -> imaging/publication -> geometry -> settings`) and prevent circular imports.
- **Modular Test Suites**: Reorganized tests into 6 focused test files under [tests/](tests) using shared helpers in [tests/helpers.py](tests/helpers.py) (56 tests passing across Python 3.11–3.13, default, and `importlib` import modes).
- **Parity Baseline Verification**: Confirmed exact behavioral parity against an 87-value extraction baseline covering pixel output hashes, SVG geometry, sizing suffixes, error codes, and batch naming.

---

## [Stage 1: Engine Hardening & Bug Fixes] - 2026-09-25

### Fixed (Review Findings F01–F12 & Independent Follow-up)
- **Source Protection & Pre-Flight Planning (F01)**: Implemented complete batch planning before any files are written. Resolved path and filesystem inode checks prevent destination files from overwriting source files, including symlinks and hard links.
- **Case-Insensitive Collision Protection (F02)**: Added runtime case-folding detection for filesystems like macOS APFS. Destination paths are normalized (Unicode NFC + casefold) to catch collisions prior to writing.
- **Symlink & Input Containment (F03 & Follow-up)**: Enforced destination containment checks against both the output root and all selected input roots. Prevents destination directories from escaping or nesting into source trees.
- **File/Directory Conflict Detection**: Added pre-flight planning checks for destination file/directory collisions, preventing partial batch failures caused by existing path conflicts.
- **Atomic Publication & Recovery Rollback (F04 & Follow-up)**: Output files stage to temporary sibling files (`.gf-*`) with pre-publication backups (`.gf-prev-*`). Ordinary errors trigger independent rollbacks for all written files. Unrecoverable files raise `RecoveryError` with an intact destination-to-backup map.
- **Bounded Memory Resampling (F05 & Follow-up)**: Rewrote `--fit cover` to resample directly from a cropped source box via Pillow `Image.resize(box=...)`, preventing multi-gigabyte memory allocations on extreme aspect ratios.
- **Comprehensive Transparency Normalization (F06)**: Implemented full compositing over solid white for RGBA, LA, PA, and color-key `tRNS` transparency across RGB, L, and palette images.
- **Structured Traversal & Output Errors (F07)**: Captured directory creation and `os.walk` traversal errors into structured batch errors with deterministic exit codes.
- **Explicit Preset Ablation (F08)**: Allowed explicitly disabling preset stages via `--denoise 0`, `--sharpen-radius 0`, or `--sharpen-percent 0`.
- **Post-Dither Contain Padding (F09 & Follow-up)**: Changed `--fit contain` to process and dither artwork before laying it onto a white canvas. Prevents inversion and error diffusion from corrupting padding margins.
- **Documentation & Semantic Accuracy (F10)**: Corrected erroneous claims regarding error diffusion, mirroring vs inversion, stamp order, and burn colors across user guides.
- **Onboarding & CWD Semantics (F11)**: Clarified `./gf` launch instructions, explicit current-working-directory semantics, and zsh-only installer script details.
- **Negative-Path Test Suite & CI (F12)**: Added 12 regression tests covering failure paths and edge cases. Protected golden fixtures (`GF_UPDATE_GOLDEN=1` required to rewrite) and added macOS to GitHub Actions CI.

---

## [Initial Prototype] - 2026-09-24

### Added
- Core image transformation pipeline converting raster artwork into 1-bit Atkinson dithered PNGs.
- Presets: `photo-soft`, `photo-high-detail`, `illustration`, `line-art`, `high-contrast`, `stamp`, `sketch`, `dark-surface` (`illustration` and `dark-surface` are not in the current preset list).
- Fit modes: `stretch`, `contain`, `cover` at fixed 300 DPI.
- Sizing options: width, height, max dimension, and scale multiplier (max dimension and scale multiplier are not in the current CLI).
- Circular and heart mask cutouts with optional SVG sidecar generation containing cut outlines.
- Recursive input directory traversal and batch output mirroring.
