"""Settings resolution precedence and the manifest recipe spelling."""

import json
from dataclasses import replace

import pytest
from PIL import Image

from glowforge_it.batch import run_batch
from glowforge_it.cli import build_parser, main
from glowforge_it.settings import ProcessingSettings, ValidationError, load_recipe_file, resolve_settings, validate_limits
from glowforge_it.workflow import WorkflowOptions


def test_recipe_keys_preserve_cli_precedence():
    args = build_parser().parse_args(['--contrast', '1.2'])
    settings = resolve_settings(args, {
        'preset': 'photo-high-detail', 'black_thresh': 17,
        'denoise_radius': 0, 'contrast': 2.0,
    })
    assert settings.black_thresh == 17
    assert settings.denoise_radius == 0
    assert settings.contrast == 1.2
    assert settings.sharpen_percent == 200


def test_wrapped_recipe_rejects_sibling_processing_keys(tmp_path):
    path = tmp_path / 'recipe.json'
    path.write_text(json.dumps({'name': 'valid', 'recipe': {'contrast': 1.1}}))
    assert load_recipe_file(path) == {'contrast': 1.1}
    path.write_text(json.dumps({'recipe': {'contrast': 1.1}, 'contrasst': 1.8}))
    with pytest.raises(ValidationError, match='outside the recipe table.*contrasst'):
        load_recipe_file(path)


@pytest.mark.parametrize('recipe,error', [
    ({'qr_text': '\ud800'}, 'valid UTF-8'),
    ({'stamp_text': 'X\u2003Y'}, 'ASCII only'),
])
def test_invalid_mark_recipe_returns_structured_error(tmp_path, capsys, recipe, error):
    path = tmp_path / 'recipe.json'
    path.write_text(json.dumps(recipe))
    assert main(['--recipe', str(path), '--json', '--dry-run']) == 2
    result = json.loads(capsys.readouterr().out)
    assert error in result['errors'][0]


@pytest.mark.parametrize('recipe,field', [
    ({'contrast': 10**350}, 'contrast'),
    ({'workflow': {'material_mode': 'darkening', 'tone_gamma': 10**350}}, 'tone_gamma'),
])
def test_oversized_recipe_numbers_return_structured_error(tmp_path, capsys, recipe, field):
    path = tmp_path / 'recipe.json'
    path.write_text(json.dumps(recipe))
    assert main(['--recipe', str(path), '--json', '--dry-run']) == 2
    captured = capsys.readouterr()
    message = json.loads(captured.out)['errors'][0]
    assert field in message and 'finite' in message
    assert captured.err == ''


def test_oversized_api_numbers_raise_validation_errors():
    oversized = 10**5000
    with pytest.raises(ValidationError, match='contrast.*finite'):
        ProcessingSettings(contrast=oversized).validate()
    with pytest.raises(ValidationError, match='gamma.*finite'):
        WorkflowOptions(material_mode='darkening', tone_gamma=oversized).validate_tone()
    with pytest.raises(ValidationError, match='width_in.*finite'):
        validate_limits(oversized, None, 1000, None, None)


def test_manifest_records_wire_keys_and_guards_reuse(tmp_path):
    source = tmp_path / 'source.png'
    Image.new('L', (30, 30), 128).save(source)
    settings = ProcessingSettings(
        black_thresh=12, no_border=True, contrast=1.0,
        sharpen_radius=0, render_mode='ordered', manifest=True,
    )
    first = run_batch([str(source)], str(tmp_path / 'legacy'), settings, quiet=True)
    assert first.exit_code == 0
    with open(first.items[0].manifest_path) as handle:
        assert json.load(handle)['recipe']['black_thresh'] == 12
    reused = run_batch([str(source)], str(tmp_path / 'legacy'), quiet=True,
                       settings=settings, existing='skip')
    assert reused.exit_code == 0 and reused.skipped_count == 1
    # An unencoded material change must still invalidate verified reuse.
    changed = run_batch([str(source)], str(tmp_path / 'legacy'), quiet=True,
                        settings=replace(settings, material='different stock'), existing='skip')
    assert changed.exit_code == 1
    assert any('recipe does not match' in error for error in changed.errors)

