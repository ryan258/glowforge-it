"""The `main.py` launcher must keep working: `gf` runs it by absolute path."""

import ast
import os
import subprocess
import sys

import main


def test_launcher_reexports_the_public_surface():
    for name in main.__all__:
        assert hasattr(main, name), name
    # The names review probes and older tests reach for.
    for name in ("transform_image", "process_directory", "publish_generation",
                 "prep_for_glowforge", "output_geometry", "main", "os"):
        assert hasattr(main, name), name


def test_launcher_keeps_the_uv_script_metadata():
    """`gf` relies on this header to resolve dependencies; extraction must not drop it."""
    header = open(main.__file__).read().split("# ///")[1]
    assert 'requires-python = ">=3.11"' in header
    assert "pillow==" in header and "numpy==" in header


def _package_deps(source):
    """Local imports a module declares, as bare module names (both spellings)."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:                          # from .imaging import ...
                if node.module:
                    yield node.module.split(".")[0]
                else:                                     # from . import imaging
                    for alias in node.names:
                        yield alias.name
            elif node.level == 0 and node.module:         # from glowforge_it.imaging import ...
                head, _, rest = node.module.partition(".")
                if head == "glowforge_it":
                    if rest:
                        yield rest.split(".")[0]
                    else:
                        for alias in node.names:
                            yield alias.name
                elif head == "main":
                    yield "main"
        elif isinstance(node, ast.Import):                # import glowforge_it.imaging / import main
            for alias in node.names:
                head, _, rest = alias.name.partition(".")
                if head == "glowforge_it":
                    yield rest.split(".")[0] if rest else ""
                elif head == "main":
                    yield "main"


def test_package_has_no_circular_or_downward_imports():
    layers = ["settings", "geometry", "workflow", "imaging", "publication", "proof", "export",
              "planning", "batch", "cli"]
    rank = {name: index for index, name in enumerate(layers)}
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "glowforge_it")
    found = sorted(f[:-3] for f in os.listdir(root) if f.endswith(".py"))
    assert found == sorted(layers + ["__init__"]), f"unlisted module: {found}"
    for name in found:
        source = open(os.path.join(root, f"{name}.py")).read()
        for dep in _package_deps(source):
            assert dep != "main", f"{name} imports the compatibility launcher"
            if name == "__init__" or not dep:
                continue
            assert rank[dep] < rank[name], f"{name} imports {dep}"


def test_the_dependency_guard_catches_every_import_spelling():
    for bad in ("from .cli import main", "from glowforge_it.cli import main",
                "from glowforge_it import cli", "import glowforge_it.cli",
                "import main", "from main import os"):
        assert set(_package_deps(bad)) & {"cli", "main"}, bad


def test_launcher_runs_as_a_script(tmp_path):
    from PIL import Image
    source = tmp_path / "in"
    source.mkdir()
    Image.new("RGB", (16, 16), "gray").save(source / "a.png")
    result = subprocess.run(
        [sys.executable, main.__file__, "--input", str(source), "-o", str(tmp_path / "out")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "out" / "a_png_dithered.png").exists()
