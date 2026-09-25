# Glowforge Image Prep: Roadmap

This roadmap defines the forward delivery plan for `glowforge-it`: a local artwork-preparation and proofing tool for makers working with AI-generated art and Glowforge workflows.

The core product loop is:
**Import → Inspect → Compare → Frame → Export a Traceable Job → Record the Result → Reproduce an Approved Revision**.

> **Note on Project History:**
> * For completed milestones (Stage 1, Stage 1.5, Stage 2), see [CHANGELOG.md](CHANGELOG.md).
> * For exploratory backlog concepts and speculative ideas, see [docs/UPDATE-IDEAS.md](docs/UPDATE-IDEAS.md).
> * For the full technical assessment and findings F01–F12 / E01–E56 catalog, see [docs/project-review.md](docs/project-review.md).

---

## Sequenced Delivery Overview

| Stage | Focus | Primary Goal | Next Milestone |
|---|---|---|---|
| **Maker Track (MW01–MW06)** | **Registered Fabrication & Proofs** | Unified SVGs, ablation polarity, maple previews, client proofs, pocket jigs, trim | Initial software CLI slices implemented; app import & physical gates open |
| **Stage 3** | **Visual Proofing** | Recipe audition, 1:1 pixel inspection, framing, and candidate selection | Immediate Next Focus (Start with 3A) |
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
  * Numerically assert and distinguish source pixels, output pixels, physical canvas dimensions, nominal outline, and engraving inset.
  * Add explicit unit support (inches, mm) and fraction parsing across all dimension inputs.
  * Add low-DPI upscaling warnings when source image resolution is significantly below 300 DPI.
* **Acceptance:** Dimension assertions agree across raster masks, SVG sidecars, and manifest metadata down to 0.001".

### 3C. Audition & 1:1 Pixel Inspection
* **Target Enhancement:** E18, E19
* **Deliverables:**
  * Add preset audition mode (`--audition`) to produce labeled contact sheets comparing candidate presets on the same source artwork.
  * Build a 1:1 pixel inspection tool highlighting crushed shadows, burned-out highlights, and local dither density.
* **Acceptance:** Selecting an auditioned candidate exports the exact full-resolution recipe without re-sampling discrepancies.

### 3D. Framing & Advanced Tone Controls
* **Target Enhancement:** E20, E24
* **Deliverables:**
  * Add crop anchors (top, bottom, left, right, center) and subject-safe margins for `--fit cover`.
  * Add asymmetric horizontal reflection/mirroring (`--mirror`) for engraving reverse sides of acrylic or glass.
  * Add tunable levels, gamma, and curve adjustments with clear before/after diffs.
* **Acceptance:** Preview accurately shows removed artwork; asymmetric fixtures verify reflection geometry.

---

## Stage 4 — Physical Evidence (Parallel Workstream)

*Note: Software tests alone cannot validate physical machine behavior. This stage runs in parallel with Stage 3.*

| Delivery | IDs | Focus & Acceptance Criteria |
|---|---|---|
| **4A. SVG App Acceptance Pack** | E25 | Import circle and heart SVG sidecars directly into the Glowforge web app. Record imported dimensions, vector/raster alignment, and default operation assignment (engrave vs cut). |
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
| **6A. Alternative Rendering Modes** | E23, E36, E37, E38 | Floyd–Steinberg, Bayer ordered dither, variable halftone dot screens, hatch textures, and multi-pass registered tone layers. |
| **6B. Input Semantics & Performance** | E34, E35 | Multi-page PDF / multi-frame GIF frame selection, embedded ICC color profile preservation, optional HEIC import, and streaming row-buffer decoding. |
| **6C. Parametric & Vector Cut Shapes** | E39, E40, E41 | Rounded rectangles, polygons, stars; custom SVG path cutlines; vector hang holes, mounting tabs, and score line groups. |
| **6D. Kerf Offsets & Sheet Nesting** | E42, E43, E44 | True geometric kerf compensation; multi-piece sheet layout and nesting with grain constraints; long-job passthrough segmentation. |
| **6E. Personalization & Barcodes** | E45, E46 | CSV-driven batch personalization (badges, favors) with deterministic text layout; dither-protected QR and barcode stamps. |
| **6F. Production Cost Estimator** | E52 | Material yield, laser operating time estimates, and job cost calculations based on user-entered parameters. |

---

## Maker Workflow Delivery Track

The six [MW01–MW06 candidates](docs/UPDATE-IDEAS.md#6-end-to-end-maker-workflow-mw01mw06) extend prepared artwork into customer approval and registered fabrication. The first CLI slices are implemented; see the [maker workflow guide](docs/maker-workflow.md). Local software checks do not close app-import or physical acceptance gates. Keep 3A fixtures as the foundation.

| Sequence | Placement | Bounded delivery and exit gate |
|---|---|---|
| 1 | **MW04: Unified SVG**, extend 4A after 3B | Extend existing bundling with operation colors/score marks; verify actual app grouping, assignments, dimensions, and order before changing defaults. |
| 2 | **MW06: Ablation polarity**, extend 3D/4B | Explicit mask polarity and versioned curves; verify endpoints, no-burn padding, and physical tonal ramps. |
| 3 | **MW01: Finish preview**, new 3E | Reproducible maple simulation from the exact burn mask; expand substrates after polarity and scale checks. |
| 4 | **MW05: Approval sheet**, new 3F linked to 5B | Local one-page proof tied to artifact hashes; depends on preview and revision identity, not the UI. |
| 5 | **MW02: Pocket jig**, new 6G linked to 4C | One blank then regular grid, measured clearance and shared coordinates; measure repeat placement before accuracy claims. |
| 6 | **MW03: Trim/orientation**, extend 3B/6F | Placement-preserving trim and constrained rotation advice; report scan rows before calibrated minutes. Measure any savings. |

Detailed contracts, failure cases, and dependencies live in the backlog. Every new artifact must participate in dry-run planning, resource limits, existing-file policy, and versioned manifests. Preview/approval artifacts remain separate from machine artwork; generation never silently changes approved artwork or marks a job customer-approved.

The expanded workflow is **prepare → inspect → simulate → approve a revision → register and fabricate → record the result → reproduce**. Physical results feed calibration; approval binds to a specific revision. Correct digital geometry alone cannot establish preview realism, jig repeatability, or timing accuracy.

---

## Quality and Decision Gates

* **Q1. Architecture Boundaries & Regression Coverage (E55):** Maintain strict one-way import hierarchy; expand automated CI testing across Python versions (3.11–3.13) and operating systems (macOS, Linux).
* **Q2. Real-World Maker Feedback (E56):** Track real-world proofing workflows, failed jobs, and reorder repeatability to validate roadmap priorities before building complex features.

---

## Non-Goals & System Boundaries

* **Laser Setting Authority:** This tool produces digital artwork (raster PNG and vector SVG). Power, speed, focus, and pass settings are configured exclusively in the Glowforge web application.
* **Material Authority:** Default context is medium maple plywood at 1/8". Material labels in logs and manifests are descriptive notes, not validated machine profiles.
* **Local First:** All image processing runs locally. User artwork and personal client data are never uploaded to cloud services without explicit user opt-in.
