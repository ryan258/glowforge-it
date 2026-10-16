# Migrating from 0.2.0rc1

The current development version is `0.2.0rc2.dev1`. This is a pre-1.0 API migration, not a compatibility release. Changes already made before the October review are retained; this guide makes the contract explicit.

## Python entry points

Import from the owning package module and pass one settings object:

```python
from glowforge_it.batch import run_batch
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions

result = run_batch(
    ['input/art.png'], 'output/job',
    ProcessingSettings(no_border=True, contrast=1, black_thresh=20, manifest=True),
    width_in=4, max_memory=500 * 1024 * 1024,
    workflow=WorkflowOptions(trim=True),
)
if not result:
    print(result.to_dict())
```

Batch and audition inputs are iterables of filesystem paths. Lists, tuples and generators may contain strings or `os.PathLike` objects such as `pathlib.Path`, for files or folders. The shared planner converts them to filesystem strings once and retains them for discovery, subfolder mirroring and source-directory protection. Progress logging, quiet mode and JSON output do not consume or change the selected inputs. Invalid path elements return planning errors instead of escaping as attribute/type errors.

`prep_for_glowforge(input_path, output_path, settings, ...)` lives in `glowforge_it.export`. `transform_image(open_image, settings, ...)` lives in `glowforge_it.imaging` and returns an image the caller must close. Both validate settings and accept pixel/memory limits. Export validates settings before expanding artifact paths, protects source aliases, snapshots input bytes, and validates every artifact destination. Custom manifest paths must share the output directory. Non-finite grayscale samples and constant images outside a recognized scale fail during pixel processing; see the handbook for supported ranges.

Use canonical fields `black_thresh`, `white_thresh`, `dither_thresh`, `denoise_radius`, and `material_thickness_in` in Python and recipe files. Legacy keyword aliases, the `main.py` re-exports, `process_directory`, `output_geometry`, and `write_svg_cut` have been removed. Resolve settings before calling the API; the optional `preset_name` describes the resolved preset rather than applying one to your settings object.

## Commands and output identity

Install the package to obtain the `gf` and `glowforge-it` commands. The repository wrapper and alias installer were removed. `uv run main.py` remains the script launcher. If an old shell alias shadows an installed command, inspect it with `type -a gf` and update your own shell configuration; no particular line number is assumed.

The `coaster` and `coaster-heart` presets were removed; use `--circle-cut` and `--heart-cut`. Option-specific filename tags were replaced by the `r` plus 12-hex recipe digest. Output paths are not immutable revisions: preserve earlier generations in separate directories or use `--existing error`.

The script launcher and `requirements.txt` pin the main rendering dependencies. A normal package installation uses the supported dependency ranges in `pyproject.toml`. Manifests record the actual Python/library versions and source fingerprint; pin an environment when byte-for-byte reproduction matters. Installing or removing the optional proof dependency changes that fingerprint record conservatively, even for a plain PNG job.

Text, QR, tone-layer and linework exports now require a manifest automatically, as active workflows already do. This applies to CLI and Python exports even if `manifest=False` or `--no-manifest` was supplied. The caller's frozen settings object is unchanged; the resolved job records `manifest: true`. Ordinary PNG and legacy cut-SVG jobs still allow an optional manifest. Regenerate older sidecar sets explicitly with `--existing overwrite` if they lack the required manifest; skip will reject an incomplete set.

## Results, verification and audition

Batch and audition return `BatchResult` containing `JobOutcome` entries. Audition now uses `output_path` and `manifest_path`; candidate recipes remain in its audition JSON. JSON usage errors are structured with exit code 2. Publication cleanup warnings appear on a written item as `cleanup_warnings`; keep the named backup until you have inspected it.

`verify_job_manifest(path)` checks archived source/output hashes. `verify_job_manifest(path, require_current_engine=True)` also requires the recorded engine source, Python and library versions. Manifest-backed skip uses the latter. Older records without runtime identity can still be checked as archives, but must be regenerated explicitly for verified reuse. CLI verification with quiet output is silent on success and keeps failure reasons on stderr; JSON verification returns those reasons in its structured result without stderr output. The manifest is a local integrity record, not a signature or an approval token.

Batch reuse also compares the requested `prompt` and `model`, including `None` when omitted. Repeat the original provenance to reuse an existing record; changing or clearing it requires an explicit overwrite. The optional Python verifier argument `expected_provenance={'prompt': ..., 'model': ...}` performs the same comparison. Ordinary archive verification without that argument continues to check archived hashes without asserting new provenance.

Audition rejects production sidecars instead of ignoring them, and verifies the candidate order, settings, geometry, runtime and sheet hash before reuse. Mixed-renderer comparisons use Python candidate pairs, for example `('dots', ProcessingSettings(render_mode='atkinson'))` and `('solid', ProcessingSettings(render_mode='silhouette'))`; the CLI applies the same explicit renderer override across all named candidate presets.

Audition columns reserve room for labels independently of image aspect ratio. Headers and labels wrap using measured text widths, and the memory budget includes the resulting sheet height before candidate rendering.

Saved auditions now include numbered sheet labels, exact width/height arguments, per-candidate pixel hashes and a source path relative to the published JSON. Export one with `gf --export-audition output/audition/design_audition.json --candidate 2 -o output/selected`, or call `export_audition_candidate(record_path, candidate, output_dir, ...)` from `glowforge_it.batch`. Candidate accepts a 1-based number or exact name. The Python call returns the usual `BatchResult` and accepts `source_path`, resource limits, machine preflight, existing-output policy, dry-run, quiet/JSON and prompt/model options.

Selection requires a current-engine record, the matching contact sheet and matching source bytes. A moved source can be supplied explicitly; old records lacking exact export data must be regenerated. The production PNG is checked against the saved full-resolution pixel hash and always gets a manifest, including `recipe.audition_pixels_sha256`. Recorded settings and dimensions are restored without preset inference or entry-point defaults; CLI rendering and sidecar overrides are rejected. The audition JSON's `selected_preset` stays unchanged: export is not an approval action.

Tone layers cannot be combined with finish previews or PDFs. Jig jobs currently reject text/QR, tone layers and linework. These combinations need explicit material assignments or replication support before they can be represented honestly.
