"""Deterministic vector linework derived from a final binary artwork mask.

The output is a centerline-style SVG sidecar for inspection and editing. It is
not a cutline, does not select a machine operation, and does not replace the
authoritative PNG burn mask.
"""

import html

import numpy as np


def _foreground(image):
    """Return black, non-transparent pixels as a boolean foreground mask."""
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    return (rgba[:, :, 3] > 0) & (rgba[:, :, 0] < 128)


def skeletonize(image, max_iterations=1000):
    """Thin black artwork to a one-pixel Zhang-Suen-style skeleton."""
    if type(max_iterations) is not int or max_iterations < 1:
        raise ValueError("max_iterations must be a positive integer.")
    pixels = _foreground(image)

    def neighbors(mask):
        padded = np.pad(mask, 1, mode="constant", constant_values=False)
        return (
            padded[:-2, 1:-1],  # north
            padded[:-2, 2:],    # north-east
            padded[1:-1, 2:],   # east
            padded[2:, 2:],     # south-east
            padded[2:, 1:-1],   # south
            padded[2:, :-2],    # south-west
            padded[1:-1, :-2],  # west
            padded[:-2, :-2],   # north-west
        )

    def transitions(ordered):
        total = np.zeros_like(pixels, dtype=np.uint8)
        for current, following in zip(ordered, ordered[1:] + ordered[:1]):
            total += (~current & following).astype(np.uint8)
        return total

    for _ in range(max_iterations):
        changed = False
        ordered = neighbors(pixels)
        north, north_east, east, south_east, south, south_west, west, north_west = ordered
        count = sum(ordered)
        turns = transitions(list(ordered))
        remove = (
            pixels & (count >= 2) & (count <= 6) & (turns == 1)
            & ~(north & east & south)
            & ~(east & south & west)
        )
        if np.any(remove):
            pixels[remove] = False
            changed = True

        ordered = neighbors(pixels)
        north, north_east, east, south_east, south, south_west, west, north_west = ordered
        count = sum(ordered)
        turns = transitions(list(ordered))
        remove = (
            pixels & (count >= 2) & (count <= 6) & (turns == 1)
            & ~(north & east & west)
            & ~(north & south & west)
        )
        if np.any(remove):
            pixels[remove] = False
            changed = True
        if not changed:
            break
    else:
        raise RuntimeError("Linework thinning did not converge within max_iterations.")
    return pixels


def _neighbors(point, foreground):
    """Return 8-connected skeleton neighbors in stable clockwise order."""
    y, x = point
    height, width = foreground.shape
    found = []
    for dy, dx in (
        (-1, 0), (-1, 1), (0, 1), (1, 1),
        (1, 0), (1, -1), (0, -1), (-1, -1),
    ):
        ny, nx = y + dy, x + dx
        if 0 <= ny < height and 0 <= nx < width and foreground[ny, nx]:
            found.append((ny, nx))
    return found


def _edge_key(first, second):
    return tuple(sorted((first, second)))


def trace_skeleton(foreground):
    """Trace a skeleton into pixel-center polylines, preserving branch points."""
    if foreground.ndim != 2 or foreground.dtype != bool:
        raise ValueError("foreground must be a two-dimensional boolean array.")
    points = set(map(tuple, np.argwhere(foreground)))
    if not points:
        return []
    adjacency = {point: _neighbors(point, foreground) for point in points}
    nodes = {point for point, neighbors in adjacency.items() if len(neighbors) != 2}
    visited = set()
    paths = []

    def trace(first, second):
        path = [first, second]
        previous, current = first, second
        visited.add(_edge_key(previous, current))
        while current not in nodes:
            options = [candidate for candidate in adjacency[current] if candidate != previous]
            if not options:
                break
            following = next((candidate for candidate in options if _edge_key(current, candidate) not in visited), None)
            if following is None:
                break
            visited.add(_edge_key(current, following))
            path.append(following)
            previous, current = current, following
        return path

    for node in sorted(nodes):
        if not adjacency[node]:
            paths.append([node])
            continue
        for neighbor in adjacency[node]:
            if _edge_key(node, neighbor) not in visited:
                paths.append(trace(node, neighbor))

    # A closed loop has no endpoint or junction. Trace one remaining edge per loop.
    for point in sorted(points):
        for neighbor in adjacency[point]:
            if _edge_key(point, neighbor) not in visited:
                path = trace(point, neighbor)
                if path[-1] != point:
                    path.append(point)
                paths.append(path)
    return paths


def _path_d(points):
    """Encode pixel-center coordinates as a compact SVG polyline path."""
    if len(points) == 1:
        y, x = points[0]
        return f"M {x + 0.5:.3f} {y + 0.5:.3f}"
    commands = [f"M {points[0][1] + 0.5:.3f} {points[0][0] + 0.5:.3f}"]
    commands.extend(f"L {x + 0.5:.3f} {y + 0.5:.3f}" for y, x in points[1:])
    return " ".join(commands)


def render_centerline_svg(image, *, source_label=None):
    """Return a vector linework SVG aligned to the input pixel canvas."""
    width, height = image.size
    skeleton = skeletonize(image)
    paths = trace_skeleton(skeleton)
    label = html.escape(source_label or "final binary artwork mask", quote=True)
    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width / 300:.6f}in" height="{height / 300:.6f}in" '
        f'viewBox="0 0 {width} {height}" data-source="{label}" '
        'data-role="centerline-style-linework">',
        '  <title>Centerline-style vector linework; inspect before use.</title>',
        '  <g fill="none" stroke="#000000" stroke-width="1" '
        'stroke-linecap="round" stroke-linejoin="round">',
    ]
    body.extend(f'    <path d="{_path_d(path)}" />' for path in paths)
    body.extend(('  </g>', '</svg>', ''))
    return "\n".join(body)
