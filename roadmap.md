# Glowforge Image Prep: Roadmap

This roadmap defines the forward delivery plan for `glowforge-it`: a local artwork-preparation and proofing tool for makers working with AI-generated art and Glowforge workflows.

The core product loop is:
**Import → Inspect → Compare → Frame → Export a Traceable Job → Record the Result → Reproduce an Approved Revision**.

This is the single planning document: staged work, the uncommitted backlog, open risks and the evidence boundary. Completed work (Stage 1 findings F01–F12, Stage 1.5, Stage 2, the maker workflow first versions) lives in [CHANGELOG.md](CHANGELOG.md). `E##` labels are stable enhancement IDs carried over from a September 2026 project review; that review is not kept in this repository, so this file is the only place they are defined.

---

## Immediate review closure

The October review closed the initial sample-validation, sidecar, audition-layout, provenance, and direct-export gaps. The November working-tree review focuses on interruption recovery, output integrity, and renderer edge cases. See the [remediation record](docs/review-remediation.md) for dated software evidence. Inspect newly generated artifacts and use the [first-burn checklist](docs/first-burn-checklist.md) to record app and physical results. A distribution license remains an owner decision before public release.

## Sequenced Delivery Overview

| Stage | Focus | Primary Goal | Next Milestone |
|---|---|---|---|
| **Maker Track (MW01–MW06)** | **Registered Fabrication & Proofs** | Unified SVGs, ablation polarity, maple previews, client proofs, pocket jigs, trim | CLI slices implemented; app import & physical gates open (below) |
| **Stage 3** | **Visual Proofing** | Recipe audition, 1:1 pixel inspection, framing, and candidate selection | After review validation: representative fixtures (3A) |
| **Stage 4** | **Physical Evidence** | Target app SVG import verification, test-card calibration, and physical logs | Parallel track with Stage 3 |
| **Stage 5** | **Professional Workspace** | Accessible local UI, revision history, portable job archives, and agent interface | After Stage 3 contracts stabilize |
| **Stage 6** | **Production Expansion** | Production layouts, kerf compensation, vector tracing, and personalization | Bounded increments by demonstrated maker need |

---

## Stage 3 — Visual Proofing (Immediate Focus)

*Prerequisite: Stage 2 shared settings, structured results, and versioned manifests.*

The goal of Stage 3 is to provide visual confidence before burning materials: inspectable recipes, side-by-side preset comparisons, 1:1 pixel inspection, and framing controls.

### 3A. Representative Fixtures & Recipe Cards
* **Target Enhancement:** E29, E53
* **Deliverables:**
  * Build a curated, rights-cleared image test pack spanning photographic portraits, high-detail line art, fine text, high-contrast graphics, and awkward aspect ratios.
  * Create concrete recipe cards pairing AI prompt directions with recommended presets, expected contrast behavior, and sample outputs.
* **Acceptance:** Fixture pack runs through the automated test suite without regressions and demonstrates both successful engravings and intentional failure cases.

### 3B. Size & Geometry Contract
* **Target Enhancement:** E21, E22
* **Deliverables:**
  * **Delivered slice:** circle and heart SVG outlines are asserted against the raster mask to 0.3 px (0.001"); `--fit stretch` warns when it distorts proportions by more than 2%.
  * Numerically assert and distinguish source pixels, output pixels, physical canvas dimensions, nominal outline, and engraving inset.
  * Positive inch dimensions now accept fractions (width, height, stock thickness, blank size, jig margin/gap). Remaining: millimeters and fractional zero-allowed clearance/kerf inputs.
  * Add low-DPI upscaling warnings when source image resolution is significantly below 300 DPI.
* **Acceptance:** Dimension assertions agree across raster masks, SVG sidecars, and manifest metadata down to 0.001".

### 3C. Audition & 1:1 Pixel Inspection
* **Target Enhancement:** E18, E19
* **Deliverables:**
  * **Delivered slice:** preset audition mode (`--audition`) produces labeled contact sheets and JSON recipe/coverage records from full-resolution candidate renders.
  * **Delivered slice:** direct candidate export from a saved audition by name or numbered sheet position; restores exact dimension arguments, source, settings and polarity, with source/sheet/runtime checks and a full-resolution pixel hash check before publication. Exports PNG plus manifest through normal planning and publication. Older records need regeneration; production-sidecar overrides remain separate work.
  * Add exact 1:1 pixel inspection for selected regions.
  * Build a 1:1 pixel inspection tool highlighting crushed shadows, burned-out highlights, and local dither density.
* **Acceptance:** Selecting an auditioned candidate exports the exact full-resolution recipe without re-sampling discrepancies.

### 3D. Framing & Advanced Tone Controls
* **Target Enhancement:** E20, E24
* **Deliverables:**
  * Add crop anchors (top, bottom, left, right, center) and subject-safe margins for `--fit cover`.
  * Add asymmetric horizontal reflection/mirroring (`--mirror`) for engraving reverse sides of acrylic or glass.
  * Levels/gamma/polarity are implemented. Remaining: interactive before/after diffs and richer curves.
* **Acceptance:** Preview accurately shows removed artwork; asymmetric fixtures verify reflection geometry.

---

## Stage 4 — Physical Evidence (Parallel Workstream)

*Note: Software tests alone cannot validate physical machine behavior. This stage runs in parallel with Stage 3.*

| Delivery | IDs | Focus & Acceptance Criteria |
|---|---|---|
| **4A. SVG App Acceptance Pack** | E25 | Generate and verify the [synthetic acceptance pack](docs/first-burn-checklist.md#generate-the-synthetic-acceptance-pack). Import the representative SVGs and record dimensions, raster/vector alignment, and initial operation assignments. App observations remain open. |
| **4B. Artwork Calibration Test Cards** | E26 | Generate standardized test targets (grayscale tonal ramps, dot density matrices, line-width samples, text legibility cards). |
| **4C. Physical Result Log & Evidence Levels** | E27, E28 | Build a local notebook format capturing sheet material, supplier, measured thickness, laser power/speed/LPI settings, and high-resolution photos of finished cuts. |

---

## Stage 5 — Professional Workspace

*Prerequisite: Stable CLI contracts and manifest definitions from Stages 2–3.*

| Delivery | IDs | Focus & Acceptance Criteria |
|---|---|---|
| **5A. Accessible Local Workspace UI** | E31 | Standalone local browser/desktop UI: drag-and-drop art, interactive recipe audition, framing guides, full-resolution export, and keyboard accessibility. |
| **5B. Proof Revisions & Portable Archive** | E51, E54 | Link proofs to exact SHA-256 hashes. Package source artwork, recipe manifest, and physical notes into a single portable `.zip` job archive. |
| **5C. Watch Folder & Queue** | E33 | Automatic folder processing with debounce, copy-completion checks, concurrency locking, and failure recovery. |
| **5D. Agent Interface Contract** | E49 | Structured JSON-driven CLI/API allowing AI coding agents to plan, inspect, render, and verify jobs deterministically. |
| **5E. Explainable AI Assistance** | E48, E50 | Deterministic image diagnostics suggesting recipe adjustments. Optional external background removal adapters preserving original inputs. |

---

## Stage 6 — Production Expansion (By Demonstrated Need)

*An option backlog prioritized according to verified maker demands.*

| Delivery | IDs | Focus & Acceptance Criteria |
|---|---|---|
| **6A. Alternative Rendering Modes** | E23, E36, E37, E38 | **Implemented slices:** solid silhouette, Bayer ordered screen, variable halftone dot screen, directional hatch/crosshatch, Sobel edge, tone contour, centerline-style SVG linework, and registered 2–4 tone-band sidecars. Remaining: alternate error diffusion, general vector tracing, and app/material layer assignment. |
| **6B. Input Semantics & Performance** | E34, E35 | Multi-page PDF / multi-frame GIF frame selection, embedded ICC color profile preservation, optional HEIC import, and streaming row-buffer decoding. |
| **6C. Parametric & Vector Cut Shapes** | E39, E40, E41 | Rounded rectangles, polygons, stars; custom SVG path cutlines; vector hang holes, mounting tabs, and score line groups. |
| **6D. Kerf Offsets & Sheet Nesting** | E42, E43, E44 | True geometric kerf compensation; multi-piece sheet layout and nesting with grain constraints; long-job passthrough segmentation. |
| **6E. Personalization & Barcodes** | E45, E46 | **Implemented slices:** collision-checked text stamps and constrained version-1/L QR masks. Remaining: CSV-driven batch personalization, richer QR versions, and barcode variants. |
| **6F. Production Cost Estimator** | E52 | Material yield, laser operating time estimates, and job cost calculations based on user-entered parameters. |

---

## Maker Workflow: Remaining Gates

MW01–MW06 first CLI slices are implemented (see the [maker workflow guide](docs/maker-workflow.md)). Local software checks do not close app-import or physical gates:

| Item | Open gate or later extension |
|---|---|
| **MW04 Unified SVG** | Import representative files with score marks; record actual grouping, assignment and order before changing the legacy blue-cut default. |
| **MW06 Polarity** | Compare ordinary, simply inverted and tuned output on the same stock (4B/4C). Proposed profiles: dark-surface, slate, glass (glass also depends on viewing side). Semantic facial editing stays deferred. |
| **MW01 Finish preview** | Compare physical samples before claiming calibrated realism. Later substrates: walnut, slate, acrylic, leather; clear substrates need a viewing background and front/rear orientation. |
| **MW05 Approval sheet** | Inspect long names, absent fields and font embedding; approval stays an explicit user action. JPEG output if needed. |
| **MW02 Pocket jig** | Measure physical fit and repeated placement error before any accuracy claim. Later: double-sided jobs (flip axis, backside transform, keyed pocket or orientation stop). |
| **MW03 Trim** | Check whether the app already trims equivalent bounds before claiming savings. Orientation advice was removed (it could not decide anything without calibrated timing); revisit only with measured machine timing (feeds E52) and an explicit `--rotate 90` that transforms all registered geometry. |

Every new artifact must participate in dry-run planning, resource limits, existing-file policy and versioned manifests. Preview/approval artifacts stay separate from machine artwork, and generation never marks a job customer-approved.

---

## Open Risks

1. **Batch interruption (E02).** A journal enables explicit per-job recovery after process interruption, while earlier successful jobs remain available. Partial output can be visible until recovery runs. POSIX advisory locking coordinates publication and recovery in the same directory. Keep independent backups for storage loss.
2. **No aggregate resource model (E03).** Per-image memory estimates exist; there is no worker/aggregate budget.
3. **No app-import evidence (E25).** Generated SVGs have not been demonstrated in the Glowforge app for size, alignment and operation assignment.
4. **No material-result corpus (E26–E28).** Presets are image-processing starting points, not validated machine recipes.
5. **No project license or contribution policy (E17).** Owner decision.
6. **Progress, cancellation and failed-only resume (E14)** are not implemented; results are structured JSON.
7. **Docs can drift from options (E30).** Generate the option/preset reference from the validated settings schema.
8. **Provenance is partial (E47).** Prompt and model are recorded; source ID, usage notes and edit history are not.

---

## Backlog (Uncommitted Ideas)

An idea moves into a stage only when it shows clear maker value, keeps deterministic local output, has bounded complexity (no heavy binaries or hardware-specific assumptions), and does not try to replace the Glowforge app or promise physical results.

| Idea | Value | Main risk |
|---|---|---|
| Alternate error diffusion (Floyd–Steinberg, Stucki, Sierra…) | Fine-tune dot clustering per wood | Atkinson was chosen because it resists shadow dot-gain; others often over-darken shadows |
| Custom SVG cutlines / `potrace` tracing (E40) | Framing beyond circle and heart | Double strokes, kinks and open loops; needs path sanitization and preview |
| Parametric shapes (E39) | Plaques, badges, ornaments without other software | Raster/SVG alignment across odd/even pixel sizes |
| Hang holes, slots, easel tabs (E41) | Directly hangable or freestanding pieces | Wall-thickness rules to avoid cracking |
| Geometric kerf offsets (E42) | Press-fit joinery and inlays | Kerf varies by species, moisture, focus; robust polygon clipping required |
| Sheet nesting (E43) | Material yield for small batches | High complexity; many makers lay out in the app |
| Pro passthrough slicing (E44) | Signs and long panels | Hardware-specific; relies on manual registration |
| Local background removal (E50) | Faster portrait/pet prep | ~150 MB model and native runtime; fuzzy hair edges dither poorly; opt-in only |
| Pre-engrave diagnostics / recipe advisor (E48) | Catch bad burns on screen | False warnings on intentional styles; visual judgment often faster |
| CSV personalization (E45) | Wedding favors, badges, awards | Font discovery, wrapping, overflow, licensing |
| Richer QR versions and barcodes (E46) | Menus, signs, inventory tags | Needs physical scan testing across materials |
| Yield and costing (E52) | Pricing small-batch work | Machine time needs measured profiles |
| Watch folder (E33) | Hands-free processing | Partial writes, locks, duplicate events |
| HEIC import, frame/page selection, ICC handling (E35) | Convenience for phone/PDF/GIF sources | Native libraries; ICC gives negligible visible difference after 1-bit dithering |

---

## Evidence Boundary

Source documentation, software checks, app observations, physical measurements and customer approval are distinct evidence levels. No app import, device run or customer research has been recorded. Remote CI results live in the repository's Actions history. Official Glowforge references consulted September 25, 2026 (background, not app evidence):

- [File uploads](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes), [printable area](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area)
- [Print-step ordering](https://support.glowforge.com/hc/en-us/articles/20546433415451-setting-the-order-of-your-print-steps): colors separate steps; they do not universally assign cut or score.
- [Manual mode](https://support.glowforge.com/hc/en-us/articles/360033633574-Working-With-Manual-Mode): LPI, speed, passes and acceleration affect timing, so rotation savings need measurement.
- [Alignment](https://support.glowforge.com/hc/en-us/articles/360033633714-Alignment): setup, height and calibration affect alignment; 0.1 mm jig repeatability has not been established.

---

## Quality and Decision Gates

* **Q1. Architecture Boundaries & Regression Coverage (E55):** Maintain the one-way import hierarchy enforced by `tests/test_compat.py`. CI covers Python 3.11–3.14 on Linux and macOS and has wheel/sdist installation smoke checks with and without the proof extra. See the [validation record](docs/review-remediation.md#validation-record) for observed results.
* **Q2. Real-World Maker Feedback (E56):** Track real-world proofing workflows, failed jobs, and reorder repeatability to validate roadmap priorities before building complex features.

---

## Non-Goals & System Boundaries

* **Laser Setting Authority:** This tool produces digital artwork (raster PNG and vector SVG). Power, speed, focus, and pass settings are configured exclusively in the Glowforge web application.
* **Material Authority:** Default context is medium maple plywood at 1/8". Material labels in logs and manifests are descriptive notes, not validated machine profiles.
* **Local First:** All image processing runs locally. User artwork and personal client data are never uploaded to cloud services without explicit user opt-in.
