"""Build wheel/sdist and smoke-test isolated installs; run explicitly, never on import.

Requires `build` in the invoking environment (uv can install it without pip).
Uses uv for temporary environments and installation when available, otherwise
stdlib venv/pip. Downloads build/runtime dependencies into temporary environments
outside the repository. No upload or release occurs.
"""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shlex
import shutil
import sys
import tempfile
import venv


ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, expected=0):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    completed = subprocess.run([str(arg) for arg in command], cwd=cwd, env=env,
                               text=True, capture_output=True)
    if completed.returncode != expected:
        raise RuntimeError(f"Command failed: {command}\n{completed.stdout}\n{completed.stderr}")
    return completed.stdout


def check_install(archive, work):
    work.mkdir()
    environment = work / 'venv'
    bindir = environment / ('Scripts' if os.name == 'nt' else 'bin')
    python = bindir / ('python.exe' if os.name == 'nt' else 'python')
    gf = bindir / ('gf.exe' if os.name == 'nt' else 'gf')
    cli = bindir / ('glowforge-it.exe' if os.name == 'nt' else 'glowforge-it')
    uv = shutil.which('uv')
    print(f'CHECK: {archive.name}: isolated environment via {"uv" if uv else "venv/pip"}', flush=True)
    if uv:
        # uv creates an unseeded environment and installs into its explicit
        # interpreter. This avoids executing ensurepip in uv-managed Python.
        run([uv, 'venv', '--no-project', '--python', sys.executable, environment], cwd=work)
        install = [uv, 'pip', 'install', '--python', python]
    else:
        venv.EnvBuilder(with_pip=True, symlinks=os.name != 'nt').create(environment)
        install = [python, '-m', 'pip', 'install']
    run([*install, archive], cwd=work)
    run([python, '-c', (
        'from pathlib import Path; import sys, glowforge_it; '
        'assert Path(glowforge_it.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); '
        'from PIL import Image; Image.new("L", (40, 40), 128).save("source.png")'
    )], cwd=work)
    run([python, '-c', 'import importlib.util; assert importlib.util.find_spec("reportlab") is None'], cwd=work)
    run([gf, '--version'], cwd=work)
    run([cli, '--version'], cwd=work)
    common = ['--input', 'source.png', '--render-mode', 'silhouette', '--no-border', '--json']
    plain = json.loads(run([cli, *common, '-o', 'plain', '--preview-finish'], cwd=work))
    assert plain['summary']['written'] == 1, plain
    missing = json.loads(run([cli, *common, '-o', 'missing-proof', '--proof-sheet'], cwd=work, expected=2))
    assert 'proof' in str(missing['errors']).lower(), missing
    run([*install, f'{archive}[proof]'], cwd=work)
    proof = json.loads(run([gf, *common, '-o', 'proof', '--proof-sheet'], cwd=work))
    assert proof['summary']['written'] == 1, proof
    manifest = next((work / 'proof').glob('*_manifest.json'))
    verified = json.loads(run([cli, '--verify-manifest', manifest, '--verify-current-engine', '--json'], cwd=work))
    assert verified['success'], verified
    assert next((work / 'proof').glob('*_proof.pdf')).read_bytes().startswith(b'%PDF-')
    print(f'PASS: {archive.name}: isolated import, both commands, optional proof dependency, export and manifest verification')


def main():
    if importlib.util.find_spec('build') is None:
        raise SystemExit(
            'Missing build dependency in the invoking Python environment.\n'
            'Install it without requiring pip in that environment:\n'
            f'  uv pip install -p {shlex.quote(sys.executable)} build\n'
            'Then rerun this script.'
        )
    with tempfile.TemporaryDirectory(prefix='gf-distribution-') as directory:
        work = Path(directory)
        dist = work / 'dist'
        run([sys.executable, '-m', 'build', '--outdir', dist], cwd=ROOT)
        wheels = list(dist.glob('*.whl'))
        sources = list(dist.glob('*.tar.gz'))
        assert len(wheels) == len(sources) == 1, list(dist.iterdir())
        check_install(wheels[0], work / 'wheel')
        check_install(sources[0], work / 'sdist')


if __name__ == '__main__':
    main()
