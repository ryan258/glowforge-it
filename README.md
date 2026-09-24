# Glowforge Image Prep

A local command-line tool for preparing raster artwork for Glowforge engraving. It can normalize image orientation, composite transparency onto white, resize, clean grayscale, apply contrast and sharpening, and convert the result to a 300-DPI Atkinson-dithered PNG. Optional circle and heart masks support coaster artwork; `--svg-cut` also writes an SVG with an embedded raster image and a vector outline.

This is an **artwork preparation tool**, not a laser-control or material-safety system. It does not choose power, speed, focus, passes, or material settings, and it cannot promise a particular burn result. Review every design and operation in the Glowforge app and follow the makerspace’s machine and material procedures.

## Project stock context

The project’s default material context is **medium maple plywood at 1/8 inch**. The CLI prints the stock label and thickness for each batch. Change the descriptive stock name with `--material` and thickness with `--material-thickness` (inches; decimals or fractions such as `0.125` or `1/4`). These values do not alter image processing or select machine settings. Glowforge’s Proofgrade listing describes Medium Maple Plywood as approximately 1/8 inch and Thick as approximately 1/4 inch; local stock labels may differ, so check the actual sheet label and measure before use. Plywood cores and adhesives vary. Confirm compatibility with the supplier and current Glowforge guidance ([material settings FAQ](https://support.glowforge.com/hc/en-us/articles/4605501879963-print-settings-faq), [Maple Plywood listing](https://shop.glowforge.com/products/maple-plywood-finished)).

## Requirements and setup

- Python 3.11 or newer
- `uv` for the `gf` wrapper, or Python with dependencies from `requirements.txt`

The inline script metadata in `main.py` pins NumPy and Pillow for `uv`. For a pip-managed environment:

```bash
python -m pip install -r requirements.txt
```

Optionally install the shell alias:

```bash
chmod +x gf install_alias.sh
./install_alias.sh
```

Reload the shell after installation. The `gf` wrapper invokes `uv run main.py` and enables `--clean-solids`; when running `uv run main.py` directly, that option is off unless requested. Pass `--no-clean-solids` to `gf` to turn the wrapper default off.

## Quick start

Put source images in `input/` and run:

```bash
gf
```

Or process a specific file or folder:

```bash
gf --input input/design.png --preset photo-high-detail -o output
```

For a 4-inch coaster design with a vector cut outline:

```bash
gf --input input/coaster-art.png --preset coaster --svg-cut -w 4 -h 4 --machine performance
```

The tool writes a PNG for engraving and, with `--svg-cut`, a `_cut.svg` sidecar containing the image and a vector outline. Glowforge supports bitmap images for engraving and vector paths for cut/score operations. Inspect the imported SVG in the app, make sure the image and outline are aligned and assigned the intended operations, and review the material/settings before printing ([file upload guidance](https://support.glowforge.com/hc/en-us/articles/360034142453-Upload-Your-Own-Design-File), [stroke behavior](https://support.glowforge.com/hc/en-us/articles/20545971062683-Simplify-Strokes)). Device import and a real material run have not been verified as part of this project.

## Output behavior

- Supported inputs: PNG, JPG/JPEG, BMP, WebP, TIFF, and GIF. For animated GIFs, Pillow processes the first frame.
- Folder inputs are traversed in stable, sorted order and their subfolder structure is mirrored under the output folder.
- PNGs are written at 300 DPI. Without explicit dimensions, pixel dimensions are preserved; with one dimension, the other is scaled proportionally.
- When both dimensions are supplied, `--fit stretch` (default) changes the aspect ratio, `--fit contain` pads with white, and `--fit cover` center-crops.
- Ordinary output is a 1-bit black-and-white PNG. Shape masks need transparency, so circle and heart PNGs use RGBA. `--svg-cut` omits the bitmap outline and draws the cut outline as a vector in the SVG sidecar.
- Output names encode the input basename/extension, preset, and changed image settings. They do not contain an input-content hash or the material label, so different files with the same name can map to the same output path across runs. Existing outputs are overwritten by default; select `--existing skip` or `--existing error` to change that behavior.
- The default per-image pixel limit is 20,000,000 for both source and output. Raise it explicitly with `--max-pixels` only when your machine and available memory can handle the larger image.
- `--machine` checks an approximate nominal area: Performance 19.5 × 11 in, Aura 12 × 12 in, Spark 8.5 × 11 in. The usable area may be smaller depending on the design and print settings; the app is authoritative ([printable-area guidance](https://support.glowforge.com/hc/en-us/articles/21251502058267-Printable-Area), [Craft Series specifications](https://glowforge.com/b/tech-specs/craft)).

## CLI reference

Use `gf --help` (or `uv run main.py --help`) for the current option list. `-h` is retained as the height flag, so help uses `--help`.

| Option | Purpose |
| --- | --- |
| `--input PATH [PATH ...]` | One or more input images or folders; defaults to `input/`. |
| `-o, --output DIR` | Destination folder; defaults to `output/`. |
| `-p, --preset NAME` | Image-preparation preset. Presets do not select material, power, speed, or pass settings. |
| `--material LABEL` | Descriptive stock label shown in the batch log; defaults to `medium maple plywood`. It does not change processing. |
| `--material-thickness IN` | Descriptive stock thickness in inches; default `0.125` (1/8). Accepts decimal or fraction notation such as `0.25` or `1/4`. It does not change processing. |
| `-w, --width IN` / `-h, --height IN` | Target dimension at 300 DPI. One dimension preserves aspect ratio. |
| `--fit MODE` | `stretch`, `contain`, or `cover`; applies when both dimensions are specified. |
| `-b, --black-threshold N` / `-W, --white-threshold N` | Force dark/light grayscale values to solid black/white. Values range from 0 to 255. |
| `-d, --dither-threshold N` | Change the Atkinson midpoint decision boundary. |
| `-c, --clean-solids` / `--no-clean-solids` | Snap near-black and near-white pixels to solids. The `gf` wrapper enables this by default. |
| `--clean-solids-black N` / `--clean-solids-white N` | Set the snapping boundaries. |
| `-i, --invert` / `--no-invert` | Invert grayscale values before dithering. |
| `--denoise N` | Median-filter size; must be odd and at least 3. |
| `--contrast N`, `--sharpen-radius N`, `--sharpen-percent N`, `--sharpen-threshold N` | Adjust image contrast and unsharp masking. |
| `--nb, --no-border` | Omit the default 1-pixel bitmap border. |
| `--circle-cut` / `--heart-cut` | Apply a centered shape mask. The default black bitmap outline engraves; it is not a cut path. |
| `--svg-cut` | With a circle or heart mask, write an SVG sidecar with a vector outline. Review it in the Glowforge app before printing. |
| `--machine MODEL` | Optional nominal bed-area preflight for `performance`, `aura`, or `spark`. |
| `--max-pixels N` | Source/output pixel guard; defaults to 20,000,000. |
| `--existing POLICY` | `overwrite` (default), `skip`, or `error`. For PNG plus SVG, the policy applies to the complete output set. |

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

- [Engraving handbook](docs/handbook.md): pipeline, presets, sizing, cutout and SVG workflow.
- [25 best commands](docs/best-commands.md): examples and what each command actually produces.
- [ELI5 guide](docs/eli5.md): simple explanation of grayscale, dithering, and cut paths.
- [101 project ideas](docs/101-ways-to-make-fun-and-profit.md): inspiration list with explicit notes about what this CLI does and does not create.
- [101 art styles that work surprisingly well](docs/101-art-styles-that-work-surprisingly-well-with-examples.md): AI source-art prompt directions paired with current image-prep starting points.
- [Roadmap and enhancement proposals](docs/UPDATE-IDEAS.md): current state, corrections, and a sequenced product plan.
- [Cow image prompts](docs/cow-prompts.md): optional source-art prompts; generated artwork still needs inspection and fitting.
