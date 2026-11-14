"""The docs cannot drift from the CLI: documented commands run, and every flag is documented."""

import importlib.util
import re
import shlex
from pathlib import Path
from shutil import copytree

from PIL import Image

from glowforge_it.cli import build_parser, gf_main, main

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
# CHANGELOG and roadmap are history and plans: they legitimately mention removed or future flags.


def _commands(text):
    """`gf ...` lines from fenced blocks (joining backslash continuations) and inline code."""
    found = []
    for block in re.findall(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", text, re.S):
        found += [line.strip() for line in block.replace("\\\n", " ").splitlines()]
    found += re.findall(r"`([^`\n]+)`", text)
    return [c for c in found if re.match(r"^(gf|glowforge-it)(?:\s|$)", c)]


def test_every_documented_command_parses_and_dry_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    copytree(ROOT / "docs/examples", "docs/examples")
    failures = []
    proof_available = importlib.util.find_spec("reportlab") is not None
    for command in sorted({c for doc in DOCS for c in _commands(doc.read_text())}):
        executable, *argv = shlex.split(command)
        if any(re.fullmatch(r"[A-Z_]{4,}", token) for token in argv):
            continue  # a placeholder such as --preset PRESET
        if "--proof-sheet" in argv and not proof_available:
            continue  # only PDF examples need the optional extra
        if "--verify-manifest" in argv:
            continue  # tested against real quick-start output below
        if '--export-audition' in argv:
            # Replay examples need a real, current record and contact sheet;
            # keep the documented command itself unchanged for dry-run.
            record = Path(argv[argv.index('--export-audition') + 1])
            if not record.exists():
                stem = record.stem.removesuffix('_audition')
                source = Path('audition-sources') / f'{stem}.png'
                source.parent.mkdir(exist_ok=True)
                Image.new('L', (30, 20), 140).save(source)
                assert gf_main(['--input', str(source), '-o', str(record.parent),
                                '--audition', 'photo-soft', 'line-art', 'stamp', '--quiet']) == 0
        Path("input").mkdir(exist_ok=True)
        wanted = [t for t in argv if t.startswith("input/")] or ["input/a.png"]
        for token in wanted:
            path = Path(token)
            if not path.suffix:  # a folder argument
                path.mkdir(parents=True, exist_ok=True)
                path = path / "a.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                Image.new("RGB", (600, 400), "gray").save(path)
        argv = [a for a in argv if a not in ("--dry-run", "--quiet")] + ["--dry-run", "--quiet"]
        entrypoint = gf_main if executable == "gf" else main
        try:
            code = entrypoint(argv)
        except SystemExit as exc:  # argparse rejects an unknown flag or value
            code = exc.code
        if code != 0:
            failures.append(command)
    assert not failures, f"documented commands that no longer run: {failures}"


def test_readme_quick_start_renders_selects_and_verifies(tmp_path, monkeypatch):
    readme = (ROOT / "README.md").read_text()
    section = readme.split("\n## Quick start\n", 1)[1].split("\n## ", 1)[0]
    workflow_block = re.search(r"```bash\n(.*?)```", section, re.S).group(0)
    commands = _commands(workflow_block)
    assert len(commands) == 4
    monkeypatch.chdir(tmp_path)
    copytree(ROOT / "docs/examples", "docs/examples")

    for command in commands:
        executable, *argv = shlex.split(command)
        assert executable == "gf"
        if "--verify-manifest" in argv:
            index = argv.index("--verify-manifest") + 1
            manifests = list(tmp_path.glob(argv[index]))
            assert len(manifests) == 1
            argv[index] = str(manifests[0])
        assert gf_main(argv) == 0, command
        if "--dry-run" in argv:
            assert not Path("output").exists()


def _parser_flags():
    return {o for a in build_parser()._actions for o in a.option_strings if o.startswith("--")}


def test_docs_only_mention_flags_the_cli_has():
    # GitNexus maintenance commands have their own parser, unrelated to gf.
    texts = ['\n'.join(line for line in doc.read_text().splitlines()
                       if not line.startswith('node .gitnexus/run.cjs ')) for doc in DOCS]
    mentioned = {f for text in texts for f in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", text)}
    unknown = mentioned - _parser_flags() - {"--with", "--extra"}  # `uv run --with/--extra` belong to uv
    assert not unknown, f"docs mention flags that do not exist: {sorted(unknown)}"


def test_readme_documents_every_cli_flag():
    readme = (ROOT / "README.md").read_text()
    # BooleanOptionalAction adds --no-x twins, and --fit-mode aliases --fit.
    missing = sorted(f for f in _parser_flags()
                     if f not in ("--help", "--fit-mode") and not f.startswith("--no-") and f not in readme)
    assert not missing, f"README does not document: {missing}"


def test_handbook_table_documents_every_cli_flag():
    handbook = (ROOT / "docs" / "handbook.md").read_text()
    missing = sorted(f for f in _parser_flags()
                     if f not in ("--help", "--fit-mode") and not f.startswith("--no-") and f not in handbook)
    assert not missing, f"handbook does not document: {missing}"
