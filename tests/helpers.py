"""Helpers shared by the split test modules."""

import os
import tempfile

from PIL import Image


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
