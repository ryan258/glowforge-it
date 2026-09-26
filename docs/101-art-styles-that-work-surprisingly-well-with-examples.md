# 101 Art Styles That Work Surprisingly Well for Laser Artwork

A prompt and processing reference for AI/Glowforge artists. Each entry gives a visual direction, a short example prompt, and a starting image preset. The prompt is for generating or commissioning the **source image**; the preset is for preparing that saved image with this project.

## How to use this guide

1. Choose an art direction and adapt its prompt to your subject.
2. Generate or create the source image. Ask for clear shapes, intentional empty space, and limited tiny details when the artwork will be small.
3. Save the image, inspect it, and run the suggested preparation preset. For example:

   ```bash
   gf --input input/woodcut-fox.png --preset line-art --material "medium maple plywood" --material-thickness 1/8
   ```

4. Review the processed PNG at its intended physical size. Add dimensions if needed, for example `-w 4 -h 4`.
5. Review the design, material, and machine settings in the Glowforge app before printing.

The project’s material label defaults to **medium maple plywood at 1/8 inch**. Change the run’s descriptive thickness with `--material-thickness 1/4` or another decimal/fraction. That value records stock context only; it does not affect image processing or set laser power, speed, focus, or passes. Check the makerspace’s actual stock label and measure the sheet.

## What the CLI can and cannot do

The current pipeline makes grayscale source art into a 1-bit PNG: Atkinson error-diffused by default, a solid thresholded silhouette, an ordered Bayer screen, a variable-cell halftone, directional hatch/crosshatch, Sobel edge linework, or tone contours. It also supports cleanup, contrast, sharpening, sizing, circle/heart masks, an optional SVG outline sidecar, and an opt-in centerline-style SVG sidecar derived from the final mask. It does **not** generate the visual style in these prompts, create general editable vectors or cut paths from a bitmap, or include separate native sketch, engraving, or pixel-art renderers. Those effects must already be present in the source artwork. A raster style preset is only a starting point for pixel preparation.

A pre-halftoned or tightly crosshatched image can form moiré or lose small gaps after Atkinson dithering. Compare the output at final size before choosing it. For cut outlines, use `--svg-cut` with a circle or heart mask, then inspect the imported SVG in the app; otherwise a black line inside a PNG is engraving artwork. Material-specific presets do not certify material compatibility or provide machine settings.

The presets named below are valid CLI presets. Unless a row says otherwise, use the suggested one like this: `gf --input input/your-source.png --preset PRESET`. The `gf` wrapper enables `--clean-solids` by default.

## 1. Printmaking and engraved linework

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 1 | Bold woodcut | `A red fox beneath a crescent moon, bold woodcut, large black masses, simple white gaps` | `line-art` |
| 2 | Linocut | `A heron among reeds, linocut print, chunky carved marks, clean open background` | `line-art` |
| 3 | Scratchboard | `A raven on a branch, scratchboard illustration, bright etched feathers on deep black` | `high-contrast` |
| 4 | Copperplate engraving | `A sailing ship at sea, fine copperplate-style contour engraving, grouped parallel lines` | `photo-high-detail` |
| 5 | Drypoint | `A wild rose, drypoint print, loose burr-like lines, strong subject silhouette` | `sketch` |
| 6 | Stipple engraving | `An owl portrait, stipple engraving, dots grouped into broad light and dark regions` | `photo-soft` |
| 7 | Crosshatch engraving | `A mountain cabin, crosshatched engraving, three clear tone groups, no gray wash` | `line-art` |
| 8 | Mezzotint-inspired | `A curled sleeping cat, mezzotint-inspired black field with broad white highlights` | `photo-soft` |
| 9 | Ukiyo-e-inspired woodblock | `A koi circling a water lily, Japanese woodblock-print composition, bold outlines` | `high-contrast` |
| 10 | Relief stamp | `A bee and two flowers, rubber-stamp relief art, thick connected lines, no tiny gaps` | `stamp` |

## 2. Portraits and faces

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 11 | Newspaper portrait | `A thoughtful face in a vintage newspaper engraving, compact dot-and-line shading` | `photo-high-detail` |
| 12 | Profile silhouette | `A child looking toward a sunflower, crisp side-profile silhouette, open background` | `high-contrast` |
| 13 | Cameo portrait | `An elegant side profile framed by a simple oval cameo border, high-contrast engraving` | `line-art` |
| 14 | Pet portrait engraving | `A fluffy dog looking forward, engraved portrait, broad fur clumps, bright eyes, simple background` | `photo-high-detail` |
| 15 | High-key portrait | `A smiling face in high-key portrait lighting, simple shadow shapes, uncluttered background` | `photo-soft` |
| 16 | Low-key portrait | `A jazz musician in dramatic side light, low-key portrait, readable silhouette and face` | `photo-high-detail` |
| 17 | Double-exposure line art | `A human profile containing a pine forest, two readable silhouettes, restrained fine detail` | `photo-soft` |
| 18 | Pointillist portrait | `A profile built from spaced round dots, pointillist print, large dots and broad value groups` | `high-contrast` |
| 19 | Etched family portrait | `Two grandparents seated together, etched portrait, simplified clothing folds, clear faces` | `photo-soft` |
| 20 | Comic portrait | `A friendly mechanic, bold black comic contours, sparse shadow marks, no speech bubbles` | `vector-graphic` |

## 3. Botanical and natural forms

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 21 | Herbarium plate | `A single maple branch with leaves and seed pods, antique botanical plate, clear silhouette` | `line-art` |
| 22 | Fern engraving | `A curled fern frond, botanical engraving, repeated leaflets with visible spacing` | `line-art` |
| 23 | Leaf-vein study | `One broad oak leaf, scientific line drawing, bold outer contour and simplified vein network` | `high-contrast` |
| 24 | Floral mandala | `A daisy mandala with eight broad petals, radial symmetry, separated black outlines` | `vector-graphic` |
| 25 | Mushroom field guide | `Three woodland mushrooms, old field-guide engraving, distinct caps and stems` | `line-art` |
| 26 | Seed-pod study | `A milkweed pod opening, botanical etching, prominent curved seeds and clean background` | `sketch` |
| 27 | Tree-ring cross section | `A stump cross section, graphic tree rings and one small sprouting leaf, bold simple lines` | `high-contrast` |
| 28 | Thorny stem illustration | `A climbing rose stem with three blossoms, botanical pen engraving, open spaces between thorns` | `line-art` |
| 29 | Butterfly-wing pattern | `A luna moth with broad symmetrical wing markings, natural-history plate, bold separations` | `high-contrast` |
| 30 | Coral study | `A branching coral specimen, scientific engraving, thick primary branches and sparse texture` | `line-art` |

## 4. Animals and wildlife

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 31 | Feather engraving | `A single crow feather, engraved barb lines, broad dark shaft, generous margins` | `line-art` |
| 32 | Fish-scale illustration | `A trout turning in a stream, carved-print style, simplified scales and bold water lines` | `high-contrast` |
| 33 | Moth specimen plate | `A luna moth with spread wings, antique specimen engraving, large readable wing markings` | `line-art` |
| 34 | Beetle engraving | `A stag beetle viewed from above, natural-history engraving, distinct legs and shell` | `high-contrast` |
| 35 | Rabbit profile | `A rabbit in clover, woodcut illustration, broad dark ears and uncluttered grass` | `line-art` |
| 36 | Horse contour drawing | `A horse head in profile, flowing contour lines, sparse mane strokes, clean white background` | `sketch` |
| 37 | Fox silhouette | `A curled fox framed by a few pine branches, solid silhouette with intentional white cut-ins` | `high-contrast` |
| 38 | Whale-and-map hybrid | `A whale silhouette filled with simple ocean contour lines, strong outer boundary` | `line-art` |
| 39 | Paw-print medallion | `A large paw print inside a simple round badge, bold vector-like black shapes` | `vector-graphic` |
| 40 | Bird in flight | `A swallow in flight over two wind lines, vintage engraving, distinct feathers and open sky` | `line-art` |

## 5. Landscapes, maps, and architecture

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 41 | Mountain contour print | `A mountain ridge reflected in a lake, contour-line engraving, three broad depth layers` | `line-art` |
| 42 | Topographic landscape | `A single island shown as bold topographic contour bands, labels omitted, clear water margin` | `high-contrast` |
| 43 | Coastline map | `A simple coastline with a lighthouse and three contour bands, monochrome map engraving` | `line-art` |
| 44 | Neighborhood street map | `A simplified street grid around a park, map engraving, major roads only, no text` | `high-contrast` |
| 45 | Architectural blueprint | `A small greenhouse in clean blueprint linework, front elevation, few structural lines` | `line-art` |
| 46 | Victorian facade | `A narrow Victorian shopfront, engraved architectural elevation, strong doorway and window shapes` | `photo-high-detail` |
| 47 | Skyline stencil | `A compact city skyline, bold stencil silhouette, varied rooflines, no tiny windows` | `high-contrast` |
| 48 | Bridge engraving | `A stone arch bridge over a river, crosshatched engraving, large separated arches` | `line-art` |
| 49 | Cathedral rose window | `A gothic rose window, symmetrical leaded shapes, thick separators and open center` | `vector-graphic` |
| 50 | Cabin field sketch | `A cabin beneath tall pines, hand-etched field sketch, simplified board and tree details` | `sketch` |

## 6. Folklore, fantasy, and celestial art

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 51 | Tarot woodcut | `A lantern-bearing traveler on a winding path, symbolic tarot-card woodcut, border left blank` | `line-art` |
| 52 | Folklore print | `A tiny house inside a giant mushroom, folk-art woodcut, bold outlines and simple leaves` | `high-contrast` |
| 53 | Dragon engraving | `A curled dragon around a round pearl, engraved scales limited to broad grouped marks` | `photo-high-detail` |
| 54 | Phoenix emblem | `A rising phoenix with broad layered feathers, symmetrical black-and-white emblem` | `vector-graphic` |
| 55 | Moon-phase folklore | `Eight moon phases above a simple mountain ridge, stark celestial engraving` | `high-contrast` |
| 56 | Star-chart illustration | `A fictional constellation shaped like a fox, sparse stars connected by clean lines` | `line-art` |
| 57 | Alchemical diagram | `A fictional botanical alchemy diagram with leaf, circle, and orbit symbols, no lettering` | `vector-graphic` |
| 58 | Fantasy map | `A small island map with mountains, one river, and a compass rose, hand-engraved, labels omitted` | `line-art` |
| 59 | Potion cabinet | `Three glass potion bottles with leaves and roots, etched illustration, large simple highlights` | `sketch` |
| 60 | Cryptid field guide | `A friendly lake creature emerging from water, naturalist field-guide engraving, simple ripples` | `photo-high-detail` |

## 7. Graphic design, icons, and lettering frames

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 61 | Art Deco poster | `A sun rising behind a stepped city, Art Deco geometry, strong symmetry and broad rays` | `high-contrast` |
| 62 | Bauhaus geometry | `A bird assembled from circles, triangles, and rectangles, geometric modernist poster` | `vector-graphic` |
| 63 | Swiss-style poster | `A mountain and cable car reduced to precise geometric forms, asymmetrical black-and-white layout` | `high-contrast` |
| 64 | Stencil icon | `A bicycle leaning against a wall, two-tone stencil icon, thick bridges between shapes` | `high-contrast` |
| 65 | Maker badge | `A hand plane, maple leaf, and spark inside a circular workshop badge, bold emblem` | `vector-graphic` |
| 66 | Negative-space monogram frame | `Interlocking blank initials formed from vines and open shapes, reserve empty space for letters` | `vector-graphic` |
| 67 | Ornamental initial frame | `A large empty central letter space surrounded by simple engraved acanthus leaves` | `line-art` |
| 68 | Engraved border | `A rectangular border of alternating leaves and dots, even spacing, empty center` | `line-art` |
| 69 | Wayfinding pictogram | `A clear mountain-trail marker icon, bold silhouette, minimal details, no text` | `high-contrast` |
| 70 | QR-code frame | `A quiet square frame of leaves with an empty white center reserved for a separately generated QR code` | `vector-graphic` |

## 8. Repeating patterns and ornament

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 71 | Celtic knotwork | `A broad three-strand knot inside a circle, high-contrast paths with generous gaps` | `vector-graphic` |
| 72 | Geometric tilework | `An eight-point geometric tile pattern, monochrome, repeated broad bands and open centers` | `high-contrast` |
| 73 | Tessellation | `Interlocking fish tessellation, simple repeated outlines, large scales and clear spacing` | `line-art` |
| 74 | Sashiko-inspired pattern | `A repeating wave-and-diamond stitch pattern, bold evenly spaced dashes` | `high-contrast` |
| 75 | Basket weave | `A simple over-under basket weave panel, broad ribbons and clear crossing gaps` | `high-contrast` |
| 76 | Quilt-block geometry | `A star quilt block with twelve large fabric-like sections, crisp black separators` | `vector-graphic` |
| 77 | Labyrinth | `A single-path circular labyrinth, thick equal-width paths, simple center mark` | `vector-graphic` |
| 78 | Op-art bands | `A large eye made from alternating curved black and white bands, wide intervals` | `high-contrast` |
| 79 | Radial mandala | `A four-layer leaf mandala with broad repeated petals and a clear outer margin` | `line-art` |
| 80 | Lace-paper ornament | `A snowflake-like lace ornament with sturdy bridges and no hairline connections` | `high-contrast` |

## 9. Unexpected material and image-making references

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 81 | Pixel art | `A tiny lighthouse in 16-bit pixel art, limited black-and-white blocks, no anti-aliased edges` | `high-contrast` |
| 82 | Low-poly portrait | `A mountain goat built from large polygon facets, monochrome, few distinct value regions` | `vector-graphic` |
| 83 | Layered paper-cut look | `A layered paper-cut forest with three depth planes, crisp silhouettes and large openings` | `high-contrast` |
| 84 | Torn-paper collage | `A lighthouse and waves assembled from torn black paper shapes, broad overlaps` | `high-contrast` |
| 85 | Cyanotype-inspired line art | `A fern and seed heads as a high-contrast photographic contact-print composition` | `photo-soft` |
| 86 | Ceramic sgraffito | `A fish scratched through a dark ceramic slip, thick incised contours and open scales` | `line-art` |
| 87 | Metal-etching pattern | `A compass rose surrounded by engraved radial lines, clear line hierarchy and empty corners` | `line-art` |
| 88 | Wood-grain abstraction | `A whale formed from broad flowing grain lines, strong outer silhouette, sparse internal curves` | `sketch` |
| 89 | Stained-glass outline | `A tulip arranged as large stained-glass-like cells with thick dark dividers` | `vector-graphic` |
| 90 | Jacquard textile motif | `A repeating crane-and-cloud motif designed like woven cloth, simplified black shapes` | `high-contrast` |

## 10. Hybrid styles and concept pieces

| # | Style | Example source-art prompt | Starting preset |
|---:|---|---|---|
| 91 | Botanical moon map | `A crescent moon surrounded by fern fronds and tiny stars, vintage engraved plate` | `line-art` |
| 92 | Animal-shaped city map | `A bear silhouette filled with a simplified city street grid, large readable roadways` | `high-contrast` |
| 93 | River-and-bird composition | `A heron silhouette whose legs become winding river contours, bold open composition` | `line-art` |
| 94 | Specimen-meets-woodcut | `A beetle labeled only with blank pointer lines, natural-history plate in bold carved-print style` | `high-contrast` |
| 95 | Mechanical engraving | `A compact wind-up bird automaton, engraved gears simplified into a few large shapes` | `photo-high-detail` |
| 96 | Sound-and-forest motif | `A forest formed from broad sound-wave arcs, balanced black-and-white graphic, no words` | `high-contrast` |
| 97 | Letterpress collage | `A stack of abstract botanical printing blocks, uneven ink texture, no readable text` | `line-art` |
| 98 | Fossil cross-section | `An ammonite fossil with bold spiral chambers, scientific engraving and clear outer edge` | `line-art` |
| 99 | Circuit-board landscape | `A mountain range integrated with a simple circuit-board trace pattern, broad separated lines` | `high-contrast` |
| 100 | Surreal architectural engraving | `A staircase looping around a single tree, architectural etching, uncluttered white field` | `photo-high-detail` |
| 101 | Maker’s personal emblem | `Combine a favorite tool, local plant, and meaningful animal into one simple two-tone badge` | `vector-graphic` |

## Quick selection guide

- **Start with `line-art`** for drawings, engraving-like marks, maps, and botanical plates.
- **Start with `high-contrast`** for bold silhouettes, stencils, icons, and broad pattern shapes.
- **Start with `vector-graphic`** for clean logo-like art and regular geometric forms.
- **Start with `photo-soft` or `photo-high-detail`** for portraits and tonal source images; compare the result because their cleanup/sharpening choices differ.
- **Start with `sketch`** for hand-drawn source art and loose etched lines.
- **Use `--denoise 3` or `--denoise 5` selectively** when the input has visible speckle; denoising can erase fine marks.

These are visual starting points, not machine recipes. For maple stock context, the current default label is medium maple plywood at 1/8 inch; set another nominal thickness with `--material-thickness`. Confirm the actual stock and approved Glowforge settings with your makerspace before a proof or production job.
