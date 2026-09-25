# Glowforge Image Prep

A local command-line tool for preparing raster artwork for Glowforge engraving. It can normalize image orientation, composite transparency onto white, resize, clean grayscale, apply contrast and sharpening, and convert the result to a 300-DPI Atkinson-dithered PNG. Optional circle and heart masks support coaster artwork; `--svg-cut` also writes an SVG with an embedded raster image and a vector outline.

This is an **artwork preparation tool**, not a laser-control or material-safety system. It does not choose power, speed, focus, passes, or material settings, and it cannot promise a particular burn result. Review every design and operation in the Glowforge app and follow the makerspace’s machine and material procedures.

## Project stock context

The project’s default material context is **medium maple plywood at 1/8 inch**. The CLI prints the stock label and thickness for each batch. Change the descriptive stock name with `--material` and thickness with `--material-thickness` (inches; decimals or fractions such as `0.125` or `1/4`). These values do not alter image processing or select machine settings. Glowforge’s Proofgrade listing describes Medium Maple Plywood as approximately 1/8 inch and Thick as approximately 1/4 inch; local stock labels may differ, so check the actual sheet label and measure before use. Plywood cores and adhesives vary. Confirm compatibility with the supplier and current Glowforge guidance ([material settings FAQ](https://support.glowforge.com/hc/en-us/articles/4605501879963-print-settings-faq), [Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished)).

## Requirements and setup

- Python 3.11 or newer
- `uv` for the `gf` wrapper, or Python with dependencies from `requirements.txt`

The implementation lives in the `glowforge_it/` package; `main.py` is a launcher that carries the inline `uv` script metadata and re-exports the public names, so every command below is unchanged. The inline metadata in `main.py` pins NumPy and Pillow for `uv`. For a pip-managed environment:

```bash
python -m pip install -r requirements.txt
```

## Quick start

From a clean checkout, with no alias installed:

```bash
git clone <this-repo-url> glowforge-it
cd glowforge-it
chmod +x gf
cp /path/to/your-artwork.png input/design.png   # input/ ships empty
./gf --input input/design.png -o output
```

Without `uv`, call the script directly:

```bash
python -m pip install -r requirements.txt
python main.py --input input/design.png -o output
```

`--input` and `-o` are resolved against your **current working directory**, not the
repository. `./gf` with no arguments therefore reads `input/` and writes `output/`
relative to wherever you are standing — which is the repository only if you `cd` there
first. Pass explicit paths when running from anywhere else.

The two entry points differ in one default: `./gf` adds `--clean-solids`, while
`python main.py` leaves it off. Pass `--no-clean-solids` to `gf` to match.
The installed `gf` console command has the same default as `./gf`;
the installed `glowforge-it` command matches `python main.py`.

Optionally install a global `gf` alias (zsh only; for bash or fish, add
`alias gf='<repo>/gf'` to your own shell profile):

```bash
./install_alias.sh
```

Reload the shell afterwards.

For a 4-inch coaster design with a vector cut outline:

```bash
gf --input input/coaster-art.png --preset coaster --svg-cut -w 4 -h 4 --machine performance
```

The tool writes a PNG for engraving and, with `--svg-cut`, a `_cut.svg` sidecar containing the image and a vector outline. Glowforge supports bitmap images for engraving and vector paths for cut/score operations. Inspect the imported SVG in the app, make sure the image and outline are aligned and assigned the intended operations, and review the material/settings before printing ([file upload guidance](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes)). Device import and a real material run have not been verified as part of this project.

## Maker workflow

The six first-version maker features are available: unified operation SVGs, explicit darkening/lightening curves, deterministic maple previews, one-page client proofs, measured single/grid pocket jigs, and placement-preserving trim with LPI-based orientation advice. See the [maker workflow guide](docs/maker-workflow.md) for commands, geometry contracts, recipes, and app/physical acceptance steps.

```bash
./gf --input input/art.png -o output/review --preset coaster -w 4 -h 4 \
  --svg-operations --material-mode darkening --proof-sheet --trim \
  --optimize-orientation --engraving-lpi 225
```

New workflow options automatically include versioned metadata and hashed manifests. The new red-cut/blue-score palette is opt-in; legacy `--svg-cut` stays blue-cut. Glowforge import and physical calibration remain pending. Generate local synthetic review artifacts with `.venv/bin/python scripts/maker_demo.py`.

## Output behavior

- Supported inputs: PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. For animated GIFs, Pillow processes the first frame.
- Folder inputs are traversed in stable, sorted order and their subfolder structure is mirrored under the output folder.
- PNGs are written at 300 DPI. Without explicit dimensions, pixel dimensions are preserved; with one dimension, the other is scaled proportionally.
- When both dimensions are supplied, `--fit stretch` (default) changes the aspect ratio, `--fit contain` pads with white, and `--fit cover` center-crops. `contain` padding is always white, including with `--invert`.
- Ordinary output is a 1-bit black-and-white PNG. Shape masks need transparency, so circle and heart PNGs use RGBA. `--svg-cut` omits the bitmap outline and draws the cut outline as a vector in the SVG sidecar.
- Output names encode the input basename/extension, preset, and changed image settings. They do not contain an input-content hash or the material label, so different files with the same name can map to the same output path across runs. Existing outputs are overwritten by default; select `--existing skip` or `--existing error` to change that behavior.
- Filename preset auto-detection: when no explicit `--preset` is passed on the CLI, files matching `*--[mode].<ext>` (such as `fox--line-art.png` or `owl--photo-soft.png`) automatically apply that recognized preset mode for that job.
- The default per-image pixel limit is 20,000,000 for both source and output. Raise it explicitly with `--max-pixels` only when your machine and available memory can handle the larger image.
- `--dry-run` reports destinations, pixel/physical dimensions, and estimated working memory without writing outputs or creating folders. Add `--json` for a structured plan.
- `--max-memory 500MB` limits a conservative estimate of image working buffers, including simultaneous dither arrays, orientation/compositing copies, and output workspace. It is not a hard limit on total process memory. PNG preflight skips compressed pixels and bounds copied metadata to 1 MiB; unusually large metadata is rejected explicitly.
- `--manifest` writes a companion JSON record with source/output hashes, dimensions, resolved recipe, material context, and optional `--prompt`/`--model` provenance. Source paths are relative to the manifest; keep that directory relationship when moving jobs, or pass `source_path` to the Python verifier.
- Use `--manifest --existing skip` for verified reuse: changed source/output hashes, missing artifacts, and recipe differences fail planning. Without `--manifest`, `--existing skip` checks existence only. `--existing error` is useful for the first trial to avoid replacing an earlier result.
- `--recipe PATH` loads user profile settings from a `.toml` or `.json` file following documented precedence (`defaults -> preset -> recipe -> explicit overrides`).
- `--machine` checks an approximate nominal area: Performance 19.5 × 11 in, Aura 12 × 12 in, Spark 8.5 × 11 in. The usable area may be smaller depending on the design and print settings; the app is authoritative ([printable-area guidance](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area), [Craft Series specifications](https://glowforge.com/b/tech-specs/craft)).

## CLI reference

Use `gf --help` (or `uv run main.py --help`) for the current option list. `-h` is retained as the height flag, so help uses `--help`.

| Option | Purpose |
| --- | --- |
| `--input PATH [PATH ...]` | One or more input images or folders; defaults to `input/`. |
| `-o, --output DIR` | Destination folder; defaults to `output/`. |
| `-p, --preset NAME` | Image-preparation preset. Presets do not select material, power, speed, or pass settings. |
| `--recipe PATH` | Path to custom user recipe profile (`.toml` or `.json`). |
| `--material LABEL` | Descriptive stock label shown in the batch log; defaults to `medium maple plywood`. It does not change processing. |
| `--material-thickness IN` | Descriptive stock thickness in inches; default `0.125` (1/8). Accepts decimal or fraction notation such as `0.25` or `1/4`. It does not change processing. |
| `-w, --width IN` / `-h, --height IN` | Target dimension at 300 DPI. One dimension preserves aspect ratio. |
| `--fit MODE` | `stretch`, `contain`, or `cover`; applies when both dimensions are specified. |
| `-b, --black-threshold N` / `-W, --white-threshold N` | Force dark/light grayscale values to solid black/white. Values range from 0 to 255. |
| `-d, --dither-threshold N` | Change the Atkinson midpoint decision boundary. |
| `-c, --clean-solids` / `--no-clean-solids` | Snap near-black and near-white pixels to solids. The `gf` wrapper enables this by default. |
| `--clean-solids-black N` / `--clean-solids-white N` | Set the snapping boundaries. |
| `-i, --invert` / `--no-invert` | Invert grayscale values (tonal only; legacy mode only). |
| `--nb, --no-border` | Omit the default 1-pixel bitmap border. |
| `--denoise N` | Median-filter size; `0` turns denoising off, otherwise odd and at least 3. |
| `--contrast N`, `--sharpen-radius N`, `--sharpen-percent N`, `--sharpen-threshold N` | Adjust image contrast and unsharp masking. `--sharpen-radius 0` or `--sharpen-percent 0` turns sharpening off, so a preset stage can be explicitly disabled. |
| `--circle-cut` / `--heart-cut` | Apply a centered shape mask. The default black bitmap outline engraves; it is not a cut path. |
| `--svg-cut` | Legacy SVG sidecar with blue cut outline; requires a shape mask. |
| `--manifest` | Emit companion versioned JSON job manifest (`_manifest.json`) adjacent to output. |
| `--dry-run` | Preview planned destinations, dimensions, and memory without writing files or creating folders. |
| `--json` | Emit structured machine-readable JSON batch result summary. |
| `--max-memory SIZE` | Preflight memory budget (e.g. `500MB`, `1GB`) to reject over-budget jobs before pixel allocation. |
| `--prompt TEXT` / `--model TEXT` | Optional AI provenance metadata to record in the job manifest. |
| `--machine MODEL` | Optional nominal bed-area preflight for `performance`, `aura`, or `spark`. |
| `--max-pixels N` | Source/output pixel guard; defaults to 20,000,000. |
| `--existing POLICY` | `overwrite` (default), `skip`, or `error`. For PNG plus SVG, the policy applies to the complete output set. |
| `--svg-operations` | Opt in to unified SVG: embedded monochrome raster, red cuts, blue scores. |
| `--score-marks` | Add an intentional blue L-shaped orientation score at top left. |
| `--material-mode MODE` | Substrate ablation polarity: `darkening` (light wood/substrate) or `lightening` (slate/dark acrylic). |
| `--tone-black N` / `--tone-white N` | Tonal curve clipping boundaries (0–255). |
| `--tone-gamma N` | Tonal gamma exponent (> 0). |
| `--preview-finish` | Emit deterministic simulated maple PNG (`_finish.png`) from the exact burn mask. |
| `--preview-seed N` | Random seed for procedural wood grain (default 0). |
| `--preview-spread-mm N` | Simulated physical dot blur in mm (0–2 mm). |
| `--proof-sheet` | Emit single-page customer approval PDF (`_proof.pdf`) with embedded Vera font and sign-off lines. |
| `--client TEXT` / `--order TEXT` | Client name and order reference for approval proof (max 240 chars each). |
| `--jig SHAPE` | Generate registered pocket jig SVG (`circle` or `rectangle`). |
| `--blank-width IN` / `--blank-height IN` | Measured blank dimensions for jig pocket. |
| `--pocket-clearance IN` | Per-side physical clearance around blank. |
| `--kerf IN` | Full laser cut width compensation. |
| `--jig-margin IN` / `--jig-gap IN` | Margin around jig canvas and gap between pocket blanks. |
| `--jig-rows N` / `--jig-columns N` | Pocket grid counts (1–400 pockets total). |
| `--trim` | Crop empty exterior rows/columns from final burn mask; companion SVG preserves placement. |
| `--optimize-orientation` | Compare 0° and 90° scan rows and bed feasibility; does not rotate artwork. |
| `--engraving-lpi N` | Machine lines per inch for scan row estimation (required with `--optimize-orientation`). |
| `--orientation-constraint MODE` | Orientation lock: `grain` (material grain direction) or `reading` (text legibility). |
| `--version` | Display program version number (`0.2.0rc1`) and exit. |

## Presets

Presets are starting points for image processing only. They are not empirically validated recipes for a specific sheet, Glowforge model, or operation. Make small proof tests and use the machine profile approved by your makerspace.

| Preset | Image use |
| --- | --- |
| `photo-high-detail`, `photo-soft` | Photo/portrait starting points |
| `vector-graphic`, `line-art`, `sketch`, `high-contrast`, `stamp` | Graphics, line work, drawings, or stencil-like art |
| `ai-art`, `ai-art-detailed`, `low-res-enhance` | AI-generated or lower-resolution source cleanup |
| `wood-hard`, `wood-soft`, `acrylic`, `leather`, `glass` | Contrast/sharpening starting points for named art/material workflows; they do not validate material compatibility or machine settings |
| `coaster`, `coaster-heart` | Circle or heart-shaped raster masks |

## Documentation

- [Maker workflow guide](docs/maker-workflow.md): unified SVGs, ablation polarity, maple previews, client proofs, pocket jigs, and trimming/orientation advice.
- [Engraving handbook](docs/handbook.md): pipeline, presets, sizing, cutout, and maker workflow.
- [30 best commands](docs/best-commands.md): examples and what each command actually produces.
- [ELI5 guide](docs/eli5.md): simple explanation of grayscale, dithering, and cut paths.
- [101 project ideas](docs/101-ways-to-make-fun-and-profit.md): inspiration list with explicit notes about what this CLI does and does not create.
- [101 art styles that work surprisingly well](docs/101-art-styles-that-work-surprisingly-well-with-examples.md): AI source-art prompt directions paired with current image-prep starting points.
- [Changelog](CHANGELOG.md): completed milestones, engine hardening, and modularization history.
- [Project roadmap](roadmap.md): prioritized forward delivery plan and next steps.
- [Project review and technical roadmap](docs/project-review.md): architectural assessment, findings F01–F12 disposition, and full enhancement catalog E01–E56.
- [Exploratory ideas backlog](docs/UPDATE-IDEAS.md): candidate features, rendering experiments, and speculative enhancements.
- [Cow image prompts](docs/cow-prompts.md): optional source-art prompts; generated artwork still needs inspection and fitting.
