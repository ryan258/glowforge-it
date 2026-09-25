"""Glowforge image preparation.

Modules, lowest level first:

    settings     defaults, presets, resolved processing settings
    geometry     shape outlines and physical sizing
    workflow     burn semantics, registered geometry, previews, operation SVG
    imaging      image-to-image transformation
    publication  staging, replacement, rollback, recovery
    proof        one-page PDF rendering
    export       PNG/SVG/PDF rendering and one image's output set
    planning     source discovery, destination namespace, path protection
    batch        plan/execute coordination and batch outcome
    cli          argument parsing and the console entry point

Nothing here imports eagerly: import the module you need. Lower-level modules never
import `cli` or the compatibility launcher `main.py`.
"""

from .settings import __version__

__all__ = [
    '__version__',
    'batch',
    'cli',
    'export',
    'geometry',
    'imaging',
    'planning',
    'publication',
    'settings',
    'workflow',
    'proof',
]
