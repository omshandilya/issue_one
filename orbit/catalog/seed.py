"""Demo data for the portal: deterministic, so every run gives the same scenes."""
import os
import random
from datetime import datetime, timedelta, timezone

import numpy as np

from orbit import config
from orbit.catalog import db as dbmod

LARGE_ID = "S1_kochi_20251012_large"
LARGE_BYTES = 48 * 1024 * 1024          # a "large scene" file, generated pattern (not a real image)
SMALL_BYTES = 2 * 1024 * 1024


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_pattern_file(path, size, seed):
    """Deterministic pseudo-random content, so a wrong byte count or offset shows up as a checksum mismatch."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rng = np.random.default_rng(seed)
    with open(path, "wb") as f:
        left = size
        while left > 0:
            n = min(left, 4 * 1024 * 1024)
            f.write(rng.integers(0, 256, size=n, dtype=np.uint8).tobytes())
            left -= n


def seed(db_path=None, files_dir=None):
    db_path = db_path or config.DB_PATH
    files_dir = files_dir or config.FILES_DIR
    if os.path.exists(db_path):
        os.remove(db_path)
    db = dbmod.connect(db_path)
    dbmod.init_db(db)
    rng = random.Random(7)
    n = 0

    def add(region, when, box, restricted=None, file_path=None, size=None, scene_id=None, name=None):
        nonlocal n
        n += 1
        sid = scene_id or f"S1_{region}_{when:%Y%m%d}_{n:03d}"
        dbmod.add_scene(db, sid, name or sid, _iso(when), *box, restricted_unit=restricted, file_path=file_path, size_bytes=size)
        return sid

    # Mumbai: 20 scenes, January to March 2025; some share a timestamp (same satellite pass)
    base = datetime(2025, 1, 7, 1, 3, 25, tzinfo=timezone.utc)
    for i in range(20):
        when = base + timedelta(days=12 * (i // 4))
        x, y = 72.70 + 0.05 * (i % 6), 18.80 + 0.05 * (i % 5)
        add("mumbai", when, (x, y, x + 0.25, y + 0.25))

    # Kutch: 15 restricted to Unit A, plus 10 public, same area
    kutch = datetime(2025, 2, 3, 6, 0, 0, tzinfo=timezone.utc)
    for i in range(25):
        x, y = 69.0 + rng.uniform(0, 1.0), 22.0 + rng.uniform(0, 1.0)
        add("kutch", kutch + timedelta(hours=3 * i), (x, y, x + 0.4, y + 0.4), restricted="A" if i < 15 else None)

    # Odisha coast: 30 scenes over four days, many with identical timestamps
    od = datetime(2025, 10, 25, 5, 10, 0, tzinfo=timezone.utc)
    for i in range(30):
        x, y = 84.6 + rng.uniform(0, 2.5), 19.1 + rng.uniform(0, 2.2)
        add("odisha", od + timedelta(days=i // 8), (x, y, x + 0.45, y + 0.4))

    # Fiji: 12 scenes (5 west of the date line, 5 east, 2 crossing it)
    fiji = datetime(2025, 11, 2, 17, 40, 0, tzinfo=timezone.utc)
    for i in range(5):
        x, y = 177.2 + 0.5 * i, -19.0 + 0.5 * (i % 3)
        add("fiji", fiji + timedelta(hours=i), (x, y, x + 0.6, y + 0.5))
    for i in range(5):
        x, y = -179.9 + 0.35 * i, -18.8 + 0.5 * (i % 3)
        add("fiji", fiji + timedelta(hours=10 + i), (x, y, x + 0.6, y + 0.5))
    for i in range(2):
        add("fiji", fiji + timedelta(hours=20 + i), (179.3, -17.5 - 0.6 * i, -179.4, -17.0 - 0.6 * i))   # crosses 180

    # Kochi: the large downloadable scene and two small ones
    for sid, size, seed_no in ((LARGE_ID, LARGE_BYTES, 101), ("S1_kochi_20251012_small_a", SMALL_BYTES, 102), ("S1_kochi_20251012_small_b", SMALL_BYTES, 103)):
        fp = f"{files_dir}/{sid}.bin"
        write_pattern_file(fp, size, seed_no)
        add("kochi", datetime(2025, 10, 12, 0, 20, 0, tzinfo=timezone.utc), (76.0, 9.8, 76.6, 10.3), file_path=fp, size=size, scene_id=sid)

    # Elsewhere: 60 scenes across the world (kept away from the Fiji box)
    for i in range(60):
        x, y = rng.uniform(-150, 150), rng.uniform(-50, 55)
        add("world", datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=rng.randint(0, 24 * 300)), (x, y, x + 0.5, y + 0.4))

    db.commit()
    total = db.execute("SELECT COUNT(*) FROM scenes").fetchone()[0]
    db.close()
    return total
