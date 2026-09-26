"""Settings resolution precedence and the manifest recipe spelling."""

import json
from dataclasses import replace

from PIL import Image

from glowforge_it.batch import run_batch
from glowforge_it.cli import build_parser
from glowforge_it.settings import ProcessingSettings, resolve_settings


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

