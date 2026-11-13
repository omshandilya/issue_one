import hashlib
import json
import os
import subprocess
import sys

import pytest

from orbit import config
from orbit.catalog import db as dbmod
from orbit.gateway import range_proxy
from orbit.tiles.cache import TileCache


def test_t4_range_resumed_download_matches_checksum():
    path = f"{config.FILES_DIR}/S1_kochi_20251012_small_a.bin"
    total_size = os.path.getsize(path)
    expected_info = range_proxy.checksum(path)

    # Download file in 500 KB chunks using Range headers
    chunk_size = 500 * 1024
    assembled = bytearray()
    start = 0

    while start < total_size:
        end = min(start + chunk_size - 1, total_size - 1)
        resp = range_proxy.serve_file(path, f"bytes={start}-{end}")
        assert resp.status_code == 206
        expected_len = end - start + 1
        assert len(resp.body) == expected_len
        assert resp.headers["Content-Range"] == f"bytes {start}-{end}/{total_size}"
        assembled.extend(resp.body)
        start = end + 1

    assert len(assembled) == total_size
    assert hashlib.sha256(assembled).hexdigest() == expected_info["sha256"]


def test_t5_tile_cache_lru_and_size_capping():
    # Configure cache with max_items=3 and max_mb=1 (approx 1 MB)
    cache = TileCache(max_items=3, max_mb=1)

    tile_a = b"A" * 1000
    tile_b = b"B" * 1000
    tile_c = b"C" * 1000
    tile_d = b"D" * 1000

    cache.put("tile_a", tile_a)
    cache.put("tile_b", tile_b)
    cache.put("tile_c", tile_c)

    # Access tile_a to make tile_b the oldest
    assert cache.get("tile_a") == tile_a

    # Insert tile_d; should evict tile_b (oldest), NOT tile_d or tile_a
    cache.put("tile_d", tile_d)

    assert cache.get("tile_b") is None  # evicted
    assert cache.get("tile_a") == tile_a  # kept
    assert cache.get("tile_c") == tile_c  # kept
    assert cache.get("tile_d") == tile_d  # kept

    # Test byte limit eviction
    small_mb_cache = TileCache(max_mb=0.002)  # ~2 KB
    small_mb_cache.put("big_1", b"X" * 1500)
    small_mb_cache.put("big_2", b"Y" * 1500)

    # Adding big_2 should have evicted big_1 because total > 2 KB
    assert small_mb_cache.get("big_1") is None
    assert small_mb_cache.get("big_2") == b"Y" * 1500
    assert small_mb_cache.current_bytes <= 2048


def test_t6_interrupted_ingest_leaves_no_corrupted_or_duplicate_scenes(tmp_path):
    # Prepare dummy incoming scene
    src_file = tmp_path / "test_scene.bin"
    content = b"Z" * (2 * 1024 * 1024)  # 2 MB
    src_file.write_bytes(content)

    meta_file = tmp_path / "test_scene.bin.json"
    meta_file.write_text(json.dumps({
        "name": "S1_test_scene_powercut",
        "acquired": "2025-11-10T12:00:00Z",
        "bbox": [75.0, 15.0, 75.5, 15.5]
    }))

    scene_id = "S1_test_powercut_001"
    final_bin = os.path.join(config.FILES_DIR, f"{scene_id}.bin")
    if os.path.exists(final_bin):
        os.remove(final_bin)

    # Clean up any leftover test data
    db = dbmod.connect()
    db.execute("DELETE FROM scenes WHERE id = ? OR name = ?", (scene_id, "S1_test_scene_powercut"))
    db.execute("DELETE FROM scene_rtree WHERE rid IN (SELECT rid FROM scene_index WHERE scene_id = ?)", (scene_id,))
    db.execute("DELETE FROM scene_index WHERE scene_id = ?", (scene_id,))
    db.commit()

    # 1. Run ingest with ORBIT_FAULT_KILL_AFTER_BYTES=500000 (aborts after 500 KB)
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["ORBIT_FAULT_KILL_AFTER_BYTES"] = "500000"
    proc = subprocess.run(
        [sys.executable, "-m", "orbit.worker.ingest", str(src_file), scene_id],
        env=env,
        capture_output=True,
    )
    assert proc.returncode != 0

    # Scene must NOT exist in the database or as broken final file
    db = dbmod.connect()
    row = db.execute("SELECT * FROM scenes WHERE id = ? OR name = ?", (scene_id, "S1_test_scene_powercut")).fetchone()
    assert row is None
    assert not os.path.exists(final_bin)

    # 2. Re-run ingest normally (simulating restart after power cut)
    env.pop("ORBIT_FAULT_KILL_AFTER_BYTES", None)
    proc2 = subprocess.run(
        [sys.executable, "-m", "orbit.worker.ingest", str(src_file), scene_id],
        env=env,
        capture_output=True,
    )
    assert proc2.returncode == 0
    assert os.path.exists(final_bin)
    assert os.path.getsize(final_bin) == len(content)

    # Exactly 1 scene in database
    rows = db.execute("SELECT * FROM scenes WHERE name = ?", ("S1_test_scene_powercut",)).fetchall()
    assert len(rows) == 1
    assert rows[0]["id"] == scene_id

    # 3. Running ingest again does not create duplicates
    proc3 = subprocess.run(
        [sys.executable, "-m", "orbit.worker.ingest", str(src_file), scene_id],
        env=env,
        capture_output=True,
    )
    assert proc3.returncode == 0
    rows = db.execute("SELECT * FROM scenes WHERE name = ?", ("S1_test_scene_powercut",)).fetchall()
    assert len(rows) == 1
