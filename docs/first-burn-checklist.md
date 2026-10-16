# First-burn acceptance record

Use a fresh generated job after the software checks pass. This template records app observations and physical measurements separately. Old files in ignored output folders are historical samples; do not assume their revision, dimensions or expected measurements apply to a new export.

## Identify the exact job

- Date/operator: ____________________
- Commit (if committed), development version and manifest runtime/source fingerprint: ____________________
- Source filename and SHA-256: ____________________
- Manifest path: ____________________
- Workflow revision (copy the full current value): ____________________
- Browser/app date and machine model: ____________________
- Stock label/supplier, measured thickness and measurement instrument/resolution: ____________________

Verify the archived files before importing. Substitute the actual manifest path:

```bash
gf --verify-manifest MANIFEST_PATH --json
```

To produce synthetic software-review samples:

```bash
uv run --extra proof scripts/maker_demo.py
```

The demo uses example dimensions and kerf. Measure real stock before generating a jig for fabrication; the demo is not a calibrated recipe.

## App import (no burn)

| Check | Expected from generated job | Observed / screenshot |
|---|---|---|
| Canvas width/height | SVG dimensions and workflow geometry | |
| Primary raster orientation and shape alignment | Inspect source, PNG and SVG together | |
| Legacy cut SVG | Embedded raster plus blue vector cut outline | |
| Unified SVG | Raster, red cuts and optional blue L score as distinct content | |
| Initial assignments and order | Record before changing anything | |
| Final assignments and order | Explicit operator review | |
| Trim placement | Same primary-art location as untrimmed control | |
| Text/QR masks | Separate imports at the recorded shared canvas offset; QR quiet zone intact | |
| Blank primary with personal mark | Import the mark even if SVG has no primary engraving | |
| Jig grid | Centers, pitch, dimensions and engraving quantity match metadata | |

Archive observations even when the app behaves differently. A successful import of one file is evidence for that file and environment, not all formats or machines. SVG embedding optimizations need their own representative import checks before changing defaults.

## One physical sample

Use the makerspace's approved stock, procedure and settings. Record the actual power, speed, passes, LPI, focus/height and operation order used; this tool does not choose them. Start with one sample or pocket and retain an untrimmed comparison when evaluating registration. For a jig, cut pockets first, secure it, then disable cuts/score and engrave the inserted blanks.

| Measurement | Expected / acceptance chosen before run | Observed |
|---|---|---|
| Width/height or diameter | Include expected kerf effect | |
| Primary artwork location relative to outline | Reference features and units | |
| Text legibility | Actual viewing distance and smallest text | |
| QR readability | Payload, device/scanner, distance, lighting | |
| Pocket fit | Blank and pocket dimensions | |
| Repeated placement | Number of trials and measured error | |
| Tonal/finish appearance | Retain photo and stock/context notes | |
| Timing | Actual app estimate and elapsed time, if comparing | |

Photo filenames and corresponding revision: ____________________

Stop on unexpected geometry or operation behavior and record the unchanged file/revision. Choose tolerances appropriate to the project before interpreting measurements; this checklist does not assert a calibrated accuracy threshold.

## Record the conclusion

- Software validation result and date: ____________________
- App observations: ____________________
- Physical measurements and limitations: ____________________
- Customer approval, if separately obtained: ____________________
- Follow-up change or decision: ____________________

Copy completed observations into the maker workflow acceptance record and roadmap with their evidence level. Generating a proof does not record customer approval, and a physical sample does not close untested combinations.
