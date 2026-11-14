# Review remediation

## Validation record

| Revision | Recorded evidence | Open checks |
| --- | --- | --- |
| October 16, 2026, documentation snapshot `35356d0` | The October record reports local full-suite and uv-based wheel/sdist checks for the remediation baseline. It also records targeted selected-audition coverage. | Exact build fingerprints for the full and distribution runs, fallback venv/pip results, and remote CI results remain unrecorded here. |
| November 12, 2026, working-tree fixes based on `35356d0` | Focused local checks cover interrupted publication and retry, path and manifest protection, exact audition reuse, TIFF geometry, renderer edge cases, the launcher and import hierarchy. The README workflow runs from dry-run through audition, selected export, and current-engine manifest verification. Checks used Python 3.13.1, NumPy 2.5.3, and Pillow 12.3.0. | Full-suite and new distribution checks, visual review of new artifacts, Glowforge app import, and physical samples remain pending. |

## Five follow-up corrections

| Finding | Behavior and focused coverage |
|---|---|
| Non-finite float grayscale could become an all-black successful export | Reject NaN/infinity before normalization and reject constant images without a recognized scale; production and audition failures preserve the previous generation without numeric warnings |
| New sidecars could omit manifests and reuse corrupt files | Text, QR, tone layers and linework require a manifest in planning and direct/batch export, even with an explicit false manifest setting; unchanged reuse succeeds, tampered or missing companions fail; legacy PNG/cut jobs retain optional manifests |
| Narrow audition artwork clipped labels and headers | Consistent-width image/label columns, measured wrapping for long names and headers, and sheet geometry included in memory preflight before candidate rendering; tests assert text stays inside the sheet without overlapping |
| Skip silently retained different prompt/model provenance | Manifest-backed skip rejects changed or cleared provenance without modifying files; matching provenance reuses, explicit overwrite records the requested values, archive hash verification remains independent |
| Direct export expanded invalid artifact counts before validation | Shared artifact-settings validation runs before path expansion; invalid types and excessive layer counts fail without creating output directories or altering sources |

These regressions live in `tests/test_review_followups.py`. Header-only dry-run checks geometry, destinations and resource estimates. The documentation tests exercise flags, dry-run examples and the synthetic README quick start. Record app observations and physical results separately.

## Additional review corrections

| Finding | Behavior and targeted coverage |
|---|---|
| High-bit-depth normalization lost PNG color-key transparency | Build alpha from original samples before scaling; preserve opaque neighboring shades that quantize to the same gray. Real 16-bit PNGs cover black, midrange and white keys across legacy, darkening and lightening modes, plus production/audition no-engrave results |
| Quiet manifest verification hid failure diagnostics | Successful quiet verification remains silent; missing, malformed, modified-output and current-engine failures retain stderr reasons, while JSON keeps structured errors without stderr |
| Path objects and generators behaved differently from string lists | Shared discovery materializes filesystem strings once. Mixed path generators work with normal, quiet and JSON logging in rendering and dry-run; directory generators retain mirroring and rejection of outputs inside source trees; invalid elements return planning errors |

These regressions live in `tests/test_review_corrections.py`. No full-suite, distribution, app-import or physical-result gate is closed by these focused checks.

## Corrections and evidence to collect

| Finding | Implementation | Coverage |
|---|---|---|
| Source changes could disconnect rendered pixels from recorded source/proof | Private disk snapshot shared by all renderers, layers, source panel and manifest; planning hash and prepublication checks | Source mutation preserves prior complete generation |
| Primary-only trimming could erase tone layers or reposition marks | Place all masks on original canvas, then crop to shared bounds; preserve QR quiet zone | Pixel-exact tone crops, shared offsets, QR margin retention |
| Stamp and QR validated independently | Combined occupancy across primary, tone layers and text before QR placement | Text/QR quiet-zone overlap rejection |
| Preview and no-engrave omitted personal marks | Union-based review mask and job status; proof warns about separate imports | Personalization changes preview hash and no-engrave state |
| Unsupported sidecars appeared valid in jigs/auditions | Reject combinations that are not represented/replicated; reject layer material simulation | Preflight fails without artifacts |
| Resource estimates missed expanded/retained buffers | Shared renderer-aware budgets, rotated pixel ceiling, vector point/path bounds, glyph-size guard, bounded audition count/sheet | Fail before heavy allocation; direct API matches planning |
| Direct APIs could overwrite source or bypass validation | Source/inode alias checks across all artifacts; settings/size/budget validation; adjacent manifests | Same-path/hardlink/symlink protection and invalid-input failures |
| Cleanup failure reported an already-published generation as failed | Return successful write with backup cleanup warnings | New outputs and retained backups coexist with written status |
| JSON usage errors escaped the result contract | JSON-aware argument parser and validation error result | Invalid flag, invalid value, missing recipe and workflow failures |
| Reuse lacked current implementation/runtime identity | Engine version, source fingerprint, Python and library versions; archive/current-engine verification modes; audition reuse validation | Old-engine archive still verifies while skip refuses reuse |
| Documentation and installed-package confidence drifted | Migration guide, corrected examples/semantics, tracked checklist, clean wheel/sdist smoke script and CI job | Check installed commands and optional proof dependencies with the distribution script. Use the revision record above for historical results. |

## Verify

```bash
.venv/bin/python -m pytest -q                      # full suite
uv pip install -p .venv/bin/python build &&
  .venv/bin/python scripts/check_distribution.py   # wheel + sdist, installed outside the checkout
node .gitnexus/run.cjs analyze                     # refresh the code graph once edits settle
node .gitnexus/run.cjs detect-changes --scope all --repo .   # before any explicitly authorized commit
```

The distribution check builds a wheel and source archive, installs each outside the checkout (uv when available, otherwise stdlib venv/pip), exercises both console commands, confirms ordinary workflows without ReportLab, checks the missing-proof error, installs the proof extra and verifies a generated job. It downloads dependencies into temporary environments. The source archive includes documentation, examples, developer scripts, test helpers and fixtures so checkout workflows can be inspected there. Rerun incomplete graph checks before relying on them.

## Still open

- Generate a fresh verified [synthetic acceptance pack](first-burn-checklist.md#generate-the-synthetic-acceptance-pack). Inspect its proof PDF, finish PNG, and SVGs visually and record which exact artifacts you opened.
- Record actual Glowforge import/grouping, physical dimensions, QR readability, pocket fit, repeat placement and material appearance using the [first-burn checklist](first-burn-checklist.md). These require app/device observations.
- Select a distribution license as an owner decision before public release. No license has been invented or applied by this remediation.
- The [recovery procedure](handbook.md#recover-an-interrupted-publication) covers one job after a process interruption. POSIX advisory locking coordinates publication and recovery in the same directory. Whole-job coordination during rendering and lock behavior on network filesystems remain open. Immutable bundles, portable job archives, and signed approval remain future work.
- Per-job estimates are conservative planning bounds, not hard RSS limits or a multi-worker scheduler. Profiling is required before promising memory/performance levels.
- A curated photographic/line-art fixture pack, 1:1 inspection, crop anchors, mirroring, accessible UI, watch folders, general nesting, richer vector shapes and batch personalization remain roadmap work. Direct selected-candidate export is now a separate implemented slice with targeted coverage in `tests/test_audition_selection.py`; broader software/distribution and app/physical gates remain open.

See [roadmap.md](../roadmap.md) for the full enhancement inventory and acceptance gates.
