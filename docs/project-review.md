# Glowforge Image Prep: updated project review and professional product roadmap

Updated September 25, 2026, after Stage 1 hardening, the independent-review follow-up, Stage 1.5 modularization, and test-import/architecture-guard follow-up.

**Review basis:** current uncommitted working tree based on commit `674eb11`. That commit alone does not contain the reviewed implementation. Implementation and test changes are unstaged; the package and split tests are currently untracked. This document update does not stage, commit, or publish them.

**Purpose:** this is the consolidated assessment and enhancement inventory. [UPDATE-IDEAS.md](UPDATE-IDEAS.md) remains the implementation status log. This report supersedes the initial report's current-state assessment while retaining its finding IDs F01–F12 and enhancement IDs E01–E56. Historical defects below are not being presented as open current bugs.

**Current assessment**

The project has advanced from a single-file raster-preparation utility to a local modular monolith with complete-batch path planning, tested source protection, bounded cover-fit resizing, more complete transparency normalization, and publication recovery. The specific defects demonstrated in Stage 1 and its independent follow-up have been addressed in the reviewed scenarios. The extraction preserves the current CLI and compatibility launcher.

The next product gap is reproducibility and visual decision support: saved job identity, manifests, inspectable plans, replay, structured results, and preset comparison. The application still lacks evidence of actual Glowforge import behavior and physical output quality. Software hardening and physical acceptance are separate workstreams; neither substitutes for the other.

The proposed product remains a local artwork-preparation and proofing workbench: import source artwork, inspect it, compare recipes, frame at physical size, export a traceable job, and record the real result. AI-generated art is an input today. The project does not itself perform model inference, generation, background removal, or automated machine control.

**Evidence and scope**

Evidence labels throughout this document:

- **Independently checked:** inspected or exercised by the reviewing assistant in this conversation. Each check has the scope stated below.
- **Implementation-reported:** supplied in implementation updates; not independently rerun in full by the reviewer.
- **Source-confirmed:** directly visible in the current files, without implying every case was executed.
- **Planned/deferred:** not implemented, or deliberately outside the completed contract.
- **Unverified:** requires additional environment, app, machine, or user evidence.

| Evidence | Status and scope |
|---|---|
| Latest full suite, default import mode | Independently checked: 56 passed |
| Latest full suite, `--import-mode=importlib` | Independently checked: 56 passed |
| Extraction comparison | Implementation-reported: 87 values identical before/after, normalized temporary paths; covers 18 image-option combinations, normalization, geometry, SVG documents, filenames, file hashes, errors, parser cases and output policies |
| Stage 1 follow-up verification | Independently checked: 20 selected tests passed, plus the independent behavioral probes |
| Extraction verification | Independently checked: 13 selected tests passed; corrected behavioral probes preserved; absolute-path Python launcher worked from an unrelated cwd with `PYTHONPATH` removed |
| Latest compatibility guard and launcher tests | Independently checked: 5 passed under `importlib` mode (including `from glowforge_it import <submodule>` import coverage) |
| Explicit shared test helpers | Source-confirmed: `tests/helpers.py` and `tests/__init__.py`; no remaining `conftest.py`; 16 planning tests independently collected under `importlib` mode |
| Forbidden absolute import injection | Implementation-reported: adding `import glowforge_it.cli` to settings caused the architecture guard to fail; file restored afterward |
| Whitespace validation | Independently checked: `git diff --check` passed cleanly |
| Current remote CI execution | Unverified; configuring the matrix does not demonstrate a completed CI run |
| Glowforge SVG import, placement and operation assignment | Unverified |
| Physical material quality, dimensional fit and calibration | Unverified |

Test selections above overlap; their counts are not additive coverage totals. The full 56-test suite was independently verified using Python 3.13.1, NumPy 2.4.2, Pillow 12.1.1 and pytest 8.2.2 under both default and `importlib` import modes.

A pre-extraction synthetic 1200 × 1200 transform measured 0.818 seconds and 79.7 MiB process peak RSS. This is historical local reference evidence, not a fresh benchmark or a maximum-size guarantee.

**Current capability map**

| Area | Implemented | Remaining boundary |
|---|---|---|
| Launch | `gf` wrapper, 70-line `main.py` compatibility launcher, inline uv dependency pins and legacy re-exports | Package installation/console distribution deferred; wrapper and direct Python differ in clean-solids default |
| Input | Multiple files and recursive folders; PNG/JPEG/BMP/WebP/TIFF/GIF | No SVG/PDF source workflow, HEIC, or explicit frame/page selection |
| Normalization | EXIF orientation and alpha/color-key compositing onto white | No explicit ICC/color-management policy or complete format-validation corpus |
| Processing | Grayscale, optional denoise, inversion, snapping, thresholds, contrast, optional sharpening, Atkinson | No alternate dither, threshold-only/grayscale output, mirror, curves or audition UI |
| Fit/layout | Fixed 300 DPI, one-axis proportional sizing, stretch/contain/cover; contain padding added after dithering | Default stretch can distort; canvas size differs from outline size; no framing controls |
| Geometry | Circle/heart masks and matching SVG outline generation | No generalized shapes, holes, tabs, kerf, nesting or registration system |
| Planning | Whole-batch discovery and destination checks, source identities, case/Unicode normalization, containment, file/directory conflicts | Probe/directory creation is a planning side effect; no dry-run contract or persistent plan |
| Publication | Staged files, ordinary-error rollback, independent recovery attempts, `RecoveryError` with backup map | Not crash-proof, not an atomic multi-file transaction, no demonstrated concurrent-writer guarantees |
| Batch reporting | Contextual errors, unconditional text summary, boolean result | No structured per-item result; no skipped counts, verified resume or provenance checks |
| Machine/material | Optional nominal bed-area check; descriptive material and thickness in logs | No machine settings chosen; no saved stock evidence or physical acceptance |
| Testing | 56 test functions split by responsibility; compatibility/import guard; Linux/macOS CI configuration | Broader export semantics, dynamic import enforcement and full physical evidence remain outside current proof |
| Content | README, handbook, commands, beginner guide, 101 ideas, 101 style prompts, 99 cow prompts, implementation roadmap | Inspiration remains richer than the demonstrated visual recipe gallery |

**Actual modular architecture**

```text
main.py                         compatibility launcher + uv metadata
  -> glowforge_it.cli           parser, CLI validators, entry point
       -> batch                 plan/execute coordination and text outcome
            -> planning         discovery, identity, paths, naming, PlannedJob
                 -> geometry    shape geometry and source-aware size preflight
            -> export           PNG/SVG rendering and one-image output set
                 -> imaging     normalization, fit, tone, dither, masks
                      -> geometry
                 -> geometry
                 -> publication staging, replacement, recovery

settings                        defaults, presets, ProcessingSettings, resolution
```

| Module | Current ownership | Source |
|---|---|---|
| `settings.py` | Defaults, presets, resolved settings and precedence | [settings](../glowforge_it/settings.py) |
| `geometry.py` | Circle/heart outlines and physical-size/machine preflight; currently opens sources through Pillow | [geometry](../glowforge_it/geometry.py) |
| `imaging.py` | Image-to-image pipeline; dither remains here | [imaging](../glowforge_it/imaging.py) |
| `planning.py` | Discovery, source identities, destination namespace, containment, structural checks and names | [planning](../glowforge_it/planning.py) |
| `publication.py` | Generic staging, replacement and recovery; no package imports | [publication](../glowforge_it/publication.py) |
| `export.py` | Raster/SVG serialization, per-image processing and publication coordination | [export](../glowforge_it/export.py) |
| `batch.py` | Calls planning, executes jobs, reports counts, returns a boolean | [batch](../glowforge_it/batch.py) |
| `cli.py` | Arguments and CLI-specific validation | [CLI](../glowforge_it/cli.py) |

The package initializer does not eagerly import implementations. The compatibility launcher preserves imports used by earlier tests and review probes. Presets remain with settings; a separate dither module, `src/` layout, packaging, and a new batch result type were deliberately deferred.

The extraction is complete; a unified typed application API is not. Long signatures and CLI-only validation remain. Geometry also combines pure outline calculations with source-file inspection. These are future design opportunities, not extraction failures.

**Architecture guard: current coverage and deliberate limits**

[Compatibility tests](../tests/test_compat.py) discover top-level package Python files, require the module list to be accounted for, enforce a rank ordering for recognized dependencies, and reject recognized imports of the compatibility launcher. Relative and absolute submodule forms are normalized. The recent absolute-import bypass is addressed for the tested spellings.

An explicit allowed-dependency map was deliberately deferred by the owner. The rank ordering therefore still permits some imports that the intended responsibility boundaries would discourage, such as publication importing imaging. Current source does not contain that edge.

Do not describe the guard as exhaustive enforcement of every possible Python import. Source inspection shows that `from glowforge_it import cli` produces an empty dependency name, which the test skips; imports from `__init__.py` are also exempt from rank checks. Dynamic imports are outside the AST guard. These are narrow future test-hardening opportunities, not observed cycles in the current package. The metatest validates listed spellings, rather than a general import-policy proof.

Shared test utilities now live in [tests/helpers.py](../tests/helpers.py), explicitly imported through the `tests` package. The prior `conftest` import/collection issue is resolved in the checked importlib collection scenario.

**Original findings F01–F12: current disposition**

“Addressed” below refers to the demonstrated finding and bounded follow-up checks. It does not imply all conceivable failure modes are exhausted.

| ID | Original issue | Current disposition and evidence |
|---|---|---|
| F01 | Earlier outputs could overwrite later explicit inputs | Addressed: all sources/destinations planned before publication; resolved-path/inode source protection; tested explicit, symlink and hard-link scenarios |
| F02 | Case-only destinations could silently collide on this Mac | Addressed in reviewed filesystem scenario: runtime case probe and normalized namespace; macOS included in CI configuration |
| F03 | Symlinked output parents could enter source trees | Addressed after follow-up: destination containment checks both output root and every selected input directory, including input nested under output |
| F04 | PNG publication could destroy the previous pair before SVG failure | Addressed for ordinary errors through rollback; follow-up attempts all recoveries and identifies retained backups. Crash-proof generations remain E02/E10 |
| F05 | Cover-fit requested an enormous intermediate | Addressed: direct source-crop resampling; regression checks size before allocation; extreme-aspect CLI input now succeeds boundedly |
| F06 | RGB/L PNG color-key transparency became black output | Addressed in tested modes through generalized transparency compositing |
| F07 | Output-root errors escaped CLI handling | Addressed for demonstrated error; planning collects contextual errors and traversal errors. Structured result model remains E05/E14 |
| F08 | Preset denoise/sharpen stages could not be disabled | Addressed: zero disables denoise, sharpen radius or strength; CLI/documentation updated |
| F09 | Inversion and later tonal processing could blacken contain padding | Addressed after follow-up: artwork processed before assembly into white layout canvas, removing tonal processing and dither diffusion across padding |
| F10 | Examples misstated dither, mirroring, thresholds and material color behavior | Specific reviewed claims corrected; wider editorial/visual recipe improvement remains E29/E53 |
| F11 | Optional alias assumed by quick start; unclear cwd | Addressed for reviewed onboarding scope: `./gf`, source-copy step, explicit cwd semantics and zsh-only alias guidance |
| F12 | Missing negative-path tests and unsafe test mechanics | Addressed for reviewed cases: regression additions, real rollback injection, bounded resize spy, explicit golden-update path and CI expansion |

The first implementation was followed by four independently demonstrated behavior/recovery gaps and two weak tests. Those were corrected and independently rechecked before extraction; the probes still produced corrected results after extraction. This report does not leave those historical gaps marked open.

**What remains unresolved**

1. **No durable job identity or replay.** Filenames are not source-content hashes and do not capture tool/recipe versions, full settings, material context or output checksums.
2. **No crash-proof output bundle.** Ordinary rollback and incomplete-recovery reporting are present; process termination can still leave partial publication. A whole batch is not an all-or-nothing transaction.
3. **No complete resource budget.** The cover intermediate is fixed, but image processing still keeps several whole-image buffers and there is no aggregate worker/memory model.
4. **No visual proofing workflow.** Users still manually compare separate files. There is no integrated crop/framing, exact-pixel inspection, preset audition or approval record.
5. **No actual exporter acceptance evidence.** The generated SVG has not been independently demonstrated in the Glowforge app for physical size, alignment and operation assignment.
6. **No controlled material-result corpus.** Presets are image-processing starting points, not empirically validated machine recipes.
7. **No structured application result contract.** `run_batch` prints and returns a boolean; direct API calls do not yet share all CLI validation.
8. **No installable release package or explicit project license.** Package extraction is not package distribution. Owner license selection, release metadata, changelog and support guidance remain pending.
9. **Limited format/geometry choices.** Atkinson remains mandatory; outline dimensions, canvas dimensions and real cut dimensions must stay distinct.
10. **Test guard remains intentionally limited.** Total ordering is not an explicit module-boundary policy; the package-root import and initializer exemptions are described above.

Without requested dimensions, the fixed 300-DPI convention preserves pixels rather than the source file's original physical dimensions. The nominal machine check may allow rotation without rotating the output, and real usable engraving area can be smaller. The current circle outline is about 3.9967 inches on a 4-inch-square canvas; the heart bounds are about 3.5976 × 3.5291 inches. These previously measured geometry facts are not finished-cut measurements.

**Documentation and content opportunities**

The README and handbook now describe the actual command entry points and core limits more accurately. The updated report should be read alongside the dated implementation log; historical test counts such as 55 refer to the extraction checkpoint, while the latest implementation-reported count is 56.

| Document/content | Keep | Remaining improvement |
|---|---|---|
| README | Product boundary, practical options, first-run/cwd explanation | Add an inspectable sample pack, visual example, version/install/support and license pointers |
| Handbook | Pipeline explanation, raster/vector distinction, stock boundary | Reconcile pipeline prose with post-dither padding; add focused troubleshooting/recovery instructions and size/color semantics |
| Command guide | Short operational examples | Add safe output policies, fitting and failure-recovery examples linked to real fixtures |
| Beginner guide | Accessible introduction | Replace the confusing bright-star analogy for black-dot density; separate adult beginner onboarding from child-oriented prose |
| 101 project ideas | Broad inspiration and prerequisites in many entries | Remove remaining sales certainty; give each idea prerequisites, output type, validation status and a sample |
| 101 art styles | Explicit distinction between source-art prompts and processing | Add real source/output/final-size examples; label untested styles; distinguish subjects from rendering techniques |
| Cow prompts | Optional, distinctive themed collection | Keep separate from professional reference recipes; include provenance/usage notes and deterministic text guidance |
| UPDATE-IDEAS | Dated implementation history | Preserve historical evidence as dated; avoid reading old limitation text as current behavior; link stable enhancement IDs to future tasks |

Reduce repeated stock paragraphs through a canonical explanation. Keep material labels descriptive. Do not turn preset names, AI prompts, or a good screen preview into claims about machine settings or physical outcomes.

**Professional product direction**

The coherent workflow remains:

```text
Create a job -> preserve original art -> inspect source -> choose size/shape
-> compare recipes -> inspect final pixels -> select a candidate
-> export traceable files -> review in Glowforge -> record measured result
```

An eventual job bundle should contain prepared raster, optional vector design, versioned manifest, human-readable job card and clearly labeled preview. Original-source inclusion should be explicit for customer artwork. Record operator-entered material/machine context with its origin and evidence level; do not invent it from an image preset.

For AI-assisted work, prioritize source/prompt provenance and explainable recipe candidates. A future agent interface can expose inspect, plan, render, compare, verify and replay through the same validated engine. Those are proposed capabilities, not current commands. Optional generation/cleanup adapters should preserve originals and make upload/cost choices explicit.

A downsample-before-dither preview can differ from the production pattern. Exact inspection should use full-resolution results or regions; label approximate interactive previews. Build audition, saved jobs and precise inspection before broad production-layout or generation features.

**Comprehensive enhancement inventory with current status**

All 56 IDs from the initial review are retained. “Implemented” means the bounded reviewed scope, not universal acceptance. “Partial” identifies work already delivered and the remaining contract. “Planned” is not implemented. Relative sizes S/M/L are engineering estimates, not delivery commitments. Priority labels are retained from the original inventory; the delivery sequence below governs the next slice.

| ID | Current status | Original priority / size | Opportunity and solution | Remaining or maintained acceptance condition |
|---|---|---|---|---|
| E01 | Implemented for reviewed cases | Now / M | Complete batch planning, source/output identity checks, collision policy; resolve F01–F03 | All paths validated before publication; no source alteration; portable collision tests |
| E02 | Partial: rollback/recovery; durable bundles remain | Now / M | Complete-generation export, manifest commit, recovery; resolve F04 | Fault at each staging/publishing step preserves a usable prior job |
| E03 | Partial: cover allocation fixed; aggregate budgets remain | Now / M | Bounded cover crop and intermediate memory budget; resolve F05 | Extreme aspect ratios stay bounded; rejected work writes no output |
| E04 | Implemented for reviewed modes | Now / S | Full transparency normalization; resolve F06 | All supported transparency modes composite consistently |
| E05 | Partial: contextual errors/text summary; structured results remain | Now / S | Structured filesystem/decode failures and batch summaries; resolve F07 | Counts, paths, error codes, and exit status agree under partial failure |
| E06 | Implemented | Now / S | Explicit denoise/sharpen off controls; resolve F08 | Preset ablations work and resolved settings show disabled stages |
| E07 | Implemented | Now / S | Explicit padding/polarity contract; resolve F09 | Background is predictable under contain, inversion, and masks |
| E08 | Implemented for F10–F11 scope | Now / S | Correct examples and onboarding; resolve F10–F11 | Commands and semantic image checks agree; clean setup is documented |
| E09 | Implemented for reviewed regressions | Now / M | Focused negative-path regression corpus; resolve F12 | Reproductions fail against old code and pass after fixes; no fixture writes |
| E10 | Planned | Next / M | Versioned job manifests with source/output hashes, dimensions, recipe, tool/dependency versions | A job is traceable without filename interpretation or absolute paths |
| E11 | Planned | Next / M | Validated replay and immutable revisions | Changed source/recipe/environment is detected; replay limitations are explicit |
| E12 | Planned | Next / S | Dry-run/job plan with destinations, fits, warnings, and budgets | No processing outputs written; plan matches subsequent execution |
| E13 | Planned | Next / S | Safer output defaults and verified skip | Existing output is preserved unless explicitly replaced; reuse validates identity |
| E14 | Planned | Next / M | Result JSON, quiet mode, progress, cancellation, failed-only resume | Scripts need not parse prose; cancellation leaves no committed partial job |
| E15 | Partial: modules extracted; shared validation/API redesign remain | Next / M | Complete typed shared settings and validation across the existing package | CLI and direct API enforce identical validation; maintain behavior of accepted inputs |
| E16 | Planned | Next / M | Installable console package and supported runtime declaration | Clean-environment install/run works on supported platforms; test dependencies are separated |
| E17 | Planned | Next / S | Version command, changelog, release evidence, license and contribution policy | Users can identify the build and applicable project terms; owner selects license |
| E18 | Planned | Next / M | Preset audition/contact sheets with comparable crops and physical-size labels | Selecting a candidate exports the same full-resolution recipe/result |
| E19 | Planned | Next / M | Before/after viewer with 1:1 inspection, tone histogram, ink coverage and feature warnings | Preview distinguishes display scaling from production pixels and material simulation |
| E20 | Planned | Next / M | Framing, crop anchor, subject-safe region, margins, mirror/rotate, trim | Preview clearly shows removed artwork; asymmetric fixtures verify reflection |
| E21 | Planned | Next / S | Explicit units, fraction support where useful, size source and effective resolution | User sees source pixels, output pixels, physical canvas and upscaling warning |
| E22 | Planned | Next / M | Separate canvas, outline, engraving inset and fit-to-shape sizing | Nominal outline dimensions can be asserted numerically before app import |
| E23 | Planned | Next / M | Threshold-only, grayscale, Floyd–Steinberg and ordered-dither modes | Deterministic fixtures; clear output-mode identity; no hidden redithering |
| E24 | Planned | Next / M | Levels, gamma, curves and optional contrast normalization | Every stage can be inspected/disabled and serialized without ambiguous precedence |
| E25 | Planned | Next / M | SVG integration acceptance pack | Circle/heart imports retain dimensions, registration and intended operation separation in actual app evidence |
| E26 | Planned | Next / M | Artwork calibration cards: ramps, dots, thin lines, gaps, text-size samples | Printed labels map exactly to recorded image recipes; operator supplies machine settings |
| E27 | Planned | Next / M | Local result notebook linking stock/model/settings/photos/measurements to jobs | Software-only, operator-reported and measured outcomes remain distinguishable |
| E28 | Planned | Next / S | Recipe evidence levels and reviewed profile metadata | Presets are labeled experimental, visually reviewed or physically tested with dates/context |
| E29 | Planned | Next / M | Representative fixture and showcase pack | Rights-cleared photos, logos, transparent art, fine text, maps and awkward ratios show successes and failures |
| E30 | Planned | Next / S | Generate option/preset reference from validated schema | Docs cannot silently drift from renamed options or changed defaults |
| E31 | Planned | Later / L | Accessible local preview workspace | Drag/drop, keyboard operation, explicit save/recovery, exact export, no implicit upload |
| E32 | Planned | Next / M | Validated TOML/JSON user recipes with schema versions | Unknown keys and unsafe settings fail clearly; imported paths cannot escape job scope |
| E33 | Planned | Later / M | Watch mode with debounce, locks and durable queue | Half-copied files wait; duplicate events do not duplicate jobs; restart is recoverable |
| E34 | Planned | Later / M | Memory/performance optimization: row buffers, decode reuse, bounded workers | Golden equivalence and measured time/RSS improvement on named representative workloads |
| E35 | Planned | Later / M | Optional HEIC, explicit GIF/WebP/TIFF frame/page policy and ICC handling | Input semantics are documented and orientation/transparency survive conversion |
| E36 | Planned | Later / M | Halftone screens with cell size/angle | Final-size samples expose aliasing and dot closure; settings persist |
| E37 | Planned | Later / M | Hatch, sketch and edge rendering | Genuine algorithms are separated from source-art style labels; preview shows detail loss |
| E38 | Planned | Later / M | Registered multi-tone layers | Registration and layer identities are explicit; app operation assignment is reviewed |
| E39 | Planned | Later / M | General shapes: rounded rectangles, ovals, polygons, stars | One geometry model drives masks, previews and SVG bounds |
| E40 | Planned | Later / L | Custom SVG shapes/vector tracing with path validation | Closed paths, bounded complexity, no external-resource surprises, visible contour review |
| E41 | Planned | Later / M | Holes, tabs, hanging slots and score groups | Dimensions, edge distance and wall constraints are inspected; editable operation groups |
| E42 | Planned | Later / L | Measured kerf offsets | True geometric offsets, topology checks, nominal/compensated dimensions, physical fit evidence |
| E43 | Planned | Later / L | Sheet layout, repeated pieces, nesting, grain/rotation restrictions and jig support | No overlap; margins respected; every instance traceable to approved artwork |
| E44 | Planned | Later / L | Model-specific long-job segmentation | Registration/overlap is explicit and demonstrated in actual supported workflow |
| E45 | Planned | Later / M | Deterministic text/personalization and CSV merge | Font handling, spelling proof, overflow checks and one-to-one record/output mapping |
| E46 | Planned | Later / M | QR/barcode artwork and separate text overlays | Codes are generated deterministically, protected from destructive dither, and scan-tested physically |
| E47 | Planned | Next / S | Prompt/source provenance: prompt, model/provider if known, source ID, usage notes and edits | Unknown provenance remains unknown; original source is preserved |
| E48 | Planned | Later / M | AI-assisted image diagnosis and recipe suggestions | Suggestions explain their basis, show alternatives and require visual choice; deterministic metrics lead |
| E49 | Planned | Later / M | Agent-friendly plan/inspect/render/verify/replay interface | Same validated engine, stable JSON schema, bounded paths/resources and no laser control |
| E50 | Planned | Later / L | Optional AI source generation/background removal/upscaling adapters | Explicit upload/cost choice, original preservation, model details and reversible accepted changes |
| E51 | Planned | Later / M | Local client/job proof approvals and revision history | Approval identifies exact artifact hash/version; exports cannot silently substitute a later revision |
| E52 | Planned | Later / M | Estimating and batch-production notes | Material/waste/design/machine/packaging costs use entered or measured values with assumptions visible |
| E53 | Planned | Next / S | Content catalog metadata and tested recipe cards | Each idea names prerequisites, source type, output type, tested status, size, and links to real examples |
| E54 | Planned | Later / M | Portable job archive, backup/export and retention controls | Another installation can inspect/replay an archive; customer data can be removed deliberately |
| E55 | Partial: OS matrix/import guard; broader semantics remain | Next / M | Maintain cross-platform CI, strengthen import-policy guard, and add semantic geometry/export checks | Supported Python/OS matrix plus XML/raster semantics verified; static forbidden imports rejected |
| E56 | Planned | Later / S | Local usage research and measurable product outcomes | Observe real tasks; record time-to-export, failed jobs, reproducible reorders and support problems before expanding scope |

**Updated delivery sequence**

| Stage | Current status | Next acceptance boundary |
|---|---|---|
| 1. Harden the demonstrated failure paths | Completed for reviewed F01–F12 and follow-up cases | Preserve regression coverage and qualified recovery claims |
| 1.5. Extract modular monolith | Completed extraction; helper import fixed; broader architecture map deliberately deferred | Preserve compatibility, current behavior and clear dependencies; narrow guard gaps remain documented |
| 2. Reproducible CLI | Planned; recommended next implementation work | Versioned job plan/manifest, source/output identity, result records and inspectable recovery state |
| 3. Visual proofing | Planned | Audition, exact-size/pixel review, framing and selected-candidate export agreement |
| 4. Physical evidence | Unverified; can proceed as a separate workstream | Actual SVG import dimensions/alignment/operations, followed by approved supervised material evidence |
| 5. Professional workspace | Planned | Local UI, user recipes, revisions, accessible operation, archive/export and agent adapter |
| 6. Production expansion | Planned | Layout/personalization/custom geometry/kerf/segmentation tied to observed needs and appropriate validation |

The next software contract should define a versioned job/manifest schema and structured results around the existing validated execution path. A truthful no-output dry-run needs to account for the current planning side effects. Replay must validate source identity and schema/version compatibility; it should not promise identical output across arbitrary future dependency versions.

Keep the next contract bounded: do not bundle manifests, full packaging, UI, nesting and AI providers into one implementation pass. The modularization already provides homes for these features; further architecture-only expansion is not the next user benefit.

Physical SVG import should record the exact software revision or artifact hashes, source/export dimensions, imported dimensions, raster/vector alignment, and observed operation assignments. It establishes app behavior; a supervised proof establishes a different material-result claim. No such evidence is claimed here.

**Verification and release handoff**

For an owner-run full suite from the repository, using the current dependency setup:

```bash
cd /Users/ryanjohnson/Projects/glowforge-it
PYTHONPATH=. uv run --with-requirements requirements.txt python -m pytest -q tests/
PYTHONPATH=. uv run --with-requirements requirements.txt python -m pytest -q --import-mode=importlib tests/
git diff --check
```

These full-suite commands were not run during this document update. `uv` may resolve/install dependencies into its cache. They are listed for later implementation acceptance, not as a request to repeat already supplied results now.

The working tree is still the reviewed artifact, not a committed release. Any later staging/commit must include the untracked package and split tests as well as the launcher and deletion of the old test file; `git diff --stat` alone omits untracked implementation files. Git/release actions remain owner-controlled.

**External reference boundary**

Official sources consulted during the initial review on September 25, 2026 are retained as background, not as newly checked app/device evidence:

- [Glowforge file uploads](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File): raster engraving and SVG/PDF design-file support.
- [Glowforge stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes): vector strokes, fills and operation behavior.
- [Glowforge printable area](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area): nominal dimensions and settings-dependent margins.
- [Glowforge Craft specifications](https://glowforge.com/b/tech-specs/craft): model context; the initially inspected page contained inconsistent material-size entries, so this is not a validated profile database.
- [Glowforge Premium](https://glowforge.com/b/premium) and [workspace tools](https://support.glowforge.com/hc/en-us/articles/34202219245723-The-Glowforge-App-Workspace): initial product-positioning context for prioritizing reproducibility and local proofing.

No account access, live import, device run, remote CI result, customer research, or comparative product trial was performed for this update.
