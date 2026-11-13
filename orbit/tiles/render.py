"""Draws map tiles for a scene. (The portal ships synthetic imagery; real scenes would be read from GeoTIFFs.)"""
import hashlib
import io
import math

import numpy as np
from PIL import Image

SIZE = 256


def tile_bounds(z, x, y):
    """(min_lon, min_lat, max_lon, max_lat) of a web-map tile."""
    n = 2 ** z
    lon0, lon1 = x / n * 360.0 - 180.0, (x + 1) / n * 360.0 - 180.0
    lat = lambda t: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * t / n))))
    return lon0, lat(y + 1), lon1, lat(y)


def scene_parts(minx, miny, maxx, maxy):
    """A scene crossing the date line is two boxes."""
    return [(minx, miny, maxx, maxy)] if minx <= maxx else [(minx, miny, 180.0, maxy), (-180.0, miny, maxx, maxy)]


def intersects(parts, b):
    return any(p[0] <= b[2] and p[2] >= b[0] and p[1] <= b[3] and p[3] >= b[1] for p in parts)


def render_png(scene_id, parts, z, x, y):
    b = tile_bounds(z, x, y)
    n = 2 ** z
    cols = b[0] + (np.arange(SIZE) + 0.5) / SIZE * (b[2] - b[0])
    ty = y + (np.arange(SIZE) + 0.5) / SIZE
    rows = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * ty / n))))
    inside = np.zeros((SIZE, SIZE), bool)
    for (x0, y0, x1, y1) in parts:
        inside |= ((cols >= x0) & (cols <= x1))[None, :] & ((rows >= y0) & (rows <= y1))[:, None]
    seed = int.from_bytes(hashlib.sha1(f"{scene_id}/{z}/{x}/{y}".encode()).digest()[:8], "little")
    rng = np.random.default_rng(seed)
    # Tiles differ a lot in size: smooth ones compress to a few KB, busy ones to a couple of hundred KB.
    amp = (0, 18, 60, 120)[seed % 4]
    base = (np.linspace(40, 160, SIZE)[None, :] + np.linspace(0, 60, SIZE)[:, None]).astype(np.float32)
    img = np.clip(base + (rng.normal(0, amp, (SIZE, SIZE)) if amp else 0), 0, 255).astype(np.uint8)
    rgba = np.dstack([img, img, np.minimum(255, img + 30).astype(np.uint8), np.where(inside, 255, 0).astype(np.uint8)])
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", compress_level=1)
    return buf.getvalue()
