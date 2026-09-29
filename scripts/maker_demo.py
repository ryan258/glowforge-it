"""Generate synthetic, asymmetric acceptance artifacts; no customer artwork needed.

Run from the repository: uv run --extra proof scripts/maker_demo.py
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from glowforge_it.batch import run_batch
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / 'output' / 'maker-demo'
    target.mkdir(parents=True, exist_ok=True)
    source = target / 'synthetic-source.png'
    image = Image.new('RGB', (600, 600), 'white')
    draw = ImageDraw.Draw(image)
    draw.polygon([(105, 400), (240, 175), (315, 300), (385, 240), (495, 400)], fill='#555555')
    draw.polygon([(200, 240), (240, 175), (280, 240), (240, 225)], fill='white')
    draw.ellipse((360, 105, 430, 175), fill='black')
    draw.line((135, 450, 465, 450), fill='black', width=4)
    draw.text((245, 475), 'SAMPLE 01', fill='black', font_size=22)
    image.save(source)
    shared = dict(settings=ProcessingSettings(no_border=True, contrast=1, sharpen_radius=0, circle_cut=True), quiet=True)
    options = WorkflowOptions(svg_operations=True, score_marks=True, material_mode='darkening',
                              proof_sheet=True, trim=True,
                              client='Synthetic demonstration - no customer', order='SAMPLE-01')
    proof = run_batch([str(source)], str(target / 'proof'), workflow=options, **shared)
    jig = run_batch([str(source)], str(target / 'jig'), machine='performance',
                    workflow=WorkflowOptions(jig='circle', blank_width=2.02, blank_height=2.02,
                        pocket_clearance=.01, jig_margin=.25, jig_rows=2, jig_columns=3,
                        kerf=.006, trim=True, score_marks=True), **shared)
    for result in (proof, jig):
        if not result:
            raise RuntimeError(result.to_dict())
        for item in result.items:
            for name, path in item.artifacts.items():
                print(f'{name}: {path}')


if __name__ == '__main__':
    main()
