# 25 Best Commands for Glowforge Engraving

This guide details the top 25 command configurations for the Glowforge Image Optimizer. It covers exact command syntaxes, specific use cases, step-by-step explanations of what the parameters do, and the rationale for why each configuration is optimal for its respective application.

---

## How to Run These Commands
- If you have installed the global alias, you can run them using `gf`.
- Alternatively, you can run them using `./gf` or `uv run main.py`.

---

## Category 1: Standard & Batch Processing

### 1. Default Batch Optimization
```bash
gf
```
* **Use Case:** Initial pass optimization of all images in the `input/` folder using default balanced settings.
* **What it Does:** Processes every image in `input/` using a contrast multiplier of `1.5`, unsharp mask sharpening (`150%` intensity at `2.0` radius), 1px solid black border, and `--clean-solids` enabled. Saves output in `output/`.
* **Why it Fits:** Gives a balanced starting point for a mix of photos and graphics to evaluate their dither pattern.

### 2. Single Design Processing
```bash
gf --input input/yggdrasil.png
```
* **Use Case:** Processing a single specific file instead of running a batch process on the entire `input/` folder.
* **What it Does:** Targets only `input/yggdrasil.png` for dithering, ignoring all other files.
* **Why it Fits:** Saves processing time and keeps the output folder clean when iterating on a single project file.

### 3. Custom Project Folders
```bash
gf --input input/projects/acrylic_signs -o output/projects/acrylic_processed
```
* **Use Case:** Separating files for a specific client or material run.
* **What it Does:** Reads images from the custom directory `input/projects/acrylic_signs` and saves the dithered results to `output/projects/acrylic_processed`.
* **Why it Fits:** Keeps your projects clean and organized without mixing output files in the main `output/` directory.

---

## Category 2: Coasters, Shapes & Cutouts

### 4. Standard 4-Inch Circular Coaster
```bash
gf --preset coaster -w 4
```
* **Use Case:** Creating a standard 4-inch circular wooden coaster.
* **What it Does:** Resizes the image to 1200x1200px (4 inches at 300 DPI), applies a circular transparency mask (RGBA mode) so everything outside the circle is transparent, and draws a 1px solid black cut line around the perimeter.
* **Why it Fits:** Creates a file where the Glowforge UI separates the inner dithered art as **Engrave** and the outer black ring as **Cut** automatically.

### 5. Standard 4-Inch Heart Coaster / Ornament
```bash
gf --preset coaster-heart -w 4
```
* **Use Case:** Creating a heart-shaped wooden coaster, Valentine ornament, or custom key tag.
* **What it Does:** Resizes the image to 1200x1200px (4 inches at 300 DPI), applies a parametric heart shape transparency mask (RGBA mode) so everything outside the heart is transparent, and draws a 1px solid black heart-shaped cut line around the perimeter.
* **Why it Fits:** Automates the creation of heart-shaped tokens where the inner dithered art is engraved and the outer heart boundary is cut out by the laser.

---

## Category 3: Wood-Specific Engraving

### 6. Softwood & Plywood Preset
```bash
gf --preset wood-soft
```
* **Use Case:** Engraving on light, soft woods like basswood, balsa, birch plywood, or draftboard.
* **What it Does:** Uses a moderate contrast boost (`1.3`) and standard sharpening to prevent over-burning, keeping dither dots separated.
* **Why it Fits:** Softwoods char easily; keeping the contrast moderate avoids deep burn pockets that could merge into messy black spots.

### 7. Hardwood Preset
```bash
gf --preset wood-hard
```
* **Use Case:** Engraving on dense, naturally dark woods like cherry, walnut, mahogany, or purpleheart.
* **What it Does:** Uses high contrast (`1.7`) and heavy unsharp masking to burn deeper and create high visual separation against the dark wood grain.
* **Why it Fits:** Dark hardwoods require deep, crisp burns to stand out visually against the dark background wood.

### 8. Hardwood with Vector Solid Lock
```bash
gf --preset wood-hard -b 15
```
* **Use Case:** Engraving logos or designs with solid black lettering on cherry wood.
* **What it Does:** Applies the deep-cutting `wood-hard` preset but locks pixels darker than `15` to absolute solid black (no dithering stipple inside letters).
* **Why it Fits:** Prevents error diffusion from introducing stray white pixels inside fine text, keeping lettering sharp and solid.

---

## Category 4: Photo & Portrait Tuning

### 9. High-Detail Photograph Engraving
```bash
gf --preset photo-high-detail
```
* **Use Case:** Engraving family portraits or high-resolution pet photos.
* **What it Does:** Applies a light denoise filter (radius 3) to smooth out camera sensor noise, boosts contrast, and applies aggressive edge sharpening.
* **Why it Fits:** Preserves fine details (like hair, fur, and fabric textures) without converting high-frequency camera noise into a grainy mess.

### 10. Soft Portraiture
```bash
gf --preset photo-soft
```
* **Use Case:** Engraving weddings, soft portraits, or baby pictures.
* **What it Does:** Applies gentle contrast (`1.2`) and minimal sharpening to allow smooth, soft transitions between light and dark shades.
* **Why it Fits:** Avoids harsh outlines and gritty facial features, yielding a warm, classic, and delicate engraving.

### 11. Low-Resolution Photo Rescue
```bash
gf --preset low-res-enhance
```
* **Use Case:** Engraving older, low-resolution, or pixelated photos.
* **What it Does:** Runs a strong denoise filter to blur pixel "staircases" and applies high-intensity sharpening to recreate sharp borders.
* **Why it Fits:** Smooths out pixelation blocks before dithering, ensuring they don't engrave as blocky grid patterns.

---

## Category 5: AI Art Cleanup

### 12. Standard AI Art Cleanup
```bash
gf --preset ai-art
```
* **Use Case:** Engraving illustrations generated by Midjourney, DALL-E, or Stable Diffusion.
* **What it Does:** Applies a median denoise (radius 3) to sweep away compression artifacts, boosts contrast (`1.6`), and applies strong sharpening.
* **Why it Fits:** AI art often has hidden anti-aliasing noise; this sweeps away the "dust" so the dithered print looks extremely clean.

### 13. Deep AI Art Cleanup with Snapping Boundaries
```bash
gf --preset ai-art-detailed --clean-solids-black 45 --clean-solids-white 215
```
* **Use Case:** Highly detailed AI art with noisy, off-white backgrounds (e.g. value 230) and dark gray shadows.
* **What it Does:** Combines the `ai-art-detailed` preset (denoise size 5) with wider snapping ranges: values under `45` snap to pure black; values above `215` snap to pure white.
* **Why it Fits:** Prevents hazy backgrounds from engraving as random speckles, ensuring a 100% clean background while locking dark shadow tones.

---

## Category 6: Material-Specific Options

### 14. Cast Acrylic Edge-Lit Signs
```bash
gf --preset acrylic
```
* **Use Case:** Engraving clear or colored cast acrylic sheets for light-up signs.
* **What it Does:** Applies high contrast and snaps solids to prevent heat building up on the plastic, keeping dither dots well-spaced.
* **Why it Fits:** Acrylic melts when exposed to continuous heat; spaced dither dots prevent melting and create a uniform frosted white texture.

### 15. Leather Engraving
```bash
gf --preset leather
```
* **Use Case:** Engraving patches, wallets, belts, or book covers.
* **What it Does:** Uses lower contrast (`1.1`), soft sharpening, and median denoise to prevent over-burning.
* **Why it Fits:** Leather burns easily and can buckle from heat; keeping the laser operations light prevents scorching and warping.

### 16. Glass Etching
```bash
gf --preset glass
```
* **Use Case:** Etching bottles, cups, mirrors, or glassware.
* **What it Does:** Boosts contrast and sharpening to make sure dither dots are distinct and isolated.
* **Why it Fits:** Glass fractures microscopically under the laser; sharp, isolated dither dots give a clean frosted look without cracking or chipping.

### 17. Deep Relief Rubber Stamps
```bash
gf --preset stamp -i
```
* **Use Case:** Engraving rubber stamp sheets to make custom ink stamps.
* **What it Does:** Inverts the image (`-i`) and applies the `stamp` preset (extremely high contrast and solids snapping) to create deep relief boundaries.
* **Why it Fits:** Stamps require deep, steep edges with no intermediate dither grays so only the intended pattern touches the ink.

---

## Category 7: Graphic Styles & Finishes

### 18. Clean Vector Logos
```bash
gf --preset vector-graphic
```
* **Use Case:** Engraving solid black-and-white vectors, silhouette art, or text logos.
* **What it Does:** Snaps solids aggressively, boosts contrast, and sets thresholds to force grays to either pure black or pure white.
* **Why it Fits:** Ensures razor-sharp vector edges without any stippling along text lines.

### 19. Comic Book & Line Art
```bash
gf --preset line-art
```
* **Use Case:** Engraving scanned ink drawings, coloring pages, or manga panels.
* **What it Does:** Boosts contrast heavily and sets a low black threshold to clear out paper smudge textures and scanner shadows.
* **Why it Fits:** Leaves paper backgrounds clean and guarantees lines are engraved as solid, continuous black.

### 20. Pencil & Charcoal Drawings
```bash
gf --preset sketch
```
* **Use Case:** Engraving delicate pencil drawings or charcoal sketches.
* **What it Does:** Keeps contrast moderate and uses a high-intensity, small-radius unsharp mask to capture faint pencil textures.
* **Why it Fits:** Preserves the soft, hand-drawn paper texture and pencil strokes instead of blowing them out.

### 21. Hard Graphical Halftones
```bash
gf --preset high-contrast --nb
```
* **Use Case:** Creating retro, high-contrast, poster-style dithered prints without an outer border.
* **What it Does:** Maximizes contrast and snaps solids while disabling the automatic 1px border.
* **Why it Fits:** Prevents an unwanted black line around the perimeter when engraving a pre-cut board.

---

## Category 8: Advanced Custom Controls

### 22. Dark Materials Negative Engraving
```bash
gf -i --preset photo-high-detail
```
* **Use Case:** Engraving on dark materials that turn light when burned (e.g. black slate, black anodized aluminum, or painted tiles).
* **What it Does:** Inverts all image colors (black becomes white, white becomes black) before running the photo-high-detail optimization.
* **Why it Fits:** Since burning slate or anodized aluminum exposes a light mark, inverting ensures highlights in the photo correspond to burned areas.

### 23. Aggressive Denoise for Compressed Files
```bash
gf --denoise 5
```
* **Use Case:** Processing extremely low-quality or heavily compressed JPEG images.
* **What it Does:** Runs a large 5x5 median filter to remove artifacts, smoothing out blocks before applying default contrast and sharpening.
* **Why it Fits:** Cleans up blocky textures that would otherwise result in messy dither patterns.

### 24. Heavy Detail Edge Boost
```bash
gf --sharpen-percent 300 --sharpen-radius 3.0
```
* **Use Case:** Engraving on very coarse-grained woods like red oak or southern pine.
* **What it Does:** Overrides sharpening to apply a massive 300% unsharp mask with a large 3.0px radius.
* **Why it Fits:** Coarse wood grain can swallow fine lines; extreme sharpening creates thick contrast boundaries that survive the wood's natural texture.

### 25. Global Brightness Calibration
```bash
gf -d 100
```
* **Use Case:** Lightening an entire batch of images because the test burn came out too dark.
* **What it Does:** Lowers the dither threshold to `100` (down from 128), causing more mid-tones to round to white.
* **Why it Fits:** Allows a quick global adjustment to compensate for laser power or wood char factor without editing source files.
