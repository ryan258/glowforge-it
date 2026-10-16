"""Cross-feature and boundary regressions from the October project review."""

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import pytest

from glowforge_it import export, publication
from glowforge_it.batch import run_batch
from glowforge_it.cli import main
from glowforge_it.contracts import artifact_paths, runtime_identity, snapshot_source
from glowforge_it.imaging import transform_image
from glowforge_it.planning import verify_job_manifest
from glowforge_it.proofing import run_audition
from glowforge_it.settings import ProcessingSettings, ValidationError
from glowforge_it.vector import trace_skeleton
from glowforge_it.workflow import WorkflowOptions


BASE = ProcessingSettings(no_border=True, contrast=1, sharpen_radius=0, render_mode='silhouette')


def make_source(tmp_path, value=255, size=(300, 300), name='source.png'):
    path = tmp_path / name
    Image.new('L', size, value).save(path)
    return str(path)


def burns(path):
    with Image.open(path) as image:
        rgba = np.asarray(image.convert('RGBA'))
        return (rgba[:, :, 0] < 128) & (rgba[:, :, 3] > 0)


def test_source_mutation_after_render_preserves_previous_generation(tmp_path, monkeypatch):
    src = make_source(tmp_path, 0, (20, 20))
    output = tmp_path / 'output'
    settings = replace(BASE, manifest=True)
    first = run_batch([src], str(output), settings, quiet=True)
    assert first
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    original = export.transform_image

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        Image.new('L', (20, 20), 255).save(src)
        return result

    monkeypatch.setattr(export, 'transform_image', mutate)
    result = run_batch([src], str(output), settings, quiet=True)
    assert not result
    assert 'Source changed' in result.items[0].error_message
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


def test_snapshot_rejects_a_different_planned_generation(tmp_path):
    src = make_source(tmp_path)
    with pytest.raises(ValidationError, match='after planning'):
        with snapshot_source(src, '0' * 64):
            pytest.fail('Changed source was accepted')


def test_trim_preserves_every_tone_layer_in_a_shared_canvas(tmp_path):
    src = tmp_path / 'tones.png'
    image = Image.new('L', (100, 100), 255)
    ImageDraw.Draw(image).rectangle((10, 15, 89, 84), fill=192)
    ImageDraw.Draw(image).rectangle((40, 40, 59, 59), fill=0)
    image.save(src)
    results = [run_batch([str(src)], str(tmp_path / str(trim)), replace(BASE, tone_layers=2),
                         workflow=WorkflowOptions(trim=trim), quiet=True) for trim in (False, True)]
    assert all(results)
    for index in (1, 2):
        untrimmed = burns(results[0].items[0].artifacts[f'tone_layer_{index}'])
        trimmed = burns(results[1].items[0].artifacts[f'tone_layer_{index}'])
        assert int(untrimmed.sum()) == int(trimmed.sum())
        assert np.array_equal(untrimmed[15:85, 10:90], trimmed)
    assert results[1].items[0].workflow_summary['trim']['offset_px'] == [10, 15]


def test_white_source_is_no_burn_in_every_tone_layer(tmp_path):
    src = make_source(tmp_path, size=(20, 20))
    result = run_batch([src], str(tmp_path / 'out'), replace(BASE, tone_layers=4), quiet=True)
    assert result
    assert all(not burns(path).any() for path in result.items[0].artifacts.values())


def test_text_cannot_invade_qr_quiet_zone(tmp_path):
    src = make_source(tmp_path)
    settings = replace(BASE, stamp_text='HELLO', stamp_position='top-left', qr_text='HELLO', qr_position='top-left')
    result = run_batch([src], str(tmp_path / 'out'), settings, quiet=True)
    assert not result and 'overlap' in result.items[0].error_message
    assert not list((tmp_path / 'out').glob('*.png'))


def test_preview_and_no_engrave_include_personalization(tmp_path):
    src = make_source(tmp_path)
    options = WorkflowOptions(preview_finish=True, trim=True)
    records = []
    for text in (None, 'HELLO'):
        result = run_batch([src], str(tmp_path / str(text)), replace(BASE, stamp_text=text), workflow=options, quiet=True)
        assert result, result.to_dict()
        records.append(result.items[0].workflow_summary)
    assert records[0]['mask']['no_engrave']
    assert not records[1]['mask']['no_engrave']
    assert records[0]['appearance']['pixels_sha256'] != records[1]['appearance']['pixels_sha256']
    assert records[1]['separate_engraving_sidecars'] == ['stamp']


@pytest.mark.parametrize('alias', ['same', 'hardlink', 'symlink'])
def test_direct_export_protects_source_aliases(tmp_path, alias):
    src = Path(make_source(tmp_path, 127, (20, 20)))
    dest = src if alias == 'same' else tmp_path / 'alias.png'
    if alias == 'hardlink':
        dest.hardlink_to(src)
    elif alias == 'symlink':
        dest.symlink_to(src)
    before = src.read_bytes()
    with pytest.raises(ValidationError, match='overwrite the source'):
        export.prep_for_glowforge(src, dest, BASE, quiet=True)
    assert src.read_bytes() == before


def test_direct_export_checks_every_sidecar_destination(tmp_path):
    src = make_source(tmp_path, name='out_stamp.png')
    with pytest.raises(ValidationError, match='overwrite the source'):
        export.prep_for_glowforge(src, tmp_path / 'out.png', replace(BASE, stamp_text='OK'), quiet=True)


def test_public_transform_uses_shared_validation():
    with pytest.raises(ValidationError, match='Contrast'):
        transform_image(Image.new('L', (8, 8)), replace(BASE, contrast=-1))
    with pytest.raises(ValidationError, match='width_in'):
        transform_image(Image.new('L', (8, 8)), BASE, width_in=float('nan'))


def test_rotated_intermediate_is_in_memory_and_pixel_preflight(tmp_path, monkeypatch):
    src = make_source(tmp_path, 128, (2000, 2))
    settings = replace(BASE, render_mode='halftone', halftone_angle=45)
    def no_rotation(*args, **kwargs):
        pytest.fail('Rotation must not allocate after preflight failure')
    monkeypatch.setattr(Image.Image, 'rotate', no_rotation)
    budget = run_batch([src], str(tmp_path / 'budget'), settings, max_memory=2*1024*1024, quiet=True)
    assert not budget and 'exceeds budget' in budget.errors[0]
    pixels = run_batch([src], str(tmp_path / 'pixels'), settings, max_pixels=100_000, quiet=True)
    assert not pixels and 'intermediate' in pixels.errors[0]
    with pytest.raises(ValidationError, match='exceeds budget'):
        export.prep_for_glowforge(src, tmp_path / 'direct.png', settings, max_memory=2*1024*1024, quiet=True)


def test_vector_point_guard_precedes_adjacency(monkeypatch):
    import glowforge_it.vector as vector
    monkeypatch.setattr(vector, '_neighbors', lambda *args: pytest.fail('Allocated adjacency before the point guard'))
    with pytest.raises(ValueError, match='point limit'):
        trace_skeleton(np.ones((10, 10), dtype=bool), max_points=20)


def test_cleanup_failure_is_written_with_recoverable_warning(tmp_path, monkeypatch):
    src = make_source(tmp_path, 0, (20, 20))
    output = tmp_path / 'out'
    assert run_batch([src], str(output), BASE, quiet=True)
    unlink = publication.os.unlink
    def fail_backup(path, *args, **kwargs):
        if Path(path).name.startswith('.gf-prev-'):
            raise PermissionError('injected cleanup failure')
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(publication.os, 'unlink', fail_backup)
    result = run_batch([src], str(output), BASE, quiet=True)
    assert result and result.written_count == 1
    warning = result.items[0].cleanup_warnings[0]
    assert Path(warning['backup']).exists()
    assert Path(warning['destination']).exists()


@pytest.mark.parametrize('extra', [['--nonsense'], ['--contrast', '-1'], ['--recipe', 'missing.toml'], ['--score-marks']])
def test_json_usage_errors_are_structured(extra, capsys):
    assert main(['--json', *extra]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result['exit_code'] == 2 and result['errors']
    assert captured.err == ''


@pytest.mark.parametrize('field,value', [('stamp_text', 'José'), ('qr_text', 'HELLO'), ('tone_layers', 2), ('svg_linework', True)])
def test_audition_rejects_unrepresented_sidecars(tmp_path, field, value):
    src = make_source(tmp_path)
    result = run_audition([src], str(tmp_path / 'out'), [('test', replace(BASE, **{field: value}))], quiet=True)
    assert result.exit_code == 2 and 'production sidecars' in result.errors[0]


def test_audition_budget_includes_contact_sheet(tmp_path):
    src = make_source(tmp_path, size=(1, 1))
    result = run_audition([src], str(tmp_path / 'out'), [('a', BASE), ('b', BASE)], max_memory=2*1024*1024, dry_run=True, quiet=True)
    assert not result and not (tmp_path / 'out').exists()


def test_archive_integrity_and_current_engine_are_distinct(tmp_path, capsys):
    src = make_source(tmp_path, size=(20, 20))
    result = run_batch([src], str(tmp_path / 'out'), replace(BASE, manifest=True), quiet=True)
    assert result
    path = Path(result.items[0].manifest_path)
    data = json.loads(path.read_text())
    assert data['tool']['runtime'] == runtime_identity()
    assert 'segno' in data['tool']['runtime']['libraries']
    data['tool']['runtime']['engine'] = 'old-engine'
    path.write_text(json.dumps(data))
    assert verify_job_manifest(path)[0]
    assert not verify_job_manifest(path, require_current_engine=True)[0]
    assert main(['--verify-manifest', str(path), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['verification'] == 'archive-integrity'
    assert not run_batch([src], str(tmp_path / 'out'), replace(BASE, manifest=True), existing='skip', quiet=True)


def test_inferred_preset_is_validated_before_dry_run_succeeds(tmp_path):
    src = make_source(tmp_path, name='art--line-art.png')
    result = run_batch([src], str(tmp_path / 'out'), replace(BASE, white_thresh=10), dry_run=True, quiet=True)
    assert not result and 'black threshold' in result.errors[0]


def test_planner_and_export_share_every_artifact_path(tmp_path):
    src = make_source(tmp_path)
    settings = replace(BASE, manifest=True, stamp_text='HELLO', svg_linework=True)
    options = WorkflowOptions(trim=True)
    result = run_batch([src], str(tmp_path / 'out'), settings, workflow=options, quiet=True)
    assert result
    item = result.items[0]
    expected = artifact_paths(item.output_path, settings, options)
    assert set(expected.values()) == {item.output_path, item.manifest_path, *item.artifacts.values()}
    assert all(Path(path).is_file() for path in expected.values())


def test_trim_preserves_qr_quiet_zone(tmp_path):
    src = make_source(tmp_path)
    result = run_batch([src], str(tmp_path / 'out'), replace(BASE, qr_text='HELLO'),
                       workflow=WorkflowOptions(trim=True), quiet=True)
    assert result
    item = result.items[0]
    mask = burns(item.artifacts['qr'])
    assert mask.shape == (29*4, 29*4)
    assert not mask[:16].any() and not mask[-16:].any()
    assert not mask[:, :16].any() and not mask[:, -16:].any()
    assert item.workflow_summary['trim']['offset_px'] == item.workflow_summary['qr']['bounds_px'][:2]


@pytest.mark.parametrize('settings,workflow,machine', [
    (replace(BASE, tone_layers=2), WorkflowOptions(preview_finish=True), None),
    (replace(BASE, stamp_text='HI'), WorkflowOptions(jig='rectangle', blank_width=1, blank_height=1,
      pocket_clearance=0.01, jig_margin=0.25), 'performance'),
])
def test_unrepresented_production_combinations_fail_preflight(tmp_path, settings, workflow, machine):
    src = make_source(tmp_path)
    result = run_batch([src], str(tmp_path / 'out'), settings, workflow=workflow,
                       machine=machine, dry_run=True, quiet=True)
    assert result.exit_code == 2
    assert not (tmp_path / 'out').exists()


def test_oversized_font_rejected_before_glyph_allocation(monkeypatch):
    from glowforge_it import personalization
    monkeypatch.setattr(personalization.ImageFont, 'load_default', lambda **kwargs: pytest.fail('Font allocated'))
    with pytest.raises(ValueError, match='exceeds the canvas'):
        personalization.render_text_stamp(Image.new('1', (20, 20)), 'X', size_px=10**9)


@pytest.mark.parametrize('change', ['source', 'recipe', 'sheet'])
def test_audition_skip_rejects_stale_or_modified_review(tmp_path, change):
    src = make_source(tmp_path, 128, (20, 20))
    output = str(tmp_path / 'out')
    candidates = [('a', BASE)]
    first = run_audition([src], output, candidates, quiet=True)
    assert first
    if change == 'source':
        Image.new('L', (20, 20), 0).save(src)
    elif change == 'recipe':
        candidates = [('a', replace(BASE, silhouette_threshold=10))]
    else:
        Path(first.items[0].output_path).write_bytes(b'changed')
    result = run_audition([src], output, candidates, existing='skip', quiet=True)
    assert not result and 'cannot reuse' in result.errors[0]


def test_manifest_requires_adjacent_artifacts(tmp_path):
    src = make_source(tmp_path)
    with pytest.raises(ValidationError, match='adjacent'):
        export.prep_for_glowforge(src, tmp_path / 'out.png', replace(BASE, manifest=True),
                                 manifest_path=tmp_path / 'elsewhere' / 'manifest.json', quiet=True)
