"""Glowforge image preparation.

Modules, lowest level first:

    settings     defaults, presets, resolved processing settings
    geometry     shape outlines and physical sizing
    imaging      image-to-image transformation
    publication  staging, replacement, rollback, recovery
    export       PNG/SVG rendering and one image's output set
    planning     source discovery, destination namespace, path protection
    batch        plan/execute coordination and batch outcome
    cli          argument parsing and the console entry point

Nothing here imports eagerly: import the module you need. Lower-level modules never
import `cli` or the compatibility launcher `main.py`.
"""

__all__ = [
    'batch', 'cli', 'export', 'geometry', 'imaging', 'planning', 'publication', 'settings',
]
