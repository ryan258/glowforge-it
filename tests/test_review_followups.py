"""Focused regressions for the five project-review follow-ups."""

from dataclasses import replace
import json
from pathlib import Path
import warnings

import numpy as np
from PIL import Image, ImageDraw
import pytest

from glowforge_it import export
from glowforge_it.batch import run_batch
from glowforge_it.cli import main
from glowforge_it.contracts import artifact_paths
from glowforge_it.imaging import to_8bit
from glowforge_it.planning import verify_job_manifest
from glowforge_it.proofing import render_audition_sheet, run_audition
from glowforge_it.settings import ProcessingSettings, ValidationError
from glowforge_it.workflow import WorkflowOptions


BASE = ProcessingSettings(no_border=True, contrast=1, sharpen_radius=0, render_mode='silhouette')
SIDECARS = [('stamp_text', 'HI', 'stamp'), ('qr_text', 'HELLO', 'qr'),
            ('tone_layers', 2, 'tone_layer_1'), ('svg_linework', True, 'linework')]


def source_image(tmp_path, size=(160, 160)):
    source = tmp_path / 'source.png'
    Image.new('L', size, 255).save(source)
    return str(source)


def generation_bytes(directory):
    return {path.name: path.read_bytes() for path in directory.iterdir()}


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf')])
@pytest.mark.parametrize('kind', ['production', 'audition'])
def test_nonfinite_tiff_fails_without_replacing_previous_generation(tmp_path, value, kind):
    source = tmp_path / 'source.tiff'
    samples = np.tile(np.linspace(0, 1, 20, dtype=np.float32), (20, 1))
    Image.fromarray(samples).save(source)
    output = tmp_path / 'output'

    def run():
        if kind == 'production':
            return run_batch([str(source)], str(output), replace(BASE, manifest=True), quiet=True)
        return run_audition([str(source)], str(output), [('solid', BASE)], quiet=True)

    assert run()
    previous = generation_bytes(output)
    samples[0, 0] = value
    Image.fromarray(samples).save(source)
    with warnings.catch_warnings():
        warnings.simplefilter('error', RuntimeWarning)
        result = run()
    assert result.exit_code == 1
    assert 'NaN or infinity' in result.items[0].error_message
    assert generation_bytes(output) == previous


@pytest.mark.parametrize('mode,value', [('F', 5), ('I', -1), ('I', 70000)])
def test_constant_grayscale_without_a_recognized_scale_is_rejected(mode, value):
    with Image.new(mode, (2, 2), value) as source:
        with pytest.raises(ValidationError, match='Constant grayscale'):
            to_8bit(source)


@pytest.mark.parametrize('mode,value,expected', [('F', 0, 0), ('F', 1, 255),
                                               ('I', 0, 0), ('I', 255, 255), ('I', 65535, 255)])
def test_constant_grayscale_with_a_recognized_scale_keeps_its_endpoint(mode, value, expected):
    with Image.new(mode, (2, 2), value) as source, to_8bit(source) as result:
        assert np.all(np.asarray(result) == expected)


@pytest.mark.parametrize('field,value,role', SIDECARS)
def test_new_sidecars_plan_manifests_and_reject_corrupt_or_incomplete_reuse(tmp_path, field, value, role):
    source = source_image(tmp_path)
    output = tmp_path / 'output'
    settings = replace(BASE, **{field: value})  # manifest=False is deliberately retained
    planned = run_batch([source], str(output), settings, dry_run=True, quiet=True)
    assert planned and planned.items[0].manifest_path
    assert not output.exists()
    written = run_batch([source], str(output), settings, quiet=True)
    item = written.items[0]
    assert written and item.manifest_path == planned.items[0].manifest_path
    manifest = Path(item.manifest_path)
    data = json.loads(manifest.read_text())
    assert data['recipe']['manifest'] is True
    assert Path(item.artifacts[role]).name in data['outputs']
    assert verify_job_manifest(manifest)[0]
    assert run_batch([source], str(output), settings, existing='skip', quiet=True).skipped_count == 1
    sidecar = Path(item.artifacts[role])
    sidecar.write_bytes(b'not the generated artifact')
    assert not run_batch([source], str(output), settings, existing='skip', quiet=True)
    assert run_batch([source], str(output), settings, quiet=True)
    manifest.unlink()
    incomplete = run_batch([source], str(output), settings, existing='skip', quiet=True)
    assert not incomplete and 'incomplete existing output' in incomplete.errors[0]


@pytest.mark.parametrize('field,value,role', SIDECARS)
def test_direct_sidecar_exports_include_a_manifest(tmp_path, field, value, role):
    source = source_image(tmp_path)
    settings = replace(BASE, **{field: value})
    result = export.prep_for_glowforge(source, tmp_path / 'export.png', settings, quiet=True)
    expected = artifact_paths(tmp_path / 'export.png', settings, WorkflowOptions())
    assert result['manifest_path'] == expected['manifest']
    assert result['artifacts'][role] == expected[role]
    assert verify_job_manifest(result['manifest_path'])[0]


def test_cli_cannot_disable_the_manifest_required_by_a_sidecar(tmp_path, capsys):
    source = source_image(tmp_path)
    assert main(['--input', source, '-o', str(tmp_path / 'out'), '--stamp-text', 'HI',
                 '--no-border', '--no-manifest', '--json']) == 0
    result = json.loads(capsys.readouterr().out)
    assert verify_job_manifest(result['items'][0]['manifest_path'])[0]


@pytest.mark.parametrize('cut', [False, True])
def test_legacy_png_and_cut_exports_keep_manifest_optional(tmp_path, cut):
    result = export.prep_for_glowforge(source_image(tmp_path), tmp_path / 'out.png',
                                      replace(BASE, circle_cut=cut, svg_cut=cut), quiet=True)
    assert result['manifest_path'] is None
    assert not (tmp_path / 'out_manifest.json').exists()


@pytest.mark.parametrize('requested', [{'prompt': 'SECOND', 'model': 'MODEL-1'},
                                     {'prompt': 'FIRST', 'model': 'MODEL-2'},
                                     {'prompt': None, 'model': None}])
def test_reuse_rejects_changed_or_cleared_provenance_without_mutation(tmp_path, requested):
    source = source_image(tmp_path)
    output = tmp_path / 'output'
    settings = replace(BASE, manifest=True)
    original = {'prompt': 'FIRST', 'model': 'MODEL-1'}
    first = run_batch([source], str(output), settings, **original, quiet=True)
    assert first
    previous = generation_bytes(output)
    assert run_batch([source], str(output), settings, **original, existing='skip', quiet=True).skipped_count == 1
    rejected = run_batch([source], str(output), settings, **requested, existing='skip', quiet=True)
    assert not rejected and 'provenance' in rejected.errors[0]
    assert generation_bytes(output) == previous
    assert verify_job_manifest(first.items[0].manifest_path)[0]  # archive checks remain independent
    replaced = run_batch([source], str(output), settings, **requested, quiet=True)
    assert replaced
    assert json.loads(Path(replaced.items[0].manifest_path).read_text())['provenance'] == requested


@pytest.mark.parametrize('value', ['two', 2.5, 10**9])
def test_direct_export_validates_before_any_artifact_expansion(tmp_path, monkeypatch, value):
    source = source_image(tmp_path)
    before = Path(source).read_bytes()
    settings = replace(BASE, tone_layers=value)
    monkeypatch.setattr(export, 'artifact_paths', lambda *args: pytest.fail('Expanded invalid artifact settings'))
    with pytest.raises(ValidationError, match='Tone layers|tone_layers'):
        export.prep_for_glowforge(source, tmp_path / 'out' / 'art.png', settings, quiet=True)
    with pytest.raises(ValidationError, match='Tone layers|tone_layers'):
        artifact_paths(tmp_path / 'out' / 'art.png', settings, WorkflowOptions())
    assert not (tmp_path / 'out').exists()
    assert Path(source).read_bytes() == before


@pytest.mark.parametrize('size,names', [((100, 600), ['photo-high-detail']),
                                     ((100, 600), ['photo-high-detail', 'low-res-enhance']),
                                     ((600, 100), ['photo-high-detail', 'low-res-enhance']),
                                     ((100, 600), ['A' * 600, 'second', 'third'])])
def test_audition_text_fits_the_sheet_and_does_not_overlap(tmp_path, monkeypatch, size, names):
    source = tmp_path / ('long-source-' * 15 + '.png')
    Image.new('L', size, 255).save(source)
    text_bounds = []
    original = ImageDraw.ImageDraw.multiline_text

    def draw_text(draw, xy, text, *args, **kwargs):
        text_bounds.append(draw.multiline_textbbox(xy, text, font=kwargs['font'], spacing=kwargs['spacing']))
        return original(draw, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, 'multiline_text', draw_text)
    sheet, metadata = render_audition_sheet(str(source), [(name, BASE) for name in names])
    try:
        assert len(text_bounds) == len(names) + 1
        for left, top, right, bottom in text_bounds:
            assert 0 <= left < right <= sheet.width
            assert 0 <= top < bottom <= sheet.height
        for index, (left, top, right, bottom) in enumerate(text_bounds):
            for other_left, other_top, other_right, other_bottom in text_bounds[index + 1:]:
                assert right <= other_left or other_right <= left or bottom <= other_top or other_bottom <= top
        assert [record['output']['size_px'] for record in metadata['candidates']] == [list(size)] * len(names)
    finally:
        sheet.close()


def test_audition_memory_budget_includes_wrapped_text_before_rendering(tmp_path, monkeypatch):
    import glowforge_it.proofing as proofing
    source = source_image(tmp_path, (20, 20))
    candidates = [('A' * 2000, BASE)]
    planned = run_audition([source], str(tmp_path / 'planned'), candidates, dry_run=True, quiet=True)
    short = run_audition([source], str(tmp_path / 'short'), [('A', BASE)], dry_run=True, quiet=True)
    budget = planned.items[0].estimated_memory_bytes
    assert budget > short.items[0].estimated_memory_bytes
    assert run_audition([source], str(tmp_path / 'fits'), candidates, max_memory=budget, quiet=True)
    monkeypatch.setattr(proofing, 'transform_image', lambda *args, **kwargs: pytest.fail('Rendered over budget'))
    rejected = run_audition([source], str(tmp_path / 'blocked'), candidates,
                            max_memory=budget - 1, dry_run=True, quiet=True)
    assert not rejected and 'exceeds budget' in rejected.errors[0]
    assert not (tmp_path / 'blocked').exists()
    with pytest.raises(ValidationError, match='exceeds budget'):
        render_audition_sheet(source, candidates, max_memory=budget - 1)
