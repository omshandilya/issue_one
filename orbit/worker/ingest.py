"""Imports a new scene into the portal.

    python -m orbit.worker.ingest <source_file> <scene_id>

The source file sits next to a small description, <source_file>.json:
    {"name": "...", "acquired": "2025-03-01T01:03:25Z", "bbox": [min_lon, min_lat, max_lon, max_lat]}
"""
import json
import os
import sys
import uuid

from orbit import config
from orbit.catalog import db as dbmod

CHUNK = 1 << 20


def fault_hook(written):
    """Test harness: ORBIT_FAULT_KILL_AFTER_BYTES=N stops the process dead (like a power cut) once N bytes are written."""
    limit = os.environ.get("ORBIT_FAULT_KILL_AFTER_BYTES")
    if limit and written >= int(limit):
        os._exit(137)


def read_chunks(path):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                return
            yield chunk


def load_meta(src):
    with open(src + ".json") as f:
        return json.load(f)


def ingest(src, scene_id):
    meta = load_meta(src)
    size = os.path.getsize(src)
    final_path = f"{config.FILES_DIR}/{scene_id}.bin"
    os.makedirs(config.FILES_DIR, exist_ok=True)
    temp_path = f"{final_path}.tmp.{os.getpid()}"

    written = 0
    try:
        with open(temp_path, "wb") as out:
            for chunk in read_chunks(src):
                fault_hook(written)
                out.write(chunk)
                written += len(chunk)
            out.flush()
            os.fsync(out.fileno())
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise

    # Atomically place the fully-written file
    os.replace(temp_path, final_path)

    # Record the scene in the database and commit only after the file is complete
    db = dbmod.connect()
    dbmod.init_db(db)
    dbmod.add_scene(db, scene_id, meta.get("name", scene_id), meta["acquired"],
                    *meta["bbox"], file_path=final_path, size_bytes=size)
    db.commit()
    print(f"imported {scene_id}: {written} bytes")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    ingest(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
