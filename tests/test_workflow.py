"""Maker workflow acceptance: mask invariants, physical registration and artifact integrity."""
import base64
from dataclasses import replace
import io
import json
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
import pytest

from glowforge_it.batch import run_batch
from glowforge_it.cli import main
from glowforge_it.imaging import transform_image
from glowforge_it.planning import verify_job_manifest
from glowforge_it.workflow import (WorkflowOptions, layout, burn_mask, finish_preview,
                                   render_operations, orientation_advice, digest)

NS = {'s': 'http://www.w3.org/2000/svg'}


def transform(img, **kwargs):
    return transform_image(img, no_border=True, contrast=1, sharpen_radius=0, **kwargs)


@pytest.mark.parametrize('mode,expected', [('darkening', [0, 255]), ('lightening', [255, 0])])
def test_polarity_endpoints_and_no_burn_padding(mode, expected):
    img = Image.new('L', (2, 1))
    img.putdata([0, 255])
    result = transform(img, workflow=WorkflowOptions(material_mode=mode))
    assert np.asarray(result.convert('L')).ravel().tolist() == expected
    contained = transform(img, workflow=WorkflowOptions(material_mode=mode), width_in=.04, height_in=.04, fit_mode='contain')
    assert set(np.asarray(contained.crop((0, 0, 12, 3)).convert('L')).ravel()) == {255}
    transparent = Image.new('RGBA', (8, 8), (255, 255, 255, 0))
    assert burn_mask(transform(transparent, workflow=WorkflowOptions(material_mode=mode))).getbbox() is None


@pytest.mark.parametrize('mode', ['darkening', 'lightening'])
def test_curve_ramp_monotonic_coverage(mode):
    coverage = []
    for value in (0, 40, 80, 120, 160, 200, 255):
        img = transform(Image.new('L', (30, 30), value), workflow=WorkflowOptions(material_mode=mode, tone_gamma=1.7, tone_black=20, tone_white=235))
        coverage.append(np.asarray(burn_mask(img)).mean())
    assert coverage == sorted(coverage, reverse=mode == 'darkening')


def test_polarity_is_not_mirroring():
    img = Image.new('L', (7, 3), 0)
    img.putpixel((1, 1), 255)
    result = burn_mask(transform(img, workflow=WorkflowOptions(material_mode='lightening')))
    assert result.getbbox() == (1, 1, 2, 2)


def test_preview_determinism_and_mask_immutability():
    img = Image.new('1', (60, 40), 1)
    img.putpixel((20, 20), 0)
    before = img.tobytes()
    options = WorkflowOptions(preview_finish=True)
    a, b = finish_preview(img, options), finish_preview(img, options)
    assert a.tobytes() == b.tobytes()
    assert a.getpixel((20, 20)) == (100, 58, 29)
    assert img.tobytes() == before
    assert a.tobytes() != finish_preview(img, replace(options, preview_seed=1)).tobytes()


def test_svg_trim_preserves_pixels_and_coordinates():
    img = Image.new('1', (60, 40), 1)
    img.paste(0, (13, 7, 20, 19))
    options = WorkflowOptions(svg_operations=True, score_marks=True, trim=True)
    root = ET.fromstring(render_operations(img, options, layout(options, img.size), circle_cut=True))
    raster = root.find('.//s:image', NS)
    assert (raster.get('x'), raster.get('y')) == ('13.00000000', '7.00000000')
    embedded = Image.open(io.BytesIO(base64.b64decode(raster.get('href').split(',')[1])))
    assert embedded.size == (7, 12)
    assert embedded.tobytes() == img.crop((13, 7, 20, 19)).tobytes()
    assert root.get('viewBox') == '0 0 60.00000000 40.00000000'
    assert root.find("s:g[@id='cut']", NS).get('stroke') == '#ff0000'
    assert root.find("s:g[@id='score']", NS).get('stroke') == '#0000ff'
    assert len(root.findall('.//s:circle', NS)) == 1


def test_jig_registered_grid_and_kerf():
    options = WorkflowOptions(jig='rectangle', blank_width=2, blank_height=1,
                              pocket_clearance=.01, jig_margin=.25, kerf=.006,
                              jig_rows=2, jig_columns=3)
    options.validate(machine='performance')
    geo = layout(options, (300, 150), machine='performance')
    assert len(geo['pockets']) == 6
    for placement, pocket in zip(geo['placements_px'], geo['pockets']):
        assert [placement[0] + 150, placement[1] + 75] == pocket['center_px']
        assert pocket['finished_size_px'][0] - pocket['path_size_px'][0] == pytest.approx(1.8)
    with pytest.raises(ValueError, match='exceed'):
        layout(replace(options, jig_columns=20), (300, 150), machine='spark')


@pytest.mark.parametrize('options', [WorkflowOptions(material_mode='lightening', preview_finish=True),
    WorkflowOptions(tone_black=255), WorkflowOptions(score_marks=True),
    WorkflowOptions(jig='circle'), WorkflowOptions(optimize_orientation=True),
    WorkflowOptions(tone_gamma=float('nan')), WorkflowOptions(jig_rows=0),
    WorkflowOptions(material_mode='darkening', tone_gamma=True)])
def test_invalid_configuration(options):
    with pytest.raises(ValueError):
        options.validate()


def test_orientation_uses_lpi_and_constraints():
    options = WorkflowOptions(optimize_orientation=True, engraving_lpi=100)
    geo = layout(options, (900, 300))
    advice = orientation_advice(options, geo, (0, 0, 900, 300), 'spark')
    assert [x['scan_rows'] for x in advice['candidates']] == [100, 300]
    assert advice['timing_calibrated'] is False
    locked = orientation_advice(replace(options, orientation_constraint='reading'), geo, (0, 0, 900, 300), 'spark')
    assert not locked['candidates'][1]['feasible']


def source(tmp_path):
    path = tmp_path / 'source.png'
    img = Image.new('RGB', (90, 60), 'white')
    img.paste('black', (20, 10, 50, 30))
    img.save(path)
    return path


def test_complete_generation_plan_reuse_and_tamper(tmp_path):
    src = source(tmp_path)
    out = tmp_path / 'out'
    options = WorkflowOptions(svg_operations=True, score_marks=True, preview_finish=True, proof_sheet=True, trim=True)
    kwargs = dict(workflow=options, no_border=True, contrast=1, sharpen_radius=0, quiet=True)
    planned = run_batch([str(src)], str(out), dry_run=True, **kwargs)
    assert planned and not out.exists()
    assert set(planned.items[0].artifacts) == {'operations', 'finish', 'proof', 'workflow'}
    result = run_batch([str(src)], str(out), **kwargs)
    assert result, result.to_dict()
    job = result.items[0]
    assert verify_job_manifest(job.manifest_path)[0]
    record = json.loads(open(job.artifacts['workflow']).read())
    revision = record.pop('revision')
    assert revision == digest(record)
    assert record['appearance_sha256'] == digest(record['appearance'])
    assert not record['customer_approved']
    assert run_batch([str(src)], str(out), existing='skip', **kwargs).skipped_count == 1
    with open(job.artifacts['finish'], 'ab') as f:
        f.write(b'tamper')
    assert not run_batch([str(src)], str(out), existing='skip', **kwargs)


def test_blank_trim_has_no_engraving(tmp_path):
    src = tmp_path / 'blank.png'
    Image.new('L', (20, 30), 255).save(src)
    result = run_batch([str(src)], str(tmp_path / 'out'), workflow=WorkflowOptions(trim=True), no_border=True, quiet=True)
    assert result
    item = result.items[0]
    assert item.workflow_summary['mask']['no_engrave']
    assert Image.open(item.output_path).size == (1, 1)
    assert not ET.parse(item.artifacts['operations']).findall('.//s:image', NS)


def test_workflow_memory_limit_and_blocked_sidecar(tmp_path):
    src = source(tmp_path)
    opts = WorkflowOptions(preview_finish=True)
    kwargs = dict(workflow=opts, quiet=True)
    out = tmp_path / 'out'
    planned = run_batch([str(src)], str(out), dry_run=True, **kwargs)
    assert not run_batch([str(src)], str(out), max_memory=planned.items[0].estimated_memory_bytes - 1, **kwargs)
    from pathlib import Path
    Path(planned.items[0].artifacts['finish']).mkdir()
    result = run_batch([str(src)], str(out), **kwargs)
    assert not result
    assert not Path(planned.items[0].output_path).exists()
    assert not list(out.glob('.gf-*'))


def test_cli_recipe_workflow(tmp_path, capsys):
    src = source(tmp_path)
    recipe = tmp_path / 'recipe.toml'
    recipe.write_text('[workflow]\nmaterial_mode="lightening"\ntone_gamma=1.2\n')
    assert main(['--input', str(src), '-o', str(tmp_path / 'out'), '--recipe', str(recipe), '--dry-run', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['items'][0]['artifacts']['workflow'].endswith('_workflow.json')


def test_trim_keeps_intentional_border(tmp_path):
    src = tmp_path / 'border.png'
    Image.new('L', (20, 30), 255).save(src)
    result = run_batch([str(src)], str(tmp_path / 'out'), workflow=WorkflowOptions(trim=True), quiet=True)
    assert result
    assert Image.open(result.items[0].output_path).size == (20, 30)
    assert result.items[0].workflow_summary['mask']['bounds_px'] == [0, 0, 20, 30]


def test_preview_does_not_change_engraving_and_revision_changes(tmp_path):
    from pathlib import Path
    src = source(tmp_path)
    kwargs = dict(quiet=True, no_border=True, contrast=1, sharpen_radius=0)
    baseline = run_batch([str(src)], str(tmp_path / 'base'), **kwargs)
    opts = WorkflowOptions(preview_finish=True)
    preview = run_batch([str(src)], str(tmp_path / 'preview'), workflow=opts, **kwargs)
    assert baseline and preview
    assert Path(baseline.items[0].output_path).read_bytes() == Path(preview.items[0].output_path).read_bytes()
    first = preview.items[0].workflow_summary['revision']
    with Image.open(src) as im:
        im.putpixel((3, 3), (0, 0, 0))
        im.save(src)
    changed = run_batch([str(src)], str(tmp_path / 'preview'), workflow=opts, **kwargs)
    assert changed and changed.items[0].workflow_summary['revision'] != first


def test_proof_failure_preserves_generation(tmp_path, monkeypatch):
    from pathlib import Path
    import glowforge_it.export as export
    src = source(tmp_path)
    kwargs = dict(workflow=WorkflowOptions(proof_sheet=True, svg_operations=True), quiet=True)
    first = run_batch([str(src)], str(tmp_path / 'out'), **kwargs)
    assert first
    item = first.items[0]
    paths = [item.output_path, item.manifest_path, *item.artifacts.values()]
    before = {p: Path(p).read_bytes() for p in paths}
    def fail(*args, **kwargs):
        raise OSError('synthetic PDF failure')
    monkeypatch.setattr(export, 'write_proof', fail)
    failed = run_batch([str(src)], str(tmp_path / 'out'), **kwargs)
    assert not failed
    assert before == {p: Path(p).read_bytes() for p in paths}
    assert not list((tmp_path / 'out').glob('.gf-*'))


def test_single_pixel_trim_and_extreme_threshold():
    img = Image.new('L', (20, 30), 255)
    img.putpixel((2, 17), 0)
    result = transform(img, workflow=WorkflowOptions(material_mode='darkening'), dither_thresh=255)
    assert burn_mask(result).getbbox() == (2, 17, 3, 18)


def test_pocket_svg_centers_match_embedded_artwork():
    opts = WorkflowOptions(jig='circle', blank_width=1, blank_height=1, pocket_clearance=.01,
                           jig_margin=.25, jig_rows=2, jig_columns=2)
    image = Image.new('1', (150, 150), 0)
    geo = layout(opts, image.size, machine='spark', circle_cut=True)
    root = ET.fromstring(render_operations(image, opts, geo, circle_cut=True))
    circles = root.findall('.//s:circle', NS)
    images = root.findall('.//s:image', NS)
    assert len(circles) == len(images) == 4
    for cut, raster in zip(circles, images):
        assert float(cut.get('cx')) == pytest.approx(float(raster.get('x')) + float(raster.get('width'))/2)
        assert float(cut.get('cy')) == pytest.approx(float(raster.get('y')) + float(raster.get('height'))/2)
