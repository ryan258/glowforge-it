# October review remediation

Status: implemented, including the five follow-ups and the additional review corrections below. Version `0.2.0rc2.dev1`. The full test suite and uv-based isolated wheel/source-distribution checks pass on this combined revision. Pass counts are not recorded here (they go stale); run the commands below, or read CI. The stdlib venv/pip fallback and the remote CI matrix have no recorded result.

## Five follow-up corrections

| Finding | Behavior and focused coverage |
|---|---|
| Non-finite float grayscale could become an all-black successful export | Reject NaN/infinity before normalization and reject constant images without a recognized scale; production and audition failures preserve the previous generation without numeric warnings |
| New sidecars could omit manifests and reuse corrupt files | Text, QR, tone layers and linework require a manifest in planning and direct/batch export, even with an explicit false manifest setting; unchanged reuse succeeds, tampered or missing companions fail; legacy PNG/cut jobs retain optional manifests |
| Narrow audition artwork clipped labels and headers | Consistent-width image/label columns, measured wrapping for long names and headers, and sheet geometry included in memory preflight before candidate rendering; tests assert text stays inside the sheet without overlapping |
| Skip silently retained different prompt/model provenance | Manifest-backed skip rejects changed or cleared provenance without modifying files; matching provenance reuses, explicit overwrite records the requested values, archive hash verification remains independent |
| Direct export expanded invalid artifact counts before validation | Shared artifact-settings validation runs before path expansion; invalid types and excessive layer counts fail without creating output directories or altering sources |

These regressions live in `tests/test_review_followups.py`. Header-only dry-run checks geometry, destinations and resource estimates; it does not decode source samples or prove final visual quality. Documentation tests check flags and runnable dry-run examples, not successful rendering or app acceptance.

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
| Documentation and installed-package confidence drifted | Migration guide, corrected examples/semantics, tracked checklist, clean wheel/sdist smoke script and CI job | Full test suite and isolated installed commands/proof dependency checks pass on the combined revision |

## Verify

```bash
.venv/bin/python -m pytest -q                      # full suite
uv pip install -p .venv/bin/python build &&
  .venv/bin/python scripts/check_distribution.py   # wheel + sdist, installed outside the checkout
node .gitnexus/run.cjs analyze                     # refresh the code graph once edits settle
node .gitnexus/run.cjs detect-changes --scope all --repo .   # before any explicitly authorized commit
```

The distribution check builds a wheel and source archive, installs each outside the checkout (uv when available, otherwise stdlib venv/pip), exercises both console commands, confirms ordinary workflows without ReportLab, checks the missing-proof error, installs the proof extra and verifies a generated job. It downloads dependencies into temporary environments and publishes nothing. Graph output marked partial or truncated is not a clean check.

## Still open

- Inspect newly generated proof PDFs, finish previews and SVGs visually after automated validation; earlier sample files do not validate this revision.
- Record actual Glowforge import/grouping, physical dimensions, QR readability, pocket fit, repeat placement and material appearance using the [first-burn checklist](first-burn-checklist.md). These require app/device observations.
- Select a distribution license as an owner decision before public release. No license has been invented or applied by this remediation.
- Multi-process locking, crash-proof immutable bundles, portable archives and signed approval remain future work. Use one writer per destination set. Hash verification is not tamper-proof approval.
- Per-job estimates are conservative planning bounds, not hard RSS limits or a multi-worker scheduler. Profiling is required before promising memory/performance levels.
- A curated photographic/line-art fixture pack, 1:1 inspection, crop anchors, mirroring, accessible UI, watch folders, general nesting, richer vector shapes and batch personalization remain roadmap work. Direct selected-candidate export is now a separate implemented slice with targeted coverage in `tests/test_audition_selection.py`; broader software/distribution and app/physical gates remain open.

See [roadmap.md](../roadmap.md) for the full enhancement inventory and acceptance gates.
