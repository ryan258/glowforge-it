# Changelog

## Unreleased - Maker workflow first versions

- Add opt-in `--svg-operations` with red cuts, blue orientation scores and embedded engraving; retain legacy blue-cut defaults pending app acceptance.
- Add explicit darkening/lightening modes and versioned levels/gamma curves with no-burn padding/transparency.
- Add seeded maple finish previews and one-page approval PDFs with embedded font, revision identity and printable sign-off fields. Add ReportLab as a runtime dependency.
- Add measured rectangular/circular pocket jigs and regular grids, shared artwork/pocket coordinates, per-side clearance and full-kerf compensation.
- Add burn-bounds trimming with placement-preserving SVGs, explicit empty-mask results, and constrained 0/90-degree scan-row advice using supplied engraving LPI.
- Include every new artifact in planning, memory estimates, existing-file policy, manifest verification and recoverable publication. Add synthetic review generator and targeted acceptance coverage.
- These are locally verified software features. Glowforge import, physical fit/finish and measured timing acceptance remain pending.

All notable changes to the `glowforge-it` project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Planned
- **Stage 3 (Visual Proofing)**: Preset audition contact sheets, 1:1 pixel inspection viewer, crop anchors, and framing guides. See [roadmap.md](roadmap.md).

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
- **Packaging & Console Script (2G)**: Added standard `pyproject.toml` configuration declaring console entry points (`glowforge-it`, `gf`), version declaration (`0.2.0`), separated runtime and test dependencies, and added `--version` CLI flag.

### Fixed
- **Trial preflight and reuse**: PNG metadata inspection now skips pixel data, including when EXIF/XMP follows IDAT. Shared memory estimates cover simultaneous float64 dither arrays and padding. Dry-run results expose sizes and memory; blocked destination roots fail before rendering. Manifest validation returns errors for malformed records and unreadable files, resolves source paths relative to the manifest, and verifies hashes/recipe before manifest-backed skip. Direct API validation includes batch-level options; unknown recipe presets fail explicitly. Installed `gf` now matches the wrapper's clean-solids default.
- **EXIF-Oriented Memory Estimation (P1)**: Extracted `get_oriented_dimensions` and `resolve_target_dimensions` in [geometry.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/geometry.py) to resolve header-level EXIF rotation tags prior to pixel decoding, ensuring estimation, planning, and rendering share identical geometry without memory budget bypass on rotated photographs.
- **Zero-Decode Budget Preflight (P2)**: Moved `max_memory` verification in `plan_batch` ahead of pixel decoding and avoided `ImageOps.exif_transpose` during planning/dry-runs.
- **Strict Manifest Verification (P2)**: Hardened `verify_job_manifest` to reject empty or missing schema definitions, require valid source and output records with hashes, detect unresolvable sources, and verify explicit source paths unconditionally.
- **Recipe Sidecar & Material CLI Support (P2)**: Included `svg_cut`, `manifest`, `material`, and `material_thickness_in` in `ProcessingSettings` and `resolve_settings`, setting CLI argument parser defaults to `None` so recipe-requested sidecars and materials are honored instead of silently dropped.
- **Strict Shared Type & Finiteness Validation (P2)**: Updated `ProcessingSettings.validate()` to strictly verify boolean types, reject boolean values on integer fields, and assert finite numeric values (rejecting `NaN` / `Inf`) before range comparisons.

---

## [Stage 1.5: Modular Monolith Extraction] - 2026-09-25

### Architecture & Modularization
- **Package Decomposition**: Extracted monolithic `main.py` (1,298 lines) into the structured [glowforge_it/](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it) package:
  - [settings.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/settings.py): Defaults, presets, and `ProcessingSettings` resolution.
  - [geometry.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/geometry.py): Circle and heart cut geometry, bed preflight, and physical sizing.
  - [imaging.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/imaging.py): Pure image-to-image pipeline (orientation, normalization, tone adjustments, Atkinson dithering, and shape masks).
  - [publication.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/publication.py): Atomic sibling staging, file replacement, rollback, and `RecoveryError`.
  - [export.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/export.py): Raster PNG and SVG sidecar document generation.
  - [planning.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/planning.py): Source discovery, destination namespace, path containment, and `PlannedJob`.
  - [batch.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/batch.py): Plan execution and batch outcome reporting.
  - [cli.py](file:///Users/ryanjohnson/Projects/glowforge-it/glowforge_it/cli.py): CLI argument parsing and input validation.
- **Compatibility Launcher**: Retained [main.py](file:///Users/ryanjohnson/Projects/glowforge-it/main.py) as a 71-line wrapper with inline `uv` dependency metadata and public API re-exports, preserving `./gf`, direct python execution, and external script invocations.
- **Strict AST Architecture Guard**: Added [tests/test_compat.py](file:///Users/ryanjohnson/Projects/glowforge-it/tests/test_compat.py) to statically enforce one-way layer dependencies (`cli -> batch -> planning/export -> imaging/publication -> geometry -> settings`) and prevent circular imports.
- **Modular Test Suites**: Reorganized tests into 6 focused test files under [tests/](file:///Users/ryanjohnson/Projects/glowforge-it/tests) using shared helpers in [tests/helpers.py](file:///Users/ryanjohnson/Projects/glowforge-it/tests/helpers.py) (56 tests passing across Python 3.11–3.13, default, and `importlib` import modes).
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
- Presets: `photo-soft`, `photo-high-detail`, `illustration`, `line-art`, `high-contrast`, `stamp`, `sketch`, `dark-surface`.
- Fit modes: `stretch`, `contain`, `cover` at fixed 300 DPI.
- Sizing options: width, height, max dimension, and scale multiplier.
- Circular and heart mask cutouts with optional SVG sidecar generation containing cut outlines.
- Recursive input directory traversal and batch output mirroring.
