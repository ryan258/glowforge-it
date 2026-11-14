"""Generate synthetic, asymmetric acceptance artifacts; no customer artwork needed.

Run from the repository: .venv/bin/python scripts/maker_demo.py
"""
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from shutil import copyfile
import sys
from tempfile import mkdtemp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from glowforge_it.batch import run_batch
from glowforge_it.planning import verify_job_manifest
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions


def main():
    if find_spec('reportlab') is None:
        raise SystemExit("The demo's proof needs ReportLab. Run: uv run --extra proof scripts/maker_demo.py")
    root = Path(__file__).resolve().parents[1]
    parent = root / 'output' / 'maker-demo'
    parent.mkdir(parents=True, exist_ok=True)
    target = Path(mkdtemp(prefix='run-', dir=parent))
    source = target / 'coaster-source.png'
    copyfile(root / 'docs' / 'examples' / source.name, source)

    base = ProcessingSettings(no_border=True, contrast=1, sharpen_radius=0, manifest=True)
    circle = replace(base, circle_cut=True)
    operations = WorkflowOptions(svg_operations=True, score_marks=True, material_mode='darkening')
    trimmed = replace(operations, trim=True, proof_sheet=True,
                      client='Synthetic demonstration', order='SAMPLE-01')
    jig = WorkflowOptions(jig='circle', blank_width=2.02, blank_height=2.02,
                          pocket_clearance=.01, jig_margin=.25, jig_rows=2, jig_columns=3,
                          kerf=.006, trim=True, score_marks=True)
    cases = (
        ('legacy-circle', replace(circle, svg_cut=True), WorkflowOptions()),
        ('legacy-heart', replace(base, heart_cut=True, svg_cut=True), WorkflowOptions()),
        ('unified-untrimmed', circle, operations),
        ('unified-trimmed', circle, trimmed),
        ('jig', circle, jig),
    )
    print(f'Acceptance pack: {target}', flush=True)
    print(f'Source: {source}')
    for name, settings, workflow in cases:
        result = run_batch([source], target / name, settings, workflow=workflow,
                           width_in=2, height_in=2, machine='performance',
                           existing='error', quiet=True)
        if not result:
            raise SystemExit(f'{name}: {result.to_json()}')
        item = result.items[0]
        valid, errors = verify_job_manifest(item.manifest_path, require_current_engine=True)
        if not valid:
            raise SystemExit(f'{name} manifest verification failed: ' + ' '.join(errors))
        print(f'\n{name}')
        print(f'  primary: {item.output_path}')
        print(f'  verified manifest: {item.manifest_path}')
        if item.svg_path:
            print(f'  cut SVG: {item.svg_path}')
        for role, path in item.artifacts.items():
            print(f'  {role}: {path}')
        for warning in item.cleanup_warnings or ():
            print(f'  publication cleanup needs review: {warning["journal"]}', file=sys.stderr)


if __name__ == '__main__':
    main()
