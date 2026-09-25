# Exploratory Ideas & Future Backlog

This document serves as an **idea incubator and speculative backlog** for `glowforge-it`. It gathers potential features, advanced algorithms, and workflow enhancements that may be explored later down the road.

> **Navigation:**
> * **Active Roadmap:** For prioritized, committed work and immediate next steps, see [roadmap.md](../roadmap.md).
> * **Completed Work:** For historical releases and implemented fixes, see [CHANGELOG.md](../CHANGELOG.md).
> * **Project Review:** For the complete audit and disposition of findings F01–F12 and enhancements E01–E56, see [project-review.md](project-review.md).

---

## Evaluation Criteria for Backlog Ideas

Ideas in this document are **uncommitted**. Before any idea moves from this backlog into [roadmap.md](../roadmap.md), it must demonstrate:
1. **Clear Maker Value:** Solves a real problem in artwork preparation, proofing, or repeatability.
2. **Deterministic Output:** Maintains local-first processing and reproducible mathematical behavior.
3. **Bounded Complexity:** Avoids excessive dependencies, unmanageable binaries, or hardware-specific assumptions.
4. **Appropriate Boundary:** Does not attempt to replace the Glowforge web application or make unsupported physical burn promises.

---

## 1. Advanced Artistic & Rendering Algorithms

These ideas explore alternative visual styles beyond the default Atkinson error diffusion.

### Variable-Cell Halftone Screens
* **Concept:** Convert grayscale continuous tones into variable-diameter circular dots arranged in a grid with configurable cell frequency (lines per inch / LPI) and screen angle (e.g., 45°).
* **Potential Value:** Produces a retro print / comic book aesthetic; avoids dither speckling in broad flat areas.
* **Risks & Open Questions:** Small halftone dots can close up or burn through on wood due to laser beam kerf and charring. High frequencies may cause aliasing. Needs physical proofing before wide use.

### Texture & Hatching Algorithms
* **Concept:** Map tone levels to directional line hatching, cross-hatching, woodcut woodgrain flow, or contour-following vector strokes.
* **Potential Value:** Distinctive hand-drawn / engraved print appearance that cuts cleanly on wood without looking like a digital bitmap.
* **Risks & Open Questions:** Vector hatch generation requires path generation and dense line handling. Raster hatch can suffer from moiré artifacts at non-integer scale factors.

### Sketch & Edge-Extraction Modes
* **Concept:** Integrate local edge-detection algorithms (Sobel, Canny, or difference-of-Gaussians) to automatically convert photographs into clean black-and-white coloring-book or line-art illustrations.
* **Potential Value:** Gives makers a 1-step route from personal photos to clean vector/raster line engravings.
* **Risks & Open Questions:** Naive edge detectors amplify photographic sensor noise, texture in clothing, and background clutter. Requires significant parameter tuning to avoid messy outputs.

### Multi-Tone Registered Layer Separation
* **Concept:** Deconstruct a grayscale artwork into 2 or 3 distinct registered 1-bit layers (e.g., deep engrave, light engrave, score outline).
* **Potential Value:** Allows makers to achieve 3D relief engraving or varying contrast depths on wood by setting distinct laser power/speed passes per layer in the Glowforge app.
* **Risks & Open Questions:** Requires explicit registration marks and manual operation mapping in the Glowforge web app. Cannot automate laser settings.

### Alternative Dither Algorithms
* **Concept:** Add selectable error-diffusion algorithms (Floyd–Steinberg, Burkes, Stucki, Jarvis–Judice–Ninke, Sierra) and ordered Bayer dither matrices.
* **Potential Value:** Lets advanced users fine-tune dot clustering for different wood grains and densities.
* **Risks & Open Questions:** Atkinson was chosen specifically because its 3/4 error distribution resists shadow dot-gain on laser engravers. Other algorithms often produce overly dense shadows on wood.

### Parametric Curves, Levels & Auto-Equalization
* **Concept:** Interactive tonal curve shaping (spline curves, gamma adjustment, automated black/white point clipping).
* **Potential Value:** Greater control over midtone contrast and shadow detail before dithering.
* **Risks & Open Questions:** Difficult to use effectively through CLI flags alone; best deferred until a visual proofing interface ([roadmap.md Stage 3/5](../roadmap.md)) is available.

---

## 2. Vector Geometry & Physical Fabrication

These concepts relate to cutline geometry, multi-part assembly, and machine-bed layout.

### Custom SVG Cutlines & Vector Tracing
* **Concept:** Allow users to provide their own SVG cutline to frame raster art, or embed an automatic vector tracer (e.g., `potrace`) to generate tight silhouette cutlines around subject art.
* **Potential Value:** Eliminates the constraint of standard circle and heart cutouts.
* **Risks & Open Questions:** Bitmap contour tracing frequently generates double strokes, microscopic kinks, or open loops that burn poorly. Strict vector path sanitization and preview are mandatory.

### Parametric Shape Library
* **Concept:** Expand built-in shapes to include rounded rectangles (with configurable corner radii), ovals, regular polygons (hexagons, octagons), stars, and scalloped-edge roundels.
* **Potential Value:** Provides ready-to-cut framing for coasters, plaques, badges, and ornaments without requiring external vector design software.
* **Risks & Open Questions:** Each shape requires verified mathematical coordinate alignment between the raster mask canvas and SVG cut paths across odd/even pixel dimensions.

### Measured Kerf Offset Compensation
* **Concept:** Automatically offset vector cutlines outward (or inward) by half the measured laser beam width (kerf, typically 0.005"–0.008") to allow tight press-fit joinery and inlays.
* **Potential Value:** Essential for woodworking joinery, boxes, and multi-wood inlay art.
* **Risks & Open Questions:** Kerf varies across material species, moisture, thickness, laser focus, and speed. True geometric polygon offsetting requires robust clipping to avoid self-intersecting loops and inverted corners.

### Sheet Nesting & Multi-Part Arranger
* **Concept:** 2D bin-packing algorithm that arranges multiple cropped artwork pieces onto a standard material sheet (e.g., 12" × 20") with configurable spacing, margin constraints, and grain direction rules.
* **Potential Value:** Maximizes material utilization for makers running small production batches.
* **Risks & Open Questions:** High algorithmic complexity. Many makers prefer manual layout in Inkscape, Illustrator, or directly inside the Glowforge workspace camera view.

### Passthrough Continuous Feed Slicing
* **Concept:** For Glowforge Pro owners, automatically segment extra-long artworks (>20") into overlapping pages with printed registration marks for continuous passthrough feeding.
* **Potential Value:** Simplifies producing signs, skateboards, and large panels.
* **Risks & Open Questions:** Hardware-specific to Glowforge Pro. Alignment relies heavily on manual physical jigging and camera alignment in the vendor app.

### Mounting Hardware Geometry
* **Concept:** Option to automatically add vector hang holes (with configurable hole diameter and edge distance), ribbon slots, or interlocking easel tabs to cutlines.
* **Potential Value:** Turns flat engravings directly into hangable ornaments, keychains, or freestanding desk plaques.
* **Risks & Open Questions:** Requires strict wall-thickness rules so the wood does not crack under laser heat or physical use.

---

## 3. AI & Smart Workflow Experiments

Ideas focused on intelligent pre-processing while maintaining local execution.

### Local AI Background Removal
* **Concept:** Integrate an on-device neural network (such as `rembg` / `u2net` via ONNX Runtime) to strip complex backgrounds from subject photos before compositing over white.
* **Potential Value:** Dramatically speeds up portrait and pet engraving preparation by eliminating manual Photoshop / GIMP cutout steps.
* **Risks & Open Questions:** Adds large binary dependencies (~150MB+ model weights, native C++ ONNX runtime). Neural segmentations can produce fuzzy edges or miss fine hair strands, which dither poorly. Must remain strictly opt-in and local.

### Pre-Engrave Artwork Diagnostics
* **Concept:** Run automated heuristics against source artwork to flag potential engraving pitfalls:
  * Insufficient contrast or crushed dark tones.
  * Fine text or thin lines below the laser resolution threshold (<0.01").
  * Muddy midtones likely to turn into solid black blotches.
  * Severe JPEG compression blocking.
* **Potential Value:** Catches disappointing burns on screen before expensive wood is wasted.
* **Risks & Open Questions:** Heuristics can produce false warnings on intentional artistic styles (e.g., moody low-key portraits).

### Prompt-to-Recipe Advisor
* **Concept:** A rule-based or lightweight local classifier that inspects source artwork metadata or image features and suggests the best starting preset (`photo-high-detail`, `stamp`, `sketch`, `dark-surface`).
* **Potential Value:** Helps beginners select good starting parameters without trial-and-error.
* **Risks & Open Questions:** Visual preview and human judgment are usually faster and more reliable than automated suggestions.

---

## 4. Production, Business & Personalization Utilities

Features for makers running small businesses or handling client commissions.

### CSV-Driven Batch Personalization
* **Concept:** Read a CSV file (e.g., list of wedding guest names, table numbers, or employee awards) and generate customized batches of engraved place cards or tags using a template image and local TrueType/OpenType font rendering.
* **Potential Value:** Huge time-saver for makers selling personalized wedding favors, badges, or corporate gifts.
* **Risks & Open Questions:** Requires robust font discovery, text wrapping, overflow detection, and license management.

### Protected Vector QR & Barcode Generation
* **Concept:** Deterministically generate vector QR codes, WiFi access codes, or serial barcodes and composite them onto artwork as crisp, un-dithered shapes.
* **Potential Value:** Allows making scannable restaurant menu stands, desk signs, and inventory tags.
* **Risks & Open Questions:** Dithering destroys barcode scannability; codes must be rendered as clean binary vectors or pure solid rectangles. Requires physical barcode scanner testing across materials.

### Material Yield & Job Costing Estimator
* **Concept:** Calculate material surface area used, waste percentage, and approximate laser run time based on pixel counts and path lengths to calculate suggested retail prices.
* **Potential Value:** Helps hobbyists transition into profitable small-batch craft businesses.
* **Risks & Open Questions:** Cannot accurately predict Glowforge laser motion times without proprietary firmware acceleration profiles.

### Production Watch Folder Mode (`--watch`)
* **Concept:** Run as a local background daemon watching an `input/` folder, automatically processing new images as they are saved from Photoshop, Procreate, or Midjourney.
* **Potential Value:** Seamless integration into a designer's daily workflow.
* **Risks & Open Questions:** Partial file writes, operating system file-lock semantics, and duplicate events require debounce logic and atomic state tracking.

---

## 5. Formats & System Platform Options

### Direct HEIC / HEIF Photo Import
* **Concept:** Allow importing iPhone HEIC photos directly without prior manual export to JPEG or PNG.
* **Potential Value:** Convenience for mobile and Mac users.
* **Risks & Open Questions:** Requires `pillow-heif` or `libheif` native system libraries, which complicate cross-platform installation and binary distribution.

### Multi-Page PDF & Animated GIF/TIFF Frame Selector
* **Concept:** CLI options to select specific pages or frames from multi-frame inputs (`--page 2`, `--frame 12`).
* **Potential Value:** Handles customer-supplied PDF vector/raster sheets or animated GIF source assets.
* **Risks & Open Questions:** Niche utility; most creators export single flattened images.

### Embedded ICC Color Profile Management
* **Concept:** Parse embedded ICC profiles and transform images to linear grayscale space before tonal manipulation.
* **Potential Value:** Technically rigorous color science pipeline.
* **Risks & Open Questions:** High mathematical complexity with negligible visible difference once artwork is reduced to a 1-bit dithered pattern engraved on biological wood grain.
