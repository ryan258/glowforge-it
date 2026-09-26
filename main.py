# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "numpy==2.4.2",
#     "pillow==12.1.1",
#     "segno==1.6.6",
# ]
# ///

"""Launcher for the `glowforge_it` package.

Kept so `uv run main.py` works from a checkout: the inline script metadata above tells
`uv` which dependencies to install. Import from
`glowforge_it` directly.
"""

import sys

from glowforge_it.cli import main

if __name__ == "__main__":
    sys.exit(main())
