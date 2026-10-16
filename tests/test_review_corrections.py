"""Regressions for transparency, quiet verification and iterable batch inputs."""

from dataclasses import replace
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from glowforge_it.batch import run_batch
from glowforge_it.cli import main
from glowforge_it.imaging import to_8bit, transform_image
from glowforge_it.planning import verify_job_manifest
from glowforge_it.proofing import run_audition
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions


BASE = ProcessingSettings(no_border=True, contrast=1, sharpen_radius=0, render_mode='silhouette')


@pytest.mark.parametrize('key,neighbor,gray', [(0, 1, 0), (32768, 32769, 128), (65535, 65534, 255)])
@pytest.mark.parametrize('polarity', ['legacy', 'darkening', 'lightening'])
def test_16bit_png_transparency_uses_original_samples(tmp_path, key, neighbor, gray, polarity):
    source = tmp_path / 'transparent16.png'
    samples = np.array([[key, neighbor], [0, 65535]], dtype=np.uint16)
    Image.fromarray(samples).save(source, transparency=key)
    with Image.open(source) as image:
        with to_8bit(image) as normalized:
            # The neighboring opaque sample quantizes to the same gray as the
            # key, but must remain opaque in the proof's source panel too.
            assert normalized.mode == 'LA'
            assert normalized.getpixel((0, 0)) == (gray, 0)
            assert normalized.getpixel((1, 0)) == (gray, 255)
            assert np.array_equal(np.asarray(normalized)[:, :, 1] == 0, samples == key)
        with transform_image(image, BASE, workflow=WorkflowOptions(material_mode=polarity)) as output:
            pixels = np.asarray(output.convert('L'))
            assert pixels[0, 0] == 255
            expected_neighbor = (0 if gray >= 127 else 255) if polarity == 'lightening' else (0 if gray <= 128 else 255)
            assert pixels[0, 1] == expected_neighbor
            assert pixels[1, 0] == (255 if key == 0 or polarity == 'lightening' else 0)
            assert pixels[1, 1] == (255 if key == 65535 or polarity != 'lightening' else 0)


@pytest.mark.parametrize('kind', ['production', 'audition'])
@pytest.mark.parametrize('polarity', ['legacy', 'darkening', 'lightening'])
def test_fully_transparent_16bit_png_never_becomes_an_engraving(tmp_path, kind, polarity):
    source = tmp_path / 'empty16.png'
    Image.fromarray(np.zeros((12, 12), dtype=np.uint16)).save(source, transparency=0)
    output = tmp_path / 'out'
    workflow = WorkflowOptions(material_mode=polarity)
    if kind == 'production':
        result = run_batch([str(source)], output, replace(BASE, manifest=True), workflow=workflow, quiet=True)
        assert result, result.to_dict()
        with Image.open(result.items[0].output_path) as image:
            assert np.all(np.asarray(image.convert('L')) == 255)
        assert verify_job_manifest(result.items[0].manifest_path, require_current_engine=True)[0]
    else:
        result = run_audition([str(source)], output, [('solid', BASE)], workflow=workflow, quiet=True)
        assert result, result.to_dict()
        metadata = json.loads(Path(result.items[0].manifest_path).read_text())
        assert metadata['candidates'][0]['burn'] == {'coverage': 0.0, 'bounds_px': None, 'no_engrave': True}


@pytest.mark.parametrize('failure,diagnostic', [('missing', 'Cannot parse manifest'),
                                             ('malformed', 'Cannot parse manifest'),
                                             ('tampered', 'hash mismatch'),
                                             ('runtime', 'engine/runtime differs')])
@pytest.mark.parametrize('json_output', [False, True])
def test_quiet_manifest_failures_keep_diagnostics(tmp_path, capsys, failure, diagnostic, json_output):
    source = tmp_path / 'source.png'
    Image.new('L', (8, 8), 255).save(source)
    result = run_batch([str(source)], tmp_path / 'out', replace(BASE, manifest=True), quiet=True)
    assert result
    manifest = Path(result.items[0].manifest_path)
    if failure == 'missing':
        manifest.unlink()
    elif failure == 'malformed':
        manifest.write_text('{broken')
    elif failure == 'tampered':
        Path(result.items[0].output_path).write_bytes(b'changed')
    else:
        data = json.loads(manifest.read_text())
        data['tool']['runtime']['engine'] = 'different-engine'
        manifest.write_text(json.dumps(data))
    args = ['--verify-manifest', str(manifest), '--quiet']
    if failure == 'runtime':
        args.append('--verify-current-engine')
    if json_output:
        args.append('--json')
    capsys.readouterr()
    assert main(args) == 1
    captured = capsys.readouterr()
    if json_output:
        data = json.loads(captured.out)
        assert data['success'] is False and data['exit_code'] == 1
        assert diagnostic in ' '.join(data['errors'])
        assert captured.err == ''
    else:
        assert captured.out == ''
        assert diagnostic in captured.err


def test_quiet_successful_manifest_verification_is_silent(tmp_path, capsys):
    source = tmp_path / 'source.png'
    Image.new('L', (8, 8), 255).save(source)
    result = run_batch([str(source)], tmp_path / 'out', replace(BASE, manifest=True), quiet=True)
    assert result
    capsys.readouterr()
    assert main(['--verify-manifest', result.items[0].manifest_path, '--quiet']) == 0
    captured = capsys.readouterr()
    assert captured.out == captured.err == ''


@pytest.mark.parametrize('kind', ['production', 'audition'])
@pytest.mark.parametrize('logging', ['normal', 'quiet', 'json'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_generator_of_mixed_path_inputs_is_independent_of_logging(tmp_path, capsys, kind, logging, dry_run):
    source = tmp_path / 'sources'
    source.mkdir()
    first, second = source / 'a.png', source / 'b.png'
    Image.new('L', (8, 8), 255).save(first)
    Image.new('L', (8, 8), 0).save(second)
    output = tmp_path / 'out'
    inputs = (path for path in (first, str(second)))
    options = dict(dry_run=dry_run, quiet=logging == 'quiet', json_output=logging == 'json')
    if kind == 'production':
        result = run_batch(inputs, output, BASE, **options)
    else:
        result = run_audition(inputs, output, [('solid', BASE)], **options)
    assert result, result.to_dict()
    assert [item.input_path for item in result.items] == [str(first), str(second)]
    assert [item.status for item in result.items] == ['planned' if dry_run else 'written'] * 2
    assert output.exists() == (not dry_run)
    captured = capsys.readouterr()
    assert captured.err == ''
    if logging == 'json':
        assert json.loads(captured.out)['success'] is True
    elif logging == 'quiet':
        assert captured.out == ''


@pytest.mark.parametrize('kind', ['production', 'audition'])
@pytest.mark.parametrize('nested_output', [False, True])
def test_generator_of_directories_keeps_mirroring_and_source_protection(tmp_path, kind, nested_output):
    source = tmp_path / 'sources'
    (source / 'nested').mkdir(parents=True)
    Image.new('L', (8, 8), 255).save(source / 'nested' / 'a.png')
    output = source / 'out' if nested_output else tmp_path / 'out'
    inputs = (path for path in [source])
    if kind == 'production':
        result = run_batch(inputs, output, BASE, quiet=True, dry_run=True)
    else:
        result = run_audition(inputs, output, [('solid', BASE)], quiet=True, dry_run=True)
    if nested_output:
        assert not result and 'inside input directory' in ' '.join(result.errors)
    else:
        assert result, result.to_dict()
        assert Path(result.items[0].output_path).parent == output / 'nested'
    assert not output.exists()


@pytest.mark.parametrize('kind', ['production', 'audition'])
def test_invalid_input_element_returns_a_planning_error(tmp_path, kind):
    if kind == 'production':
        result = run_batch([42], tmp_path / 'out', BASE, quiet=True, dry_run=True)
    else:
        result = run_audition([42], tmp_path / 'out', [('solid', BASE)], quiet=True, dry_run=True)
    assert result.exit_code == 1
    assert 'iterable of filesystem paths' in ' '.join(result.errors)
    assert not (tmp_path / 'out').exists()
