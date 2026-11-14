"""Artwork constraints shared by planning, production, and audition."""

import json
from pathlib import Path
from xml.etree import ElementTree

import pytest
from PIL import Image, ImageDraw, TiffImagePlugin

from glowforge_it.batch import run_batch
from glowforge_it.geometry import resolve_oriented_geometry
from glowforge_it.imaging import transform_image
from glowforge_it.proofing import run_audition
from glowforge_it.settings import ProcessingSettings
from glowforge_it.workflow import WorkflowOptions


def _oriented_tiff(path, orientation):
    exif = Image.Exif()
    exif[274] = orientation
    image = Image.new('L', (90, 20), 255)
    ImageDraw.Draw(image).rectangle((0, 0, 9, 4), fill=0)
    image.save(path, exif=exif)


@pytest.mark.parametrize('orientation', [5, 6, 7, 8])
def test_tiff_preflight_counts_exif_orientation_once_without_decoding(tmp_path, monkeypatch, orientation):
    source = tmp_path / 'source.tiff'
    _oriented_tiff(source, orientation)

    def forbid_decode(*args, **kwargs):
        pytest.fail('Preflight decoded TIFF pixels')

    monkeypatch.setattr(TiffImagePlugin.TiffImageFile, 'load', forbid_decode)
    assert resolve_oriented_geometry(source, width_in=0.3)[:4] == (20, 90, 90, 405)


def test_tiff_decoding_from_path_and_open_file_matches(tmp_path):
    source = tmp_path / 'source.tiff'
    _oriented_tiff(source, 6)
    settings = ProcessingSettings(render_mode='silhouette', no_border=True)
    with source.open('rb') as stream, Image.open(stream) as opened, Image.open(source) as named:
        from_stream = transform_image(opened, settings)
        from_path = transform_image(named, settings)
        assert named.filename == str(source)
    assert from_stream.size == from_path.size == (20, 90)
    assert from_stream.tobytes() == from_path.tobytes()


def test_tiff_artifact_and_audition_geometry_agree(tmp_path):
    source = tmp_path / 'portrait.tiff'
    _oriented_tiff(source, 6)
    settings = ProcessingSettings(render_mode='silhouette', no_border=True, contrast=1, sharpen_radius=0)
    workflow = WorkflowOptions(svg_operations=True)
    output = tmp_path / 'production'
    plan = run_batch([source], output, settings, workflow=workflow, dry_run=True, quiet=True)
    assert plan.items[0].output_size == (20, 90)
    written = run_batch([source], output, settings, workflow=workflow, quiet=True)
    assert written, written.to_dict()
    job = written.items[0]
    with Image.open(job.output_path) as artwork:
        assert artwork.size == (20, 90)
        assert artwork.getpixel((19, 0)) == 0
        assert artwork.getpixel((0, 0)) == 255
    svg = ElementTree.parse(job.artifacts['operations']).getroot()
    assert list(map(float, svg.attrib['viewBox'].split())) == [0, 0, 20, 90]
    assert job.workflow_summary['geometry']['canvas_px'] == [20, 90]

    audition = run_audition([source], tmp_path / 'audition', [('solid', settings)], width_in=0.3, quiet=True)
    assert audition, audition.to_dict()
    record = json.loads(Path(audition.items[0].manifest_path).read_text())
    assert record['candidates'][0]['output']['size_px'] == [90, 405]


def test_tiff_proof_panels_have_matching_orientation(tmp_path, monkeypatch):
    canvas = pytest.importorskip('reportlab.pdfgen.canvas')
    draw_image = canvas.Canvas.drawImage
    panels = []

    def record_panel_size(self, image, *args, **kwargs):
        panels.append(image.getSize())
        return draw_image(self, image, *args, **kwargs)

    monkeypatch.setattr(canvas.Canvas, 'drawImage', record_panel_size)
    source = tmp_path / 'source.tiff'
    _oriented_tiff(source, 6)
    result = run_batch([source], tmp_path / 'proof', ProcessingSettings(no_border=True),
                       workflow=WorkflowOptions(proof_sheet=True), quiet=True)
    assert result, result.to_dict()
    assert panels == [(20, 90), (20, 90)]


@pytest.mark.parametrize('limits,diagnostic', [
    ({}, 'Denoise intermediate'),
    ({'max_pixels': 200_000_000, 'max_memory': 2 * 1024**2}, 'exceeds budget'),
])
def test_preflight_bounds_denoise_workspace(tmp_path, limits, diagnostic):
    source = tmp_path / 'source.png'
    Image.new('L', (32, 32), 255).save(source)
    output = tmp_path / 'out'
    result = run_batch([source], output, ProcessingSettings(denoise_radius=10001), dry_run=True, quiet=True, **limits)
    assert result.exit_code == 1
    assert diagnostic in result.errors[0]
    assert not output.exists()
