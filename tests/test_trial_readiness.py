"""Regression probes for preflight, manifest failures, and trial output reuse."""
import json
import struct
import zlib

import pytest
from PIL import Image, ImageFile, PngImagePlugin

from glowforge_it.batch import run_batch
from glowforge_it.geometry import resolve_oriented_geometry
from glowforge_it.planning import estimate_image_memory, verify_job_manifest
from glowforge_it.settings import ProcessingSettings, ValidationError, resolve_settings
from glowforge_it.cli import build_parser


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


@pytest.mark.parametrize('metadata', ['none', 'early-exif', 'late-exif', 'late-xmp'])
def test_png_metadata_preflight_never_loads_pixels(tmp_path, monkeypatch, metadata):
    source = tmp_path / 'source.png'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (100, 10)).save(source, **({'exif': exif} if metadata == 'early-exif' else {}))
    if metadata.startswith('late'):
        data = source.read_bytes()
        if metadata == 'late-exif':
            chunk = png_chunk(b'eXIf', exif.tobytes()[6:])
        else:
            chunk = png_chunk(b'iTXt', b'XML:com.adobe.xmp\0\0\0\0\0<tiff:Orientation>6</tiff:Orientation>')
        source.write_bytes(data[:-12] + chunk + data[-12:])

    with monkeypatch.context() as m:
        def fail_decode(*args, **kwargs):
            pytest.fail('Pixel decoding was attempted during preflight')
        m.setattr(ImageFile.ImageFile, 'load', fail_decode)
        m.setattr(PngImagePlugin.PngImageFile, 'load', fail_decode)
        dims = resolve_oriented_geometry(str(source), width_in=1)
        assert dims[2:4] == ((300, 30) if metadata == 'none' else (300, 3000))
        result = run_batch([str(source)], str(tmp_path / 'out'), dry_run=True, max_memory=1, quiet=True)
        assert result.exit_code == 1
        assert 'exceeds budget' in result.errors[0]
        assert not (tmp_path / 'out').exists()

    # Metadata resolution must agree with the decoder, including late chunks.
    from PIL import ImageOps
    with Image.open(source) as image:
        assert ImageOps.exif_transpose(image).size == dims[:2]


def test_memory_estimate_covers_live_dither_buffers_and_is_shared(tmp_path):
    source = tmp_path / 'source.png'
    Image.new('RGB', (100, 100)).save(source)
    live_arrays = 100 * 100 * 8 + 2 * (100 + 3) * (100 + 2) * 8 + 100 * 100
    estimate = estimate_image_memory(str(source))
    assert estimate > live_arrays
    for budget, exit_code in ((150_000, 1), (estimate - 1, 1), (estimate, 0)):
        result = run_batch([str(source)], str(tmp_path / 'out'), dry_run=True, max_memory=budget, quiet=True)
        assert result.exit_code == exit_code
    with pytest.raises((OSError, ValueError)):
        estimate_image_memory(str(tmp_path / 'missing.png'))


@pytest.mark.parametrize('data', [[], None, 42, 'manifest', {'schema_version': '1.0', 'source': []}])
def test_malformed_manifest_is_a_failure_result(tmp_path, data):
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(data))
    valid, errors = verify_job_manifest(str(manifest))
    assert not valid and errors


def make_job(tmp_path):
    source = tmp_path / 'input' / 'art.png'
    source.parent.mkdir()
    Image.new('RGB', (12, 12), 'gray').save(source)
    result = run_batch([str(source)], str(tmp_path / 'out'), settings=ProcessingSettings(manifest=True), quiet=True)
    assert result.exit_code == 0
    return source, result.items[0]


def test_manifest_resolves_source_relative_to_manifest_not_cwd(tmp_path, monkeypatch):
    source, job = make_job(tmp_path)
    monkeypatch.chdir(tmp_path / 'out')
    assert verify_job_manifest(job.manifest_path) == (True, [])
    source.write_bytes(b'changed')
    valid, errors = verify_job_manifest(job.manifest_path)
    assert not valid and 'hash mismatch' in errors[0]


@pytest.mark.parametrize('damage', ['directory', 'bad-filename', 'bad-hash', 'outside-output', 'bad-relpath'])
def test_manifest_bad_records_and_unreadable_files_return_errors(tmp_path, damage):
    source, job = make_job(tmp_path)
    from pathlib import Path
    path = Path(job.manifest_path)
    data = json.loads(path.read_text())
    if damage == 'directory':
        source.unlink()
        source.mkdir()
    elif damage == 'bad-filename':
        data['source']['filename'] = []
    elif damage == 'bad-hash':
        data['source']['sha256'] = 123
    elif damage == 'outside-output':
        data['outputs'] = {'../input/art.png': next(iter(data['outputs'].values()))}
    else:
        data['source']['relpath'] = 123
    path.write_text(json.dumps(data))
    valid, errors = verify_job_manifest(str(path))
    assert not valid and errors


@pytest.mark.parametrize('options', [dict(settings=ProcessingSettings(manifest='false')),
                                     dict(settings=ProcessingSettings(material=None)),
                                     dict(settings=ProcessingSettings(material_thickness_in=None)),
                                    dict(width_in=float('nan')), dict(max_memory='1GB'), dict(max_pixels=None)])
def test_direct_api_rejects_invalid_batch_options_before_writes(tmp_path, options):
    result = run_batch(['not-used.png'], str(tmp_path / 'out'), quiet=True, **options)
    assert result.exit_code == 2
    assert not (tmp_path / 'out').exists()


def test_recipe_rejects_unknown_preset():
    with pytest.raises(ValidationError, match='preset'):
        resolve_settings(build_parser().parse_args([]), {'preset': 'coastr'})


@pytest.mark.parametrize('damage', ['source', 'output', 'recipe', 'missing-output-record'])
def test_manifest_skip_rejects_stale_or_incomplete_job(tmp_path, damage):
    source, job = make_job(tmp_path)
    output = str(tmp_path / 'out')
    assert run_batch([str(source)], output, settings=ProcessingSettings(manifest=True), existing='skip', quiet=True).skipped_count == 1
    options = {}
    if damage == 'source':
        Image.new('RGB', (12, 12), 'white').save(source)
    elif damage == 'output':
        from pathlib import Path
        Path(job.output_path).write_bytes(b'changed')
    elif damage == 'recipe':
        options['material'] = 'walnut'
    else:
        from pathlib import Path
        path = Path(job.manifest_path)
        data = json.loads(path.read_text())
        data['outputs'] = {'wrong.png': next(iter(data['outputs'].values()))}
        path.write_text(json.dumps(data))
    result = run_batch([str(source)], output, settings=ProcessingSettings(manifest=True, **options), existing='skip', quiet=True)
    assert result.exit_code == 1
    assert 'cannot reuse existing job' in result.errors[0]


def test_dry_run_includes_size_and_budget_and_rejects_blocked_root(tmp_path):
    source = tmp_path / 'art.png'
    Image.new('RGB', (20, 10)).save(source)
    output = tmp_path / 'out'
    result = run_batch([str(source)], str(output), width_in=1, dry_run=True, quiet=True)
    item = result.to_dict()['items'][0]
    assert item['output_size'] == (300, 150)
    assert item['estimated_memory_bytes'] == estimate_image_memory(str(source), width_in=1)
    output.write_text('must remain unchanged')
    result = run_batch([str(source)], str(output / 'nested'), dry_run=True, quiet=True)
    assert result.exit_code == 1
    assert output.read_text() == 'must remain unchanged'


def test_manifest_publication_failure_restores_entire_previous_generation(tmp_path, monkeypatch):
    from pathlib import Path
    from glowforge_it import publication
    source = tmp_path / 'art.png'
    Image.new('RGB', (12, 12), 'gray').save(source)
    options = dict(settings=ProcessingSettings(manifest=True, svg_cut=True, circle_cut=True), quiet=True)
    output = tmp_path / 'out'
    first = run_batch([str(source)], str(output), **options)
    assert first.exit_code == 0
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    Image.new('RGB', (12, 12), 'black').save(source)
    real_replace = publication.os.replace
    failed = False

    def fail_manifest_once(src, dst):
        nonlocal failed
        if not failed and str(dst).endswith('_manifest.json') and Path(src).name.startswith('.gf-'):
            failed = True
            raise OSError('injected manifest publication failure')
        return real_replace(src, dst)

    monkeypatch.setattr(publication.os, 'replace', fail_manifest_once)
    result = run_batch([str(source)], str(output), **options)
    assert result.exit_code == 1 and failed
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_installed_gf_default_and_explicit_override(tmp_path):
    from glowforge_it.cli import gf_main
    source = tmp_path / 'art.png'
    Image.new('RGB', (12, 12), 'gray').save(source)
    for extra, expected in (([], True), (['--no-clean-solids'], False)):
        output = tmp_path / str(expected)
        assert gf_main(['--input', str(source), '-o', str(output), '--manifest', '--quiet', *extra]) == 0
        manifest = json.loads(next(output.glob('*_manifest.json')).read_text())
        assert manifest['recipe']['clean_solids'] is expected


def test_gf_clean_solids_default_yields_to_recipe(tmp_path):
    """The gf wrapper's clean-solids default ranks below a recipe; only explicit flags beat it."""
    from glowforge_it.cli import gf_main
    source = tmp_path / 'art.png'
    Image.new('RGB', (12, 12), 'gray').save(source)
    recipe = tmp_path / 'r.toml'
    recipe.write_text('clean_solids = false\n')
    output = tmp_path / 'out'
    assert gf_main(['--input', str(source), '-o', str(output), '--recipe', str(recipe), '--manifest', '--quiet']) == 0
    manifest = json.loads(next(output.glob('*_manifest.json')).read_text())
    assert manifest['recipe']['clean_solids'] is False
