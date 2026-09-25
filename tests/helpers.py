"""Helpers shared by the split test modules."""

import os
import tempfile

from PIL import Image

# The keyword set process_directory/run_batch expect, with every stage at its default.
BATCH_DEFAULTS = dict(
    black_thresh=0, white_thresh=255, dither_thresh=128,
    clean_solids=False, clean_solids_black=35, clean_solids_white=220,
    invert=False, width_in=None, height_in=None, no_border=False,
    denoise_radius=0, contrast=1.5, sharpen_radius=2.0,
    sharpen_percent=150, sharpen_threshold=3,
    circle_cut=False, heart_cut=False, preset_name=None,
)


def gray(size=(8, 8)):
    return Image.new("RGB", size, "gray")


def folds_case(directory):
    """Local case-folding probe, independent of the implementation under test."""
    fd, probe = tempfile.mkstemp(prefix=".case-", dir=directory)
    os.close(fd)
    try:
        return os.path.exists(probe.replace(".case-", ".CASE-"))
    finally:
        os.unlink(probe)
