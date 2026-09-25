# Glowforge Image Prep: Roadmap

This roadmap indexes the current state, technical corrections, and future delivery sequence for `glowforge-it`.

## Primary Documents

* **[Project Review & Professional Product Roadmap](docs/project-review.md):** Consolidated architectural assessment, disposition of findings F01–F12, comprehensive enhancement catalog (E01–E56), and multi-stage product vision.
* **[Implementation Status Log & Priority Plan](docs/UPDATE-IDEAS.md):** Detailed dated implementation history, technical findings from independent review, and prioritized engineering backlog (P0–P3).

---

## Current Status

### Completed Milestones

* **Stage 1 — Engine Hardening (Findings F01–F12):**
  * **Batch Path Planning & Containment:** All sources and destinations are resolved and validated before any file is published. Prevents destination writes into source directories, even with nested or symlinked structures.
  * **Case-Folding Collision Detection:** Runtime probing detects case-insensitive filesystems (such as macOS APFS) and normalizes paths (NFC + casefold) to catch destination collisions prior to execution.
  * **Bounded Cover Resampling:** High-aspect-ratio cover-fit resizing crops directly from source bounds via `Image.resize(box=...)`, avoiding unbounded intermediate memory allocation.
  * **Transparency Normalization:** Full compositing over white for RGBA, LA, PA, and color-key `tRNS` transparency across RGB, L, and palette images.
  * **Post-Dither Layout Padding:** For `--fit contain`, artwork is processed and dithered before being laid onto white canvas padding, preventing inverted or dither-speckled borders.
  * **Staging & Rollback Recovery:** Sibling file staging (`.gf-*`) and pre-publication backup (`.gf-prev-*`) with independent multi-file rollback. If restoration fails, `RecoveryError` preserves backup files and maps them to destination paths.
  * **Explicit Ablation Flags:** Preset stages can be explicitly turned off via `--denoise 0`, `--sharpen-radius 0`, or `--sharpen-percent 0`.

* **Stage 1.5 — Modular Monolith Extraction:**
  * Clean decomposition of `main.py` into the `glowforge_it/` package:
    * `settings.py`: Defaults, presets, resolved `ProcessingSettings`.
    * `geometry.py`: Shape cut geometry (circle, heart) and machine bed preflight.
    * `imaging.py`: Pure image-to-image pipeline (normalize, tone, dither, mask).
    * `publication.py`: Generic staging, replacement, rollback, and `RecoveryError`.
    * `export.py`: Raster PNG and SVG sidecar document generation.
    * `planning.py`: Source discovery, destination namespace, containment, and `PlannedJob`.
    * `batch.py`: Batch coordination and text reporting.
    * `cli.py`: Argument parsing and CLI validation.
  * Strict one-way AST dependency guard in `tests/test_compat.py`.
  * `main.py` preserved as a 71-line compatibility launcher retaining `uv` script metadata and public re-exports.
  * 56 tests passing across 6 modular test suites.

---

## Sequenced Delivery Plan

| Stage | Focus | Key Deliverables |
|---|---|---|
| **Stage 2** | Reproducible CLI | Versioned job manifests (`E10`), source content SHA-256 hashes, structured JSON results (`E14`), immutable job directories, dry-run contract (`E12`). |
| **Stage 3** | Visual Proofing | Preset audition / contact sheets (`E18`), 1:1 pixel inspection viewer (`E19`), crop and framing controls (`E20`), dimension annotations. |
| **Stage 4** | Physical Evidence | Glowforge app SVG import verification (`E25`), supervised test-card calibration on medium maple plywood (`E26`), physical result log (`E27`). |
| **Stage 5** | Professional Workspace | Local preview UI (`E31`), validated TOML/JSON user recipes (`E32`), local revision history (`E51`). |
| **Stage 6** | Production Expansion | Sheet nesting (`E43`), measured kerf compensation (`E42`), segmentation (`E44`), and personalization overlays (`E45`). |

---

## Boundary and Non-Goals

* **Software vs. Machine:** This tool prepares artwork files (PNG/SVG). Laser power, speed, focus, and pass settings are configured exclusively in the Glowforge app.
* **Material Authority:** Default context is medium maple plywood at 1/8". Stock labels in CLI outputs are descriptive notes, not validated machine profiles.
* **Local First:** All image processing runs locally. User artwork is not transmitted to cloud services or external model providers.
