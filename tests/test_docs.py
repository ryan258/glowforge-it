"""The docs cannot drift from the CLI: documented commands run, and every flag is documented."""

import re
import shlex
from pathlib import Path

import pytest
from PIL import Image

from glowforge_it.cli import build_parser, gf_main

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
# CHANGELOG and roadmap are history and plans: they legitimately mention removed or future flags.


def _commands(text):
    """`gf ...` lines from fenced blocks (joining backslash continuations) and inline code."""
    found = []
    for block in re.findall(r"```(?:bash|sh|shell|zsh)?\n(.*?)```", text, re.S):
        found += [line.strip() for line in block.replace("\\\n", " ").splitlines()]
    found += re.findall(r"`([^`\n]+)`", text)
    return [c for c in found if re.match(r"(gf|glowforge-it)\s", c)]


def test_every_documented_command_parses_and_dry_runs(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")  # --proof-sheet examples need the optional extra
    monkeypatch.chdir(tmp_path)
    failures = []
    for command in sorted({c for doc in DOCS for c in _commands(doc.read_text())}):
        argv = shlex.split(command)[1:]
        if any(re.fullmatch(r"[A-Z_]{4,}", token) for token in argv):
            continue  # a placeholder such as --preset PRESET
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
        argv = [a for a in argv if a not in ("--dry-run", "--quiet")] + ["--dry-run", "--quiet", "-o", "check-out"]
        try:
            code = gf_main(argv)
        except SystemExit as exc:  # argparse rejects an unknown flag or value
            code = exc.code
        if code != 0:
            failures.append(command)
    assert not failures, f"documented commands that no longer run: {failures}"


def _parser_flags():
    return {o for a in build_parser()._actions for o in a.option_strings if o.startswith("--")}


def test_docs_only_mention_flags_the_cli_has():
    mentioned = {f for doc in DOCS for f in re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", doc.read_text())}
    unknown = mentioned - _parser_flags() - {"--with", "--extra"}  # `uv run --with/--extra` belong to uv
    assert not unknown, f"docs mention flags that do not exist: {sorted(unknown)}"


def test_readme_documents_every_cli_flag():
    readme = (ROOT / "README.md").read_text()
    # BooleanOptionalAction adds --no-x twins, and --fit-mode aliases --fit.
    missing = sorted(f for f in _parser_flags()
                     if f not in ("--help", "--fit-mode") and not f.startswith("--no-") and f not in readme)
    assert not missing, f"README does not document: {missing}"
