# First-burn acceptance record

Use a fresh generated job and record software checks, app observations, and physical measurements separately. Keep the printed paths with your observations so you can identify the exact files later.

## Generate the synthetic acceptance pack

From the checkout with the proof extra installed in `.venv`, run:

```bash
.venv/bin/python scripts/maker_demo.py
```

For a checkout without that environment, run `uv run --extra proof scripts/maker_demo.py`.

The script creates a fresh `output/maker-demo/run-*` folder, prints the manifest and SVG paths, and verifies each job against the current engine. The legacy circle and heart and the unified trim pair start on 2 × 2 inch canvases. Use the jig's workflow JSON for its dimensions. Keep the folder together so the manifests can still find the source. For an independent recheck, use the same Python environment as the generator and substitute the printed manifest path.

```bash
.venv/bin/python main.py --verify-manifest "MANIFEST_PATH" --verify-current-engine --json
```

## Identify the exact job

- Date/operator: ____________________
- Commit (if committed), development version and manifest runtime/source fingerprint: ____________________
- Source filename and SHA-256: ____________________
- Manifest path: ____________________
- Workflow revision (copy the full current value): ____________________
- Browser/app date and machine model: ____________________
- Stock label/supplier, measured thickness and measurement instrument/resolution: ____________________

## App import (no burn)

Start with the legacy circle SVG. Check canvas size, raster orientation, outline alignment, and initial operation assignments. Record the observed order before changing any assignment. Compare the remaining cases as time and energy allow.

| Pack case | Check in the Glowforge app or local PDF viewer | Observed / screenshot |
|---|---|---|
| Legacy circle and heart SVGs | Each includes the engraving raster and one blue cut outline. Compare app size and outline alignment with the manifest and source. | |
| Unified untrimmed and trimmed SVGs | Compare imported canvas and artwork placement. Check the embedded raster, red cut path, and blue L score as separate content. Record any differences in app bounds. | |
| Proof PDF and simulated finish | Inspect one-page layout, source and finish orientation, full revision text, and the blank sign-off fields. | |
| Pocket jig SVG | Compare canvas, centers, pitch, and six artwork placements with its workflow metadata. | |

Record which cases you opened and keep the observations even when the app behaves differently. For a separate personalization job, check text and QR masks at their recorded shared canvas offset, including the QR quiet zone. A blank primary can still have an engraving mask to import.

## One physical sample

Use the makerspace's approved stock, procedure and settings. Record the actual power, speed, passes, LPI, focus/height and operation order used. Start with one sample or pocket and retain an untrimmed comparison when evaluating registration. The synthetic jig uses example dimensions and kerf. Measure your blanks and use your measured parameters for fabrication. Follow the [two-phase jig workflow](maker-workflow.md#registered-pocket-jig-one-blank-then-a-grid) for pocket cuts and engraving.

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
