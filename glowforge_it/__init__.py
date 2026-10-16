"""Glowforge image preparation.

Modules, lowest level first (tests/test_compat.py enforces this order):

    settings        defaults, presets, resolved processing settings
    geometry        shape outlines, physical sizing, rotated canvas bounds
    workflow        burn semantics, registered geometry, previews, operation SVG
    publication     staging, replacement, rollback, recovery
    contracts       artifact names, resource bounds, runtime identity, stable source bytes
    renderers       deterministic binary mark-making renderers
    vector          deterministic centerline-style SVG linework
    personalization protected text-stamp masks
    qr              constrained QR sidecar renderer
    imaging         image-to-image transformation
    proof           one-page PDF rendering
    export          PNG/SVG/PDF rendering and one image's output set
    planning     source discovery, destination namespace, path protection
    proofing     mode-agnostic visual proofing and preset audition
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
    'contracts',
    'export',
    'geometry',
    'imaging',
    'planning',
    'publication',
    'renderers',
    'vector',
    'personalization',
    'qr',
    'settings',
    'workflow',
    'proof',
    'proofing',
]
