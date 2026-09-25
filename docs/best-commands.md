# 25 Useful Commands for Glowforge Image Preparation

These examples prepare image files; none selects laser power, speed, focus, passes, or an approved stock profile. The project defaults to the stock label **medium maple plywood** at **1/8 inch**. `--material` and `--material-thickness` change the batch’s descriptive stock context only. Confirm the actual sheet and makerspace settings before printing.

Use the installed `gf` wrapper, `./gf`, or `uv run main.py`. The wrapper enables `--clean-solids` by default; use `--no-clean-solids` to turn it off.

## 1. Everyday and batch workflows

### 1. Process the input folder

```bash
gf
```

Processes supported images in `input/`, mirrors subfolders into `output/`, and uses the balanced default image settings plus the wrapper’s clean-solids option. Same settings reuse the same output name, so the default policy overwrites; choose `--existing skip` or `--existing error` when needed.

### 2. Prepare one file

```bash
gf --input input/yggdrasil.png
```

Reads only that source file. The resulting PNG is a raster engraving image, not a complete cut layout.

### 3. Separate a client batch

```bash
gf --input input/projects/acrylic_signs -o output/projects/acrylic_processed
```

Keeps the source batch separate and mirrors subfolders. The `acrylic` name in the folder and preset describes the intended art workflow; it does not confirm that a particular plastic is laser-compatible.

## 2. Coasters and vector outlines

### 4. Circular coaster engraving PNG

```bash
gf --input input/coaster.png --preset coaster -w 4 -h 4
```

Makes a 4 × 4 inch canvas at 300 DPI, applies a centered circular transparency mask, and includes a 1-pixel bitmap edge by default. The edge is part of the engraving image; PNG bitmap lines do not become cuts.

### 5. Circle plus vector outline sidecar

```bash
gf --input input/coaster.png --preset coaster --svg-cut -w 4 -h 4
```

Writes the PNG and a sibling `_cut.svg` that embeds the engraving image and includes a vector circle. Upload and inspect the SVG in the Glowforge app; confirm the art and path are aligned and assigned to the intended operations before printing. Pin both dimensions for a round canvas. A shape mask does not nest multiple pieces or provide kerf compensation.

## 3. Maple plywood image starting points

### 6. Label a maple plywood batch

```bash
gf --input input/maple-art.png --preset wood-soft --material "medium maple plywood" --material-thickness 1/4
```

This records “medium maple plywood” at a nominal 1/4 inch in the batch log and applies the `wood-soft` image preset (contrast 1.4, white threshold 245, denoise 3). Use this thickness only if it matches the actual sheet. The default thickness is 1/8 inch; fractions and decimals are accepted. Stock labels vary, and this label has no effect on pixels or machine settings.

### 7. Compare a second contrast starting point

```bash
gf --input input/maple-art.png --preset wood-hard
```

This applies contrast 1.7, black threshold 10, and sharpen radius 2. Compare the resulting preview with `wood-soft` using a small proof on the actual material; preset names are not verified burn outcomes.

### 8. Push near-black source values to solid black

```bash
gf --input input/logo.png --preset wood-hard -b 15
```

The black threshold changes grayscale values at or below 15 to solid black before dithering. Inspect fine type and narrow gaps at final size; hard thresholds can fill them in.

## 4. Photos and portrait artwork

### 9. Detailed photo starting point

```bash
gf --preset photo-high-detail
```

Uses denoise 3, contrast 1.8, sharpen radius 1.5, and sharpen percent 200. It can help bring out source detail but may also exaggerate noise; inspect before choosing a material test.

### 10. Softer portrait starting point

```bash
gf --preset photo-soft
```

Uses contrast 1.2 and modest sharpening (radius 1, percent 100). Compare several crops or settings when faces are important; the preset cannot guarantee a particular skin or wood tone.

### 11. Low-resolution source cleanup

```bash
gf --preset low-res-enhance
```

Applies denoise 3, contrast 1.6, and stronger sharpening (radius 1.5, percent 220). It changes the source; it does not reconstruct missing detail.

## 5. AI artwork cleanup

### 12. AI-art starting point

```bash
gf --input input/ai-art.png --preset ai-art
```

Uses median denoise 3, clean-solids snapping, contrast 1.6, and sharpening. Review gradients and small facial or typographic details after conversion.

### 13. Change the snapping boundaries

```bash
gf --input input/ai-art.png --preset ai-art-detailed --clean-solids-black 45 --clean-solids-white 215
```

Uses denoise 5 and the detailed preset; the CLI overrides the clean-solids boundaries to 45 and 215. Aggressive snapping can erase shadow detail or turn pale texture completely white, so compare the output to the source.

## 6. Artwork for other materials

These examples select pixel-processing presets only. Verify the exact material with the manufacturer and makerspace before laser use; similarly named materials can have different cores, coatings, or adhesives.

### 14. Acrylic artwork contrast

```bash
gf --input input/acrylic-art.png --preset acrylic
```

Applies clean-solids snapping, contrast 2, and sharpening. It does not identify acrylic type, configure a laser, or guarantee against melting.

### 15. Leather artwork

```bash
gf --input input/leather-art.png --preset leather
```

Uses contrast 1.3, denoise 3, sharpen radius 1, and percent 120. Confirm the specific leather is compatible with the machine; the preset does not determine tanning chemistry.

### 16. Glass artwork

```bash
gf --input input/glass-art.png --preset glass
```

Applies contrast 1.9 and sharpening. Confirm the model’s capabilities and the shop procedure for the glass before use.

### 17. Reverse stamp artwork

```bash
gf --input input/stamp-art.png --preset stamp -i
```

Inverts the grayscale values first, then snaps near-black below 60 and near-white above 190 to solid values (these are the `--clean-solids` boundaries, not the `-b`/`-W` hard thresholds), then applies contrast 3, then dithers. `-i` is a tonal flip only: for a stamp that prints the right way round, mirror the art horizontally in an image editor before running this. This prepares a visual pattern only; the tool does not create a cut/relief layout or validate stamp material settings.

## 7. Graphic and line-art processing

### 18. Raster logo cleanup

```bash
gf --input input/logo.png --preset vector-graphic
```

Snaps near-solid grayscale values, applies contrast 2, and dithers remaining tones. If you need editable vector paths or cuts, provide vector artwork through a vector editor; this command does not vectorize the source.

### 19. Scanned line art

```bash
gf --input input/drawing.png --preset line-art
```

Uses clean-solids, contrast 2.5, and black threshold 20. Inspect paper texture and thin strokes; thresholding may remove faint marks.

### 20. Pencil sketch

```bash
gf --input input/sketch.png --preset sketch
```

Uses contrast 1.3 and sharpening tuned for faint details. The final binary pattern depends on source quality and can be compared at a few dither thresholds.

### 21. High contrast without a bitmap edge

```bash
gf --input input/panel.png --preset high-contrast --no-border
```

Uses clean-solids, thresholds, and contrast 2.5, while omitting the automatic outer bitmap border. It does not create a vector outline.

## 8. Tuning individual controls

### 22. Invert grayscale values

```bash
gf --input input/design.png --invert
```

Swaps light and dark source values before dithering. Preview the output; a visual inversion does not guarantee the intended material mark.

### 23. Stronger median denoise

```bash
gf --input input/photo.jpg --denoise 5
```

Applies a 5 × 5 median filter before resizing and dithering. Larger filters remove more small features as well as noise.

### 24. Sharpening comparison

```bash
gf --input input/line-art.png --sharpen-percent 200 --sharpen-radius 1.5
```

Overrides sharpening for that run. Compare at final physical size because excessive sharpening can add halos and close small gaps.

### 25. Compare dither thresholds

```bash
gf --input input/photo.jpg --dither-threshold 115
```

Changes how the Atkinson algorithm classifies midtone values. It changes the image pattern, not laser power or material response. Make several outputs and compare them before deciding which one to test.

## Material and machine check

The CLI can optionally check an approximate nominal bed size with `--machine performance`, `--machine aura`, or `--machine spark`. The Glowforge app may offer less usable area for a specific print step, so treat this as an early warning rather than a guarantee. Confirm dimensions, stock, operations, and machine settings in the app. See the [handbook](handbook.md) for output behavior and the [roadmap](UPDATE-IDEAS.md) for proposed enhancements.
