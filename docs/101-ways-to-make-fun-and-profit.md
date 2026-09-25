# 101 Ways to Make Fun and Profit

An idea menu for Glowforge makers and small creative businesses. Some entries
include a runnable image-preparation command; others need source artwork,
vector/layout work in another tool, or manual arranging in the Glowforge app.
The CLI prepares raster images. It does not generate text, grids, QR codes,
vector designs, sheets of nested parts, or machine settings.

This is a **menu, not a roadmap**. The project’s default stock context is medium maple plywood at 1/8 inch. Set
a different nominal thickness with `--material-thickness 1/4` (or a decimal);
this is a descriptive label only. Check the actual stock and the machine
procedure before printing.

---

## Read this once, then never again

Four things apply to nearly every entry below. They are stated here so they
don't have to be repeated 101 times.

**1. `gf` already passes `--clean-solids`.** The wrapper script enables it
with the default near-black/near-white thresholds. It snaps only pixels that
fall beyond those boundaries; inspect pale texture before using the result.
If you call `uv run main.py` directly, pass `-c` to enable it.

**2. Pin both dimensions on anything round.** Cut-shape diameter is
`min(width, height)`, so `-w 4` alone only gives a 4-inch circle when the
source image is square. Use `-w 4 -h 4`.

**3. A bitmap outline engraves.** With `--svg-cut`, the tool also writes an
SVG sidecar with a vector outline. Upload and inspect it in the Glowforge
app, verify alignment and assign the intended operations before printing.

**4. Confirm stock safety with the operator.** Use material compatibility
guidance from Glowforge, the stock supplier, and the makerspace. This tool
cannot identify material or determine whether its coatings, core, or adhesive
are suitable for a laser.

Nominal area examples are model-specific: Performance 19.5 × 11 inches, Aura
12 × 12 inches, and Spark 8.5 × 11 inches. Some operations/settings reduce
usable area; use `--machine MODEL` as an early check and confirm the final
workspace in the app.

---

## 1. Calibrate first (1–8)

Eight useful proof and comparison exercises. Follow the makerspace’s
approved stock and machine procedure, and record the settings for the test.

1. **The power/speed grid** — make a 5×5 grid in a design app, import it, and label each cell with the machine-approved test settings. This CLI cannot generate the grid or select power/speed; its command can prepare a source image for the engraving step: `gf --input input/test-art.png --preset wood-soft -w 6 -h 6`.
2. **The gradient bar** — create a black-to-white gradient source in an image editor, then prepare it here: `gf --input input/gradient.png --preset photo-high-detail -w 8 -h 1.5`. Use the material test and shop procedure to assess tone; the result is not a guaranteed calibration.
3. **The dither-threshold ladder** — run `gf --input input/photo.png -d 100`, then repeat with `-d 115`, `-d 128`, `-d 140`, and `-d 155`. Each run produces a separate image file; arrange or label them in another tool before printing.
4. **The contrast ladder** — run `gf --input input/photo.png --contrast 1.2`, then repeat with `--contrast 1.5`, `1.8`, `2.2`, and `2.8`. Compare the separate output files; the CLI does not make a comparison sheet.
5. **The material swatch set** — one small test image across every material you own, filed in a box. `gf --preset high-contrast -w 2 -h 2`
6. **The kerf ruler** — create a ruler/vector test design in another tool, use an approved test procedure, and compare the result with calipers. This CLI does not create ruler marks or apply kerf compensation.
7. **The tiny-text limit card** — lay out the same word at several sizes in a design app, then test the artwork on each approved material. This CLI does not create or measure text.
8. **The invert comparison** — prepare both the original and inverted artwork and compare the previews before a small approved proof. `gf --input input/design.png --preset wood-soft --invert -w 3 -h 3`

---

## 2. Coasters and drinkware (9–20)

Coasters are a common small-format project; test the artwork, finish, and local
demand before treating any design as a product.

9. **Classic photo coaster** — prepare a face or landscape in a 4-inch circle with a vector outline: `gf --input input/photo.png --preset coaster --svg-cut -w 4 -h 4`
10. **Heart coaster** — prepare the source art and optional vector outline: `gf --input input/photo.png --preset coaster-heart --svg-cut -w 4 -h 4`
11. **Matching set of six** — process six prepared source images in one batch for consistent software options. The CLI writes six separate files; it does not nest or guarantee matching physical results. Arrange the designs in the app.
12. **Pet-face coaster** — prepare a centered circular engraving and vector-cut layout: `gf --input input/pet.png --preset photo-high-detail --circle-cut --svg-cut -w 4 -h 4`. Inspect the embedded art and outline in the app.
13. **Map coaster** — provide a map image and prepare it for a circle: `gf --input input/map.png --preset line-art --circle-cut --svg-cut -w 4 -h 4`. Check that small street labels remain legible.
14. **Constellation coaster** — provide the chart as source art, then prepare the artwork and vector outline: `gf --input input/sky-chart.png --preset high-contrast -i --circle-cut --svg-cut -w 4 -h 4`.
15. **Album-art coaster set** — batch four source covers with the same options. The CLI creates separate files rather than a laid-out sheet: `gf --input input/covers --preset vector-graphic --circle-cut --svg-cut -w 4 -h 4`.
16. **Slate coaster artwork** — if the makerspace approves this material and machine, prepare a high-contrast circle: `gf --input input/design.png --preset high-contrast --circle-cut --svg-cut -w 4 -h 4`. Confirm the machine can perform the intended work on that stock.
17. **Leather coaster artwork** — confirm the specific leather and shop procedure first, then prepare the image: `gf --input input/design.png --preset leather --circle-cut --svg-cut -w 4 -h 4`.
18. **Acrylic coaster artwork** — verify the exact acrylic type and machine compatibility first: `gf --input input/design.png --preset acrylic -i --circle-cut --svg-cut -w 4 -h 4`. Inversion changes the image; it does not configure back-side printing.
19. **Bar-runner strip** — one long 12×3 panel instead of individual coasters. `gf --preset wood-hard -w 12 -h 3`
20. **Growler / bottle label plate** — prepare a 3-inch round plaque; use an approved food-contact-safe finishing workflow if it will be near a drink. `gf --input input/label.png --preset wood-hard --circle-cut --svg-cut -w 3 -h 3`

---

## 3. Gifts and keepsakes (21–34)

21. **Photo-on-wood portrait** — the flagship. Big, slow, worth it. `gf --preset photo-high-detail -w 8`
22. **Anniversary date plaque** — a date, a place, and a small ornament. `gf --preset line-art -w 6`
23. **Handwriting keepsake** — scan a note from someone and burn their actual handwriting. This is the one that makes people cry. `gf --preset sketch --contrast 2.0 -w 5`
24. **Recipe card in a grandparent's hand** — same trick, mounted in a kitchen frame. `gf --preset sketch -w 8 -h 10`
25. **Signature plaque** — one scanned signature, cleaned to pure black. `gf --preset line-art -b 40 -w 6`
26. **Kid's drawing, immortalized** — a crayon scribble becomes a real object. `gf --preset ai-art --denoise 3 -w 6`
27. **Baby footprint / handprint plaque** — inked print, scanned, cleaned. `gf --preset high-contrast -w 5 -h 7`
28. **Ultrasound engraving** — low contrast source, so lean hard on the enhancer. `gf --preset low-res-enhance --contrast 2.0 -w 5`
29. **Wedding-vow panel** — full text of the vows, small type, big panel. `gf --preset line-art -w 8 -h 10`
30. **Soundwave plaque** — waveform of a voice message or a first-dance song. `gf --preset vector-graphic -w 10 -h 3`
31. **Music-link code plaque** — create or obtain a QR/streaming code and combine it with album art in a design app first. Then prepare that composite: `gf --input input/music-code.png --preset high-contrast -w 4 -h 6`. Test scan reliability on the finished material.
32. **Memorial plaque** — portrait, name, dates. Handle with care and burn a test first. `gf --preset photo-soft -w 6`
33. **Passport-stamp travel board** — every stamp from a trip, tiled on one panel. `gf --preset line-art -w 12 -h 8`
34. **Engraved leather journal cover** — veg-tan, light touch, no over-burn. `gf --preset leather -w 6 -h 8`

---

## 4. Home and décor (35–48)

35. **Botanical print series** — three or five plant illustrations, matched frames. `gf --preset line-art -w 8 -h 10`
36. **Vintage map panel** — old maps are already halftoned; denoise before dithering. `gf --preset low-res-enhance --denoise 3 -w 12 -h 9`
37. **City skyline silhouette** — thresholds collapse the midtones so most of the panel is solid. Dithering still runs on whatever tones remain; there is no no-dither mode. `gf --preset high-contrast -b 60 -W 200 -w 12 -h 4`
38. **Topographic contour panel** — thin lines, so protect them from the sharpen halo. `gf --preset line-art --sharpen-percent 100 -w 10 -h 10`
39. **Star chart of a specific night** — inverted so the sky engraves and the stars are left unengraved. How that reads depends on the stock; the CLI does not control burn colour. `gf --preset high-contrast -i -w 10 -h 10`
40. **Tarot-card set** — create 22 source designs and batch-prep them at the same size. The CLI writes individual files; arrange the card sheet in a layout tool. `gf --input input/tarot-cards --preset vector-graphic -w 2.75 -h 4.75`
41. **Bookmark set** — offcut-sized, sells at craft fairs by the fistful. `gf --preset line-art -w 2 -h 6`
42. **Light-switch plate** — engrave a blank hardwood plate. `gf --preset wood-hard -w 3 -h 5`
43. **Mirror-back etch** — engrave the back for depth. Flip the art horizontally in an image editor first: `-i` inverts tone, it does not mirror. `gf --preset glass -i -w 6 -h 6`
44. **Acrylic edge-lit panel** — engraved art glows when lit from the edge. `-i` flips which tones engrave, not the artwork geometry. `gf --preset acrylic -i -w 6 -h 8`
45. **Wall-mounted herb labels** — batch-prep twelve source images at one size. The outputs are separate; arrange them in the app. `gf --input input/herb-labels --preset line-art -w 1.5 -h 3`
46. **Cutting-board inlay art** — decorative only, never on the cutting surface. `gf --preset wood-soft -w 8 -h 5`
47. **Tile trivet** — ceramic tile engraves like slate: contrast or nothing. `gf --preset high-contrast -w 4 -h 4`
48. **Wooden lampshade panel** — perforate-adjacent effect with heavy dither. `gf --preset wood-hard -d 150 -w 6 -h 8`

---

## 5. Signs, words and lettering (49–56)

49. **House-number plaque** — big, clean, weatherproofed after. `gf --preset vector-graphic -w 10 -h 4`
50. **Business sign** — logo plus name. Vector-graphic preset is built for this. `gf --preset vector-graphic -w 12 -h 6`
51. **Bar / workshop sign** — hand-lettered look, distressed. `gf --preset sketch -w 14 -h 6`
52. **Door hanger** — "in a meeting", "recording", "do not disturb". `gf --preset high-contrast -w 4 -h 9`
53. **Trail marker set** — arrows and distances for a property or an event. `gf --preset line-art -w 6 -h 3`
54. **Quote panel** — one line of text nobody will read twice, and one they will. `gf --preset line-art -w 10 -h 4`
55. **Bilingual welcome sign** — two scripts, one panel; check tiny-glyph legibility first (see #7). `gf --preset vector-graphic -w 12 -h 5`
56. **Accessible information sign concept** — consult accessibility standards and an experienced fabricator before making any tactile or Braille sign. This raster image tool cannot create or validate compliant tactile features, so this idea needs a qualified design workflow.

---

## 6. Pets and portraits (57–66)

Pet artwork can be personally meaningful and may support custom commissions.
Confirm photo rights, image quality, customer expectations, and the full job
cost before offering it as a paid service.

57. **Pet-portrait plaque** — the core product. `gf --preset photo-high-detail -w 6 -h 8`
58. **Pet-portrait coaster** — prepare a 4-inch round portrait and vector outline: `gf --input input/pet.png --preset photo-high-detail --circle-cut --svg-cut -w 4 -h 4`
59. **Pet memorial marker** — same care as #32. `gf --preset photo-soft -w 5 -h 7`
60. **Pet-silhouette keychain** — pure black shape, no tonal detail. `gf --preset high-contrast -b 70 -w 1.5 -h 1.5`
61. **Nose-print keepsake** — ink the nose, scan it, burn it. Weird, and it sells. `gf --preset line-art -w 3 -h 3`
62. **Breed-outline sign** — line art plus the animal's name. `gf --preset line-art -w 8 -h 4`
63. **Multi-pet family panel** — compose the animal photos into one source image in a design editor, then prepare that composite: `gf --input input/pet-family.png --preset photo-high-detail -w 12 -h 6`
64. **Human portrait, high key** — soft preset keeps skin from turning to noise. `gf --preset photo-soft -w 6 -h 8`
65. **Group photo panel** — provide a composed source image and inspect face detail at final size: `gf --input input/group-photo.png --preset photo-high-detail -w 12 -h 8`
66. **Silhouette profile pair** — the Victorian two-portrait format, still good. `gf --preset high-contrast -b 60 -w 5 -h 7`

---

## 7. Weddings and events (67–76)

Event work is the fastest route from hobby to invoice, because the deadline
is fixed and the client is already spending money.

67. **Save-the-date wooden cards** — batch-prep one image per card. Outputs are separate files, not a sheet layout; arrange and review them in the app. `gf --input input/card-art --preset line-art -w 4 -h 6`
68. **Guest-name place cards** — one image per guest, dropped in `input/`. `gf --preset line-art -w 3.5 -h 2`
69. **Table-number set** — create twelve source images, batch-prep the separate outputs, then arrange them in the app. `gf --input input/table-numbers --preset vector-graphic -w 5 -h 7`
70. **Ring-box lid engraving** — small, precise, high stakes. Test twice. `gf --preset vector-graphic -w 2 -h 2`
71. **Guest-book alternative panel** — prepare an illustration with margin for signatures: `gf --input input/guestbook.png --preset line-art -w 16 -h 10 --machine performance`. Review the real app work area before printing.
72. **Seating-chart panel** — provide a composed chart image and check type at actual size: `gf --input input/seating-chart.png --preset line-art -w 18 -h 10 --machine performance`. The app may provide less usable area than the nominal bed.
73. **Wedding-favor heart tags** — prepare heart-shaped art and an optional vector outline: `gf --input input/tag-art.png --preset coaster-heart --svg-cut -w 3 -h 3`. Add tag text and any hole in a vector design tool; this CLI does not add either.
74. **Bar-menu board** — compose the menu text and monogram in another tool, then prepare a 10 × 6 inch raster: `gf --input input/menu.png --preset vector-graphic -w 10 -h 6`.
75. **Cake-topper art plate** — engraved acrylic, back-side. `gf --preset acrylic -i -w 6 -h 4`
76. **Anniversary-gift reissue** — re-burn the invitation five years later, on wood. `gf --preset line-art -w 8 -h 10`

---

## 8. Kids, games and toys (77–86)

77. **Custom domino set** — create 28 tile source images and batch-prep them at one size. The CLI does not arrange the pieces on a sheet. `gf --input input/dominoes --preset high-contrast -w 1 -h 2`
78. **Chess-piece top inlays** — prepare a source image for each disc: `gf --input input/piece-art.png --preset vector-graphic --circle-cut --svg-cut -w 1 -h 1`. This does not make an inlay fit or cut a matching recess.
79. **Board-game player boards** — prototype a game you're designing. `gf --preset line-art -w 8 -h 5`
80. **Custom playing cards on veneer** — a full 52-card deck if you're patient. `gf --preset high-contrast -w 2.5 -h 3.5`
81. **Puzzle panel** — engrave the art, cut the puzzle grid as a vector. `gf --preset photo-high-detail -w 8 -h 10`
82. **Name puzzle for a toddler** — big letters, rounded, sanded smooth. `gf --preset vector-graphic -w 12 -h 4`
83. **Growth-chart ruler** — the six-foot design must be split into registered sections in another layout tool or handled with an approved passthrough workflow. This CLI does not segment long art. Prepare one section at a time, for example: `gf --input input/growth-chart-section-01.png --preset line-art -w 6 -h 12`.
84. **Coloring-panel for kids** — line art they fill in with markers. `gf --preset line-art --sharpen-percent 100 -w 8 -h 10`
85. **Maze plate** — engrave the maze, add a marble channel if you're ambitious. `gf --preset line-art -w 6 -h 6`
86. **Dinosaur / animal flash-card set** — batch-prep one source image per card: `gf --input input/cards --preset high-contrast -w 3 -h 4`. The CLI makes individual output files, not one arranged run.

---

## 9. Business offers to validate (87–96)

These are business hypotheses, not income forecasts. Before offering work,
calculate material, machine time, design/proof time, setup, packaging, fees,
shipping, taxes, rework, and local rules. Use customer-approved art and keep
the consent and proof process clear.

87. **Pet-portrait commissions** — offer a sample, collect a high-quality customer photo with permission, and price the design/proof time as well as production.
88. **Custom coaster sets** — test a small set size, packaging, and local demand before standardizing the offer.
89. **Personalized market-stall blanks** — make a limited number of samples, then customize only after agreeing on the name/art proof and material.
90. **Local-business signage** — quote from an approved design, dimensions, finish, installation needs, and material cost; start with one sample or small job.
91. **Event bundle** — scope a combination of cards, place pieces, numbers, and tags with a proof deadline, quantity, and replacement policy.
92. **Online photo-personalized listing** — explain image requirements, customer permissions, proof approval, delivery time, and how source photos are stored or deleted.
93. **Craft-fair bookmarks** — prototype a few sizes and finishes and track material waste, display cost, and time spent restocking.
94. **Corporate-gift batch** — confirm logo rights, quantity, finish, delivery date, payment terms, and test approval before promising a run.
95. **Engraving service for makers** — define who supplies compatible stock and production-ready artwork, who approves the proof, and who handles failures and pickup/shipping.
96. **Introductory class** — get maker-space approval, safety/operator coverage, accessible project instructions, and a realistic per-seat material budget.

---

## 10. Weird experiments (97–101)

No commercial justification. That is the point.

97. **Compare the same photo through the presets** — run it separately for each preset and compare the output images. The CLI does not yet generate a labeled preset contact sheet or grid.
98. **Engrave a photo of the laser onto a panel, photograph it, engrave that** — repeat until the image collapses into pure Atkinson noise. A generation-loss ladder.
99. **Settings-linked QR plaque** — the project does not yet write a settings sidecar or replay file. Today, keep a manual note of the CLI command, create a QR code pointing to that note in another tool, and combine it with your artwork.
100. **Dither a wood-grain photo onto a matching piece** — Atkinson dithering is currently the only built-in screen style; a classic halftone-dot option is a future enhancement.
101. **Make one small experiment with no commercial goal** — choose an image you like, prepare it, review the output, and learn from one proof. The point is to make something for the pleasure of it.

---

## When an entry doesn't work

- **Muddy, dark, no detail** → contrast too low or material too dark. Try `--contrast 2.0` and check #4.
- **Speckled and noisy** → `--denoise 3` (or `5` for AI-generated sources).
- **Output has speckled near-white areas** → inspect the source and compare `-c` plus different `--clean-solids-white` values. The wrapper enables `-c` by default; direct `uv run main.py` does not.
- **Fine lines bleeding together** → the sharpen halo is too aggressive. `--sharpen-percent 100`.
- **Blown-out highlights** → lower `-W`, e.g. `-W 235`.
- **Round shape came out too small** → you forgot `-h`. See rule 2 at the top.

The CLI does not select power/speed or validate stock safety. For its current behavior, see **[handbook.md](handbook.md)**; for command examples, see **[best-commands.md](best-commands.md)**. Ideas that require an additional tool are labeled in the entry.
