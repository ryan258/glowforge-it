# UPDATE-IDEAS — Roadmap to a Comprehensive Tool for Visual Creatives

A review of the current project plus a prioritized catalog of proposed upgrades. Each idea includes a concrete solution proposal, sized honestly. Quick wins first — most of the highest-value items are a few lines of Pillow.

---

## 1. Current State Review

**What exists (and works):**

- `main.py` — single-file CLI: EXIF fix → alpha-composite → grayscale → optional denoise/resize/invert → threshold snapping → contrast → unsharp mask → Atkinson dither → border or circle/heart cutout.
- 17 presets covering materials (wood, acrylic, leather, glass) and styles (photo, AI art, line art, stamp).
- Collision-resistant output filenames encoding the settings used.
- `gf` wrapper script + alias installer, `uv` inline-metadata deps (PEP 723).
- Solid test suite (validators, transparency, EXIF, dithering, golden image, cutout masks) + GitHub Actions CI.
- Good docs: handbook, best-commands, ELI5.

**Honest assessment:** this is a strong single-purpose *preprocessor*. To serve visual creatives more broadly it needs (a) more artistic output styles, (b) faster iteration loops (preview before burning), (c) more shapes/layout tooling, and (d) internal cleanup so the above are cheap to add.

**Code-health findings (fix these first — they make everything else cheaper):**

| # | Finding | Where | Fix |
|---|---------|-------|-----|
| C1 | 17 parameters hand-plumbed through 4 function signatures; every new option touches ~6 places | `transform_image`, `prep_for_glowforge`, `process_directory`, `__main__` | Introduce a `Settings` dataclass (or plain dict) built once from `DEFAULTS ← preset ← CLI args`; pass one object. This single refactor cuts the cost of every idea below. |
| C2 | Filename-tag builder is two nearly identical ~25-line branches (preset vs. no-preset) | `process_directory` lines ~454–507 | One loop over `(flag, tag, baseline)` tuples where baseline = `preset.get(key, DEFAULTS[key])` (empty preset dict when none). Deletes ~40 lines. |
| C3 | Dead branch: the `rel_path` if/else resolves to identical code in both arms | `process_directory` lines ~541–558 | Delete the outer conditional; keep the `os.path.isdir(input_dir)` check only. |
| C4 | Circle and heart cutout are copy-paste twins (mask → putalpha → outline) | `transform_image` lines ~283–341 | One `apply_cutout(img, points_or_ellipse, no_border)` helper; shapes become point-generator functions. This is also the extension point for every new shape (idea S1). |
| C5 | Pure-Python dither loop is O(w·h) interpreted — slow on 300 DPI photos (a 10×8" image is 7.2M pixels) | `transform_image` lines ~249–279 | Keep Atkinson but note the ceiling; offer Pillow's native Floyd–Steinberg (`img.convert('1')`, C-speed, zero code) as an alternate algorithm (idea A1). Numba/Cython only if users actually complain. |
| C6 | CI installs `requirements.txt` via pip while the tool ships PEP 723 inline deps for uv — two dependency sources that can drift | `.github/workflows/ci.yml`, `requirements.txt`, `main.py` header | Use `astral-sh/setup-uv` in CI and run `uv run pytest`; delete `requirements.txt`. One source of truth. |
| C7 | Supported input formats hardcoded to png/jpg/jpeg/bmp | `process_directory` | Add `.webp`, `.tif`, `.tiff`, `.gif` — Pillow already reads them; it's a tuple edit. HEIC via optional `pillow-heif` (idea I3). |

---

## 2. Idea Catalog

Legend: **Effort** S = hours, M = a day-ish, L = multi-day. **Value** is for the target user (visual creatives making laser projects).

### A. Artistic output styles (the biggest creative lever)

| # | Idea | Value | Effort |
|---|------|-------|--------|
| A1 | **Selectable dithering algorithms** — `--dither-algo atkinson\|floyd-steinberg\|ordered\|none`. Floyd–Steinberg is free (`img.convert('1')`, native C). Ordered/Bayer is a tiled threshold matrix — ~10 lines of NumPy, gives a distinct retro-print texture creatives love. `none` = plain threshold for pure stencil looks. | High | S |
| A2 | **Halftone dot screens** — classic newspaper/screen-print look: map local brightness to variable-radius black circles on a grid, optional screen angle. Pure Pillow `ImageDraw` over downsampled cells (~40 lines). Engraves beautifully on wood and acrylic. Add as `--style halftone --halftone-cell 8 --halftone-angle 45`. | High | M |
| A3 | **Line/hatch screens** — brightness → variable line weight or spacing (horizontal, 45°, crosshatch). Same cell-mapping machinery as A2; share the code. Gives an etched/engraved-plate aesthetic. | High | M (with A2) |
| A4 | **Photo → sketch/line-art conversion** — `--style sketch-lines`: `ImageFilter.FIND_EDGES` (or Sobel via `ImageFilter.Kernel`) + invert + autocontrast, then existing pipeline. Turns any photo into engraveable line art in ~5 lines. | High | S |
| A5 | **Auto-levels / histogram equalization** — `--auto-contrast` → `ImageOps.autocontrast(img, cutoff=1)`, `--equalize` → `ImageOps.equalize(img)`. One line each; often better than manual `--contrast` guessing. Fold into presets. | High | S |
| A6 | **Gamma control** — `--gamma 0.8` via a 256-entry LUT + `img.point(lut)`. Midtone control that contrast alone can't do; critical for photo engraves on dark woods. | Med | S |
| A7 | **3D / depth engrave mode** — `--mode grayscale` skips dithering and outputs cleaned, contrast-shaped *grayscale* PNG for Glowforge's "vary power" / 3D engrave. The whole pipeline before step 8 already does the work; just early-return. Unlocks a completely different engraving style for ~10 lines. | High | S |
| A8 | **Duotone / layered-material separation** — split an image into 2–3 tone layers (dark/mid/light) exported as separate 1-bit files, engraved as separate passes at different powers. Threshold at N levels, save N files. Advanced but very "creative pro" feature. | Med | M |

### B. Shapes & cut paths

| # | Idea | Value | Effort |
|---|------|-------|--------|
| S1 | **Generalized shape library** — after C4's refactor, add `--cut-shape circle\|heart\|hexagon\|octagon\|rounded-rect\|oval\|star\|scalloped`. Each shape is just a point-list generator (regular polygons are 3 lines; rounded-rect is `ImageDraw.rounded_rectangle`). Replaces `--circle-cut`/`--heart-cut` (keep as aliases). | High | M |
| S2 | **Custom shape from image mask** — `--cut-shape-file mask.png`: any black-on-white silhouette becomes the cutout mask + traced outline. Mask = threshold the file; outline = `mask.filter(ImageFilter.FIND_EDGES)` composited in black. No SVG parsing needed. | High | S–M |
| S3 | **Vector SVG cut-line sidecar** — emit `name_cut.svg` next to the PNG with the true vector path (circle/polygon/heart points → SVG `<path>`). Glowforge cuts vectors more cleanly than 1px raster rings, and creatives can edit the path in Illustrator/Inkscape. SVG is text — stdlib string formatting, no dependency. | High | M |
| S4 | **Hang-hole punch** — `--hole [top\|top-left\|…] --hole-diameter 0.2`: adds a small unfilled circle inside the shape for ornaments/keychains/tags. A few lines in the cutout helper; pairs with S3 for a vector hole. | High | S |
| S5 | **Score vs. cut distinction** — Glowforge classifies vector strokes by color. In the SVG sidecar (S3), draw cut lines in one color and optional decorative score lines (e.g., inner offset ring) in another: `--score-inset 0.15`. | Med | S (after S3) |
| S6 | **Kerf offset for the cut path** — expand/contract the cut outline by kerf/2 (`--kerf 0.008in`) so finished pieces measure true size. For polygon paths this is simple centroid-scaling; do properly (offsetting) only if users ask. | Med | S–M |

### C. Layout & production (batch makers, market sellers)

| # | Idea | Value | Effort |
|---|------|-------|--------|
| L1 | **Sheet nesting / tiling** — `--sheet 19.5x11 --copies 12` lays processed pieces onto one Glowforge-bed-sized canvas in a grid with configurable gap. Grid math + `Image.paste`. Huge time-saver for coaster/ornament batches; no bin-packing needed for identical pieces. | High | M |
| L2 | **Contact-sheet preset preview** — `gf --audition photo.jpg` runs the image through *all* (or a chosen set of) presets and composites a labeled grid into one preview PNG. Answers "which preset should I use?" without burning material. Loop + paste + `ImageDraw.text`. | High | S–M |
| L3 | **Material test card generator** — `gf testcard` emits a ready-to-engrave grid of dither densities / gradient bars with labels, so users can calibrate power/speed per material once. Pure generation, no input image. | Med | S–M |
| L4 | **Settings sidecar for reproducibility** — write `output/name.json` recording every resolved setting + input hash. The encoded filename already tries to do this; JSON does it losslessly and lets a future `--replay name.json` re-run it. ~10 lines with `json.dump`. | Med | S |
| L5 | **Parallel batch processing** — `concurrent.futures.ProcessPoolExecutor` over the input list. Meaningful once A2/A3 or big photo batches arrive; trivially parallel workload. | Med | S |

### D. Workflow & UX

| # | Idea | Value | Effort |
|---|------|-------|--------|
| W1 | **User-defined presets via config file** — read `~/.config/gf/presets.toml` (stdlib `tomllib`) and merge into `PRESETS`. Creatives accumulate per-material recipes; today they must retype flags. ~15 lines. | High | S |
| W2 | **Watch mode** — `gf --watch`: poll `input/` mtimes every 2s (stdlib loop; skip watchdog dependency), process new files on arrival. Drag-drop workflow with zero terminal round-trips. | Med | S |
| W3 | **Web preview UI** — local single-page app (stdlib `http.server` + one HTML file): drag image, sliders for the main knobs, live before/after at screen resolution. This is the single biggest UX jump for non-terminal creatives, and the biggest build. Do only after the CLI feature set stabilizes; the C1 Settings refactor makes the pipeline callable from it for free. | High | L |
| W4 | **Better terminal output** — `--quiet`, per-file `[3/12]` progress counter, and a final summary line (files, total time, output dir). Replace the current parameter-dump print. Stdlib only. | Med | S |
| W5 | **Proper packaging** — add `pyproject.toml` with a `gf` entry point so `uv tool install glowforge-it` (or pipx) installs it globally; retire `install_alias.sh` and the zsh-only alias hack. Also makes PyPI publishing possible later. | Med | S–M |
| W6 | **Text/monogram overlay** — `--caption "The Johnsons" --caption-font ...`: render text via `ImageFont` before dithering. Personalization (names/dates) is the #1 use case for gift/market makers. | High | M |

### E. Input handling & robustness

| # | Idea | Value | Effort |
|---|------|-------|--------|
| I1 | **More input formats** — add webp/tiff/gif to the extension tuple (C7). Free. | High | S |
| I2 | **Max-dimension guard** — warn (or auto-fit with `--fit-bed`) when output exceeds Glowforge bed size (~19.5×11" ⇒ 5850×3300 px at 300 DPI). Prevents a common silent failure at print time. | Med | S |
| I3 | **HEIC support (iPhone photos)** — optional `pillow-heif`; import guarded by try/except with a helpful message. Creatives shoot reference photos on phones. | Med | S |
| I4 | **Subject isolation / background removal** — optional `rembg` integration behind `--remove-bg` (guarded import, clearly optional in docs — it pulls an ONNX model). Pet-portrait coasters are a massive use case. Not stdlib, but nothing in Pillow does this. | High | M |
| I5 | **Auto-crop borders** — `--autocrop`: `ImageOps.invert(gray).getbbox()` crop to content. One line; removes wasted margin before resize. | Med | S |

---

## 3. Suggested Sequencing

1. **Foundation (do first):** C1 Settings dataclass, C2/C3 dedupe, C4 cutout helper, C6 CI unification, C7+I1 formats. Everything after this gets cheaper.
2. **Quick creative wins (each ≤ a few hours):** A1 dither algorithms, A4 sketch mode, A5 auto-contrast/equalize, A7 grayscale/3D mode, A6 gamma, S4 hang hole, W1 user presets, L4 settings sidecar, W4 output polish, I2 bed guard, I5 autocrop.
3. **Differentiators:** A2/A3 halftone & hatch screens, S1 shape library, S3 SVG cut sidecar, L1 sheet nesting, L2 preset audition, W6 text overlay.
4. **Big bets (validate demand first):** W3 web preview UI, I4 background removal, A8 duotone layers.

## 4. What NOT to build (deliberately skipped)

- **A GUI framework app (Electron/Qt):** the web preview (W3) covers the need at a fraction of the weight.
- **G-code / direct machine control:** Glowforge's cloud owns the machine; PNG+SVG is the correct interface boundary.
- **A plugin system:** presets + config file (W1) cover extensibility; a plugin API is speculative until a second contributor exists.
- **Vectorization/auto-trace (raster→SVG art):** potrace exists and is good; shelling out to it could be a future `--trace` flag, but reimplementing it is a rabbit hole.
- **Numba/Cython dither acceleration:** measure first; Pillow's native Floyd–Steinberg (A1) already gives a C-speed escape hatch for huge images.
