"""Selected audition export preserves recipes, source identity and production safeguards."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw
import pytest

from glowforge_it import batch, export
from glowforge_it.batch import export_audition_candidate
from glowforge_it.cli import gf_main, main
from glowforge_it.imaging import transform_image
from glowforge_it.planning import verify_job_manifest
from glowforge_it.proofing import run_audition
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions


BASE = ProcessingSettings(contrast=1, sharpen_radius=0, no_border=True)


def make_audition(tmp_path, *, settings=BASE, workflow=None, width_in=None, height_in=None):
    source = tmp_path / 'art--line-art.png'
    values = np.tile(np.linspace(0, 255, 31).astype('uint8'), (17, 1))
    image = Image.fromarray(values)
    ImageDraw.Draw(image).rectangle((2, 2, 6, 9), fill=255)
    image.save(source)
    candidates = [('dots', settings), ('solid', replace(settings, render_mode='silhouette', silhouette_threshold=100))]
    result = run_audition([source], tmp_path / 'audition', candidates, workflow=workflow,
                          width_in=width_in, height_in=height_in, quiet=True)
    assert result, result.to_dict()
    record = Path(result.items[0].manifest_path)
    return source, record, candidates


@pytest.mark.parametrize('fit,width,height,polarity', [
    ('stretch', None, None, 'legacy'),
    ('contain', .101, None, 'legacy'),
    ('cover', None, .077, 'lightening'),
    ('contain', .1, .1, 'darkening'),
    ('cover', .1, .1, 'legacy'),
    ('stretch', .1, .08, 'legacy'),
])
@pytest.mark.parametrize('selector,index', [('1', 0), ('solid', 1)])
def test_selection_exports_exact_full_resolution_pixels(tmp_path, monkeypatch, fit, width, height, polarity, selector, index):
    workflow = WorkflowOptions(material_mode=polarity)
    source, record, candidates = make_audition(tmp_path, settings=replace(BASE, fit_mode=fit),
        workflow=workflow, width_in=width, height_in=height)
    saved = record.read_bytes()
    metadata = json.loads(saved)
    monkeypatch.chdir(tmp_path.parent)  # resolve source against the record, not cwd
    output = tmp_path / 'final'
    assert gf_main(['--export-audition', str(record), '--candidate', selector, '-o', str(output), '--quiet']) == 0
    png = next(output.glob('*.png'))
    with Image.open(source) as original, transform_image(original, candidates[index][1],
            workflow=workflow, width_in=width, height_in=height) as expected, Image.open(png) as actual:
        assert actual.mode == expected.mode
        assert actual.size == expected.size
        assert actual.tobytes() == expected.tobytes()
        assert hashlib.sha256(actual.tobytes()).hexdigest() == metadata['candidates'][index]['output']['pixels_sha256']
    manifest = next(output.glob('*_manifest.json'))
    assert verify_job_manifest(manifest, require_current_engine=True)[0]
    recipe = json.loads(manifest.read_text())['recipe']
    assert recipe['preset'] == candidates[index][0]
    assert recipe['clean_solids'] is False  # gf's default and filename preset must not alter selection
    assert recipe['width_in'] == width and recipe['height_in'] == height
    assert recipe['audition_pixels_sha256'] == metadata['candidates'][index]['output']['pixels_sha256']
    assert record.read_bytes() == saved


def test_cli_can_select_a_preset_name_and_reuse_export(tmp_path):
    source = tmp_path / 'art.png'
    Image.new('L', (8, 8), 140).save(source)
    assert main(['--input', str(source), '--audition', 'photo-soft', 'stamp',
                 '-o', str(tmp_path / 'audition'), '--quiet']) == 0
    record = tmp_path / 'audition' / 'art_audition.json'
    output = tmp_path / 'final'
    args = ['--export-audition', str(record), '--candidate', 'photo-soft', '-o', str(output), '--quiet']
    assert gf_main(args) == 0
    saved = {p.name: p.read_bytes() for p in output.iterdir()}
    assert gf_main([*args, '--existing', 'skip']) == 0
    assert {p.name: p.read_bytes() for p in output.iterdir()} == saved
    assert gf_main([*args, '--existing', 'error']) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == saved


@pytest.mark.parametrize('change', ['missing_pixel_hash', 'same_pixel_size_different_request'])
def test_audition_reuse_requires_an_exact_export_record(tmp_path, change):
    source, record, candidates = make_audition(tmp_path, width_in=.1)
    if change == 'missing_pixel_hash':
        data = json.loads(record.read_text())
        del data['candidates'][1]['output']['pixels_sha256']
        record.write_text(json.dumps(data))
    width = .1 if change == 'missing_pixel_hash' else .10001
    original = record.read_bytes()
    result = run_audition([source], record.parent, candidates, width_in=width,
                          existing='skip', quiet=True)
    assert result.exit_code == 1 and 'cannot reuse existing audition' in result.errors[0]
    assert record.read_bytes() == original


def test_moved_record_accepts_a_source_override_and_dry_run_is_read_only(tmp_path, capsys):
    source, record, _ = make_audition(tmp_path)
    moved = tmp_path / 'moved' / 'elsewhere'
    shutil.copytree(record.parent, moved)
    moved_record = moved / record.name
    original = moved_record.read_bytes()
    output = tmp_path / 'final'
    assert gf_main(['--export-audition', str(moved_record), '--candidate', '2', '--input', str(source),
                    '-o', str(output), '--dry-run', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['items'][0]['status'] == 'planned'
    assert data['items'][0]['manifest_path']
    assert not output.exists()
    assert moved_record.read_bytes() == original


@pytest.mark.parametrize('selector', ['0', '-1', '3', 'missing'])
def test_unknown_candidate_reports_available_choices_without_output(tmp_path, capsys, selector):
    _, record, _ = make_audition(tmp_path)
    result = export_audition_candidate(record, selector, tmp_path / 'final', quiet=True)
    assert result.exit_code == 2
    assert '1: dots, 2: solid' in result.errors[0]
    assert 'Unknown audition candidate' in capsys.readouterr().err
    assert not (tmp_path / 'final').exists()


@pytest.mark.parametrize('change,message', [
    ('source', 'source hash mismatch'), ('sheet', 'contact-sheet hash mismatch'),
    ('runtime', 'engine/runtime differs'), ('old', 'regenerate the audition'),
    ('size', 'dimensions do not match'), ('recipe', 'complete resolved recipes'),
    ('hash', 'valid pixel hash'), ('root', 'Cannot load audition candidate'),
    ('workflow', 'Cannot load audition candidate'), ('malformed', 'Cannot load audition candidate'),
])
def test_invalid_or_stale_records_fail_without_outputs(tmp_path, capsys, change, message):
    source, record, _ = make_audition(tmp_path)
    data = json.loads(record.read_text())
    if change == 'source':
        Image.new('L', (31, 17), 0).save(source)
    elif change == 'sheet':
        record.with_suffix('.png').write_bytes(b'changed')
    elif change == 'runtime':
        data['tool']['identity']['engine'] = 'old'
    elif change == 'old':
        del data['audition']['export_version']
    elif change == 'size':
        data['candidates'][0]['output']['size_px'] = [1, 1]
    elif change == 'recipe':
        del data['candidates'][0]['recipe']['contrast']
    elif change == 'hash':
        data['candidates'][0]['output']['pixels_sha256'] = 'invalid'
    elif change == 'root':
        data = []
    elif change == 'workflow':
        data['audition']['workflow'] = {'version': 'burn-v1', 'unknown': True}
    record.write_text('{bad' if change == 'malformed' else json.dumps(data))
    assert gf_main(['--export-audition', str(record), '--candidate', '1',
                    '-o', str(tmp_path / 'final'), '--json']) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert message in result['errors'][0]
    assert captured.err == ''
    assert not (tmp_path / 'final').exists()


def test_pixel_mismatch_preserves_existing_generation(tmp_path):
    _, record, _ = make_audition(tmp_path)
    output = tmp_path / 'final'
    assert export_audition_candidate(record, '1', output, quiet=True)
    saved = {p.name: p.read_bytes() for p in output.iterdir()}
    data = json.loads(record.read_text())
    data['candidates'][0]['output']['pixels_sha256'] = '0' * 64
    record.write_text(json.dumps(data))
    result = export_audition_candidate(record, '1', output, quiet=True)
    assert result.exit_code == 1 and 'Rendered pixels differ' in result.items[0].error_message
    assert {p.name: p.read_bytes() for p in output.iterdir()} == saved


def test_source_change_between_selection_and_planning_is_rejected(tmp_path, monkeypatch):
    source, record, _ = make_audition(tmp_path)
    original = batch.plan_batch

    def mutate_then_plan(*args, **kwargs):
        Image.new('L', (31, 17), 0).save(source)
        return original(*args, **kwargs)

    monkeypatch.setattr(batch, 'plan_batch', mutate_then_plan)
    result = export_audition_candidate(record, '1', tmp_path / 'final', quiet=True)
    assert result.exit_code == 1
    assert 'Source changed since the audition' in result.errors[0]
    assert not list((tmp_path / 'final').glob('*'))


def test_selection_respects_memory_preflight(tmp_path, monkeypatch):
    _, record, _ = make_audition(tmp_path)
    monkeypatch.setattr(export, 'transform_image', lambda *args, **kwargs: pytest.fail('Rendered over budget'))
    result = export_audition_candidate(record, '1', tmp_path / 'final', max_memory=1, dry_run=True, quiet=True)
    assert result.exit_code == 1 and 'exceeds budget' in ' '.join(result.errors)
    assert not (tmp_path / 'final').exists()


@pytest.mark.parametrize('protected', ['record', 'sheet'])
def test_selection_cannot_replace_its_review_inputs(tmp_path, protected):
    source, record, _ = make_audition(tmp_path)
    output = tmp_path / 'final'
    planned = export_audition_candidate(record, '1', output, dry_run=True, quiet=True)
    assert planned
    output.mkdir()
    if protected == 'record':
        # Even a renamed record placed at the production manifest path is an
        # input, and must not be replaced by that manifest.
        target = Path(planned.items[0].manifest_path)
        shutil.copyfile(record, target)
        shutil.copyfile(record.with_suffix('.png'), output / record.with_suffix('.png').name)
        used_record, guarded = target, target
    else:
        guarded = record.with_suffix('.png')
        Path(planned.items[0].output_path).symlink_to(guarded)
        used_record = record
    saved = guarded.read_bytes()
    result = export_audition_candidate(used_record, '1', output, source_path=source, quiet=True)
    assert result.exit_code == 1 and 'would overwrite the source image' in ' '.join(result.errors)
    assert guarded.read_bytes() == saved


def test_invalid_record_path_is_a_structured_api_error(tmp_path):
    result = export_audition_candidate(None, '1', tmp_path / 'final', quiet=True)
    assert result.exit_code == 2 and 'Cannot load audition candidate' in result.errors[0]
    assert not (tmp_path / 'final').exists()


@pytest.mark.parametrize('extra', [
    ['--contrast', '2'], ['--width', '1'], ['--no-clean-solids'], ['--border'],
    ['--manifest'], ['--svg-cut'], ['--trim'], ['--preset', 'stamp'],
    ['--recipe', 'missing.json'], ['--audition', 'stamp'], ['--verify-manifest', 'missing.json'],
    ['--input', 'a.png', 'b.png'],
])
def test_selection_rejects_conflicting_cli_options(extra, capsys):
    assert gf_main(['--export-audition', 'unused.json', '--candidate', '1', '--json', *extra]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['errors']


@pytest.mark.parametrize('args', [['--candidate', '1'], ['--export-audition', 'unused.json']])
def test_selection_flags_require_each_other(args, capsys):
    assert main([*args, '--json']) == 2
    assert 'requires' in json.loads(capsys.readouterr().out)['errors'][0]
